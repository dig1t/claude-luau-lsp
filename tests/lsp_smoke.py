#!/usr/bin/env python3
"""Smoke test for bin/luau-lsp.sh.

Spawns the wrapper as a real LSP server in throwaway workspaces and checks:
  1. plain workspace  -> bare mode: Color3 IS an unknown global
  2. Roblox workspace (wally.toml, no local defs) -> cache mode: Color3 known
  3. Roblox workspace with its own globalTypes.d.luau -> project-defs mode
  4. stale cache (>24h) is refreshed on launch
  5. unreachable defs URL + warm cache -> still starts with stale defs

Requires: python3, luau-lsp on PATH, network for the first cache fill.
Usage: python3 tests/lsp_smoke.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WRAPPER = REPO / "bin" / "luau-lsp.sh"

SAMPLE = 'local c = Color3.fromRGB(255, 0, 0)\nprint(c)\n'


def lsp_request(proc, msg_id, method, params):
    body = json.dumps(
        {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params}
    )
    proc.stdin.write(f"Content-Length: {len(body)}\r\n\r\n{body}".encode())
    proc.stdin.flush()


def lsp_notify(proc, method, params):
    body = json.dumps({"jsonrpc": "2.0", "method": method, "params": params})
    proc.stdin.write(f"Content-Length: {len(body)}\r\n\r\n{body}".encode())
    proc.stdin.flush()


def read_messages(proc, seconds):
    """Read LSP messages from stdout for up to `seconds`, return them all."""
    import select

    messages = []
    buf = b""
    deadline = time.time() + seconds
    fd = proc.stdout.fileno()
    while time.time() < deadline:
        ready, _, _ = select.select([fd], [], [], 0.2)
        if not ready:
            continue
        chunk = os.read(fd, 65536)
        if not chunk:
            break
        buf += chunk
        while True:
            header_end = buf.find(b"\r\n\r\n")
            if header_end == -1:
                break
            headers = buf[:header_end].decode(errors="replace")
            length = None
            for line in headers.split("\r\n"):
                if line.lower().startswith("content-length:"):
                    length = int(line.split(":")[1].strip())
            if length is None or len(buf) < header_end + 4 + length:
                break
            body = buf[header_end + 4 : header_end + 4 + length]
            buf = buf[header_end + 4 + length :]
            try:
                messages.append(json.loads(body))
            except json.JSONDecodeError:
                pass
    return messages


def diagnostics_for(workspace, env=None):
    """Run the wrapper in `workspace`, open sample.luau, return diagnostics."""
    src = workspace / "sample.luau"
    src.write_text(SAMPLE)

    full_env = dict(os.environ)
    if env:
        full_env.update(env)

    proc = subprocess.Popen(
        [str(WRAPPER)],
        cwd=workspace,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=full_env,
    )
    try:
        lsp_request(
            proc,
            1,
            "initialize",
            {
                "processId": os.getpid(),
                "rootUri": workspace.as_uri(),
                "capabilities": {},
                "workspaceFolders": [
                    {"uri": workspace.as_uri(), "name": "test"}
                ],
            },
        )
        # Wait for the initialize result before proceeding.
        for _ in range(50):
            msgs = read_messages(proc, 1)
            if any(m.get("id") == 1 for m in msgs):
                break
            if proc.poll() is not None:
                raise RuntimeError(
                    "server exited early:\n" + proc.stderr.read().decode()
                )
        lsp_notify(proc, "initialized", {})
        lsp_notify(
            proc,
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": src.as_uri(),
                    "languageId": "luau",
                    "version": 1,
                    "text": SAMPLE,
                }
            },
        )
        diags = []
        deadline = time.time() + 15
        while time.time() < deadline:
            for m in read_messages(proc, 1):
                if m.get("method") == "textDocument/publishDiagnostics":
                    if m["params"]["uri"] == src.as_uri():
                        diags = m["params"]["diagnostics"]
                        return diags
        return diags
    finally:
        proc.kill()
        proc.wait()


def has_unknown_color3(diags):
    return any(
        "Color3" in d.get("message", "") and "Unknown" in d.get("message", "")
        for d in diags
    )


def run_case(name, fn):
    try:
        fn()
        print(f"PASS  {name}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL  {name}: {exc}")
        return False


def find_working_binary():
    """A luau-lsp that runs from ANY cwd (toolchain shims need a manifest
    up the tree, so a PATH hit alone is not enough for temp fixtures)."""
    home = Path.home()
    candidates = []
    on_path = shutil.which("luau-lsp")
    if on_path:
        candidates.append(Path(on_path))
    for storage in (
        home / ".rokit" / "tool-storage" / "JohnnyMorganz" / "luau-lsp",
        home / ".aftman" / "tool-storage" / "JohnnyMorganz" / "luau-lsp",
    ):
        if storage.is_dir():
            versions = sorted(storage.iterdir(), reverse=True)
            candidates.extend(v / "luau-lsp" for v in versions)
    for c in candidates:
        if not c.is_file():
            continue
        try:
            ok = (
                subprocess.run(
                    [str(c), "--version"],
                    cwd=tempfile.gettempdir(),
                    capture_output=True,
                    timeout=10,
                ).returncode
                == 0
            )
        except (OSError, subprocess.TimeoutExpired):
            ok = False
        if ok:
            return c
    return None


def main():
    binary = find_working_binary()
    if binary is None:
        print("SKIP: no working luau-lsp found")
        sys.exit(1)

    tmp = Path(tempfile.mkdtemp(prefix="claude-luau-lsp-test-"))
    cache_home = tmp / "cache"
    cache_defs = cache_home / "claude-luau-lsp" / "globalTypes.d.luau"
    # CLAUDE_LUAU_LSP_BIN also exercises the wrapper's override path.
    base_env = {
        "XDG_CACHE_HOME": str(cache_home),
        "CLAUDE_LUAU_LSP_BIN": str(binary),
    }
    results = []

    def case_plain():
        ws = tmp / "plain"
        ws.mkdir()
        diags = diagnostics_for(ws, base_env)
        assert has_unknown_color3(diags), (
            f"expected 'Unknown global Color3' in bare mode, got: {diags}"
        )

    def case_roblox_cache():
        ws = tmp / "roblox-cache"
        ws.mkdir()
        (ws / "wally.toml").write_text("[package]\n")
        diags = diagnostics_for(ws, base_env)
        assert cache_defs.is_file() and cache_defs.stat().st_size > 100_000, (
            "cache file was not downloaded"
        )
        assert not has_unknown_color3(diags), (
            f"Color3 unknown despite Roblox cache mode: {diags}"
        )

    def case_roblox_project_defs():
        ws = tmp / "roblox-project"
        ws.mkdir()
        shutil.copy(cache_defs, ws / "globalTypes.d.luau")
        mtime_before = cache_defs.stat().st_mtime
        diags = diagnostics_for(ws, base_env)
        assert not has_unknown_color3(diags), (
            f"Color3 unknown despite project defs: {diags}"
        )
        assert cache_defs.stat().st_mtime == mtime_before, (
            "cache was touched in project-defs mode"
        )

    def case_stale_refresh():
        old = time.time() - 90000  # ~25h
        os.utime(cache_defs, (old, old))
        ws = tmp / "roblox-stale"
        ws.mkdir()
        (ws / "wally.toml").write_text("[package]\n")
        diagnostics_for(ws, base_env)
        assert cache_defs.stat().st_mtime > old + 3600, (
            "stale cache was not refreshed"
        )

    def case_offline_stale():
        old = time.time() - 90000
        os.utime(cache_defs, (old, old))
        ws = tmp / "roblox-offline"
        ws.mkdir()
        (ws / "wally.toml").write_text("[package]\n")
        env = dict(base_env)
        env["CLAUDE_LUAU_LSP_TYPES_URL"] = "https://invalid.invalid/defs"
        diags = diagnostics_for(ws, env)
        assert not has_unknown_color3(diags), (
            f"stale cache not used when refresh failed: {diags}"
        )

    results.append(run_case("plain workspace -> bare mode", case_plain))
    results.append(run_case("roblox workspace -> cached defs", case_roblox_cache))
    results.append(
        run_case("roblox workspace -> project defs untouched", case_roblox_project_defs)
    )
    results.append(run_case("stale cache refreshed on launch", case_stale_refresh))
    results.append(
        run_case("refresh failure -> stale cache still used", case_offline_stale)
    )

    shutil.rmtree(tmp, ignore_errors=True)
    if all(results):
        print(f"\nall {len(results)} cases passed")
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()
