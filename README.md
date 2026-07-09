# claude-luau-lsp

Luau LSP plugin for Claude Code. Type checking, go-to-definition, hover info, and diagnostics for `.luau` and `.lua` files, with Roblox API types loaded automatically when the workspace is a Roblox project.

## Prerequisites

[luau-lsp](https://github.com/JohnnyMorganz/luau-lsp) must be installed. Any of these work:

```bash
rokit add JohnnyMorganz/luau-lsp
aftman add JohnnyMorganz/luau-lsp
```

A copy on `PATH` also works. The launcher checks `PATH` first, then `~/.rokit/bin`, `~/.aftman/bin`, and `~/.foreman/bin`.

## Installation

```bash
claude plugin marketplace add dig1t/claude-luau-lsp
claude plugin install luau-lsp@claude-luau-lsp
```

## How it works

The plugin starts `luau-lsp` through a launcher script that inspects the workspace root:

| Workspace | Launch mode |
|---|---|
| Has `globalTypes.d.luau` | Roblox: uses the project's own definitions file, never modifies it |
| Has `wally.toml` or a `*.project.json` (Rojo) | Roblox: uses a cached copy of the [Roblox API definitions](https://raw.githubusercontent.com/JohnnyMorganz/luau-lsp/main/scripts/globalTypes.d.luau), downloaded on first use and refreshed when older than 24 hours |
| Anything else | Plain Luau: bare `luau-lsp lsp`, no Roblox globals |

The cached definitions live in `~/.cache/claude-luau-lsp/` (or `$XDG_CACHE_HOME/claude-luau-lsp/`). If a refresh fails (offline, proxy), the stale copy is used and a warning goes to stderr. Roblox projects no longer need their own `.claude-plugin/plugin.json` to get Roblox types.

If a `luau-lsp` binary exists but will not start (a toolchain shim killed by macOS with "Code Signature Invalid", or an aftman shim run outside a tree with an `aftman.toml`), the launcher skips it, says why on stderr, and falls back to the next candidate, including the real binaries inside `~/.rokit/tool-storage` and `~/.aftman/tool-storage`.

## Rojo sourcemaps

luau-lsp picks up `sourcemap.json` from the workspace root by itself. Generating the sourcemap is left to the project. A SessionStart hook in the project's `.claude/settings.json` works well:

```json
{
	"hooks": {
		"SessionStart": [
			{
				"matcher": "*",
				"hooks": [
					{
						"type": "command",
						"command": "rojo sourcemap --include-non-scripts --output sourcemap.json"
					}
				]
			}
		]
	}
}
```

## Configuration

Both knobs are environment variables read by the launcher:

| Variable | Effect |
|---|---|
| `CLAUDE_LUAU_LSP_BIN` | Absolute path to the `luau-lsp` binary to use. Skips auto-detection when it runs; falls back to auto-detection when it does not. |
| `CLAUDE_LUAU_LSP_TYPES_URL` | Alternate URL for `globalTypes.d.luau` (internal mirrors, pinned versions). |

## Troubleshooting

The launcher logs to stderr with a `[claude-luau-lsp]` prefix. Claude Code shows LSP server logs in `claude --debug`.

- **"no working luau-lsp found"**: install luau-lsp (see prerequisites), or point `CLAUDE_LUAU_LSP_BIN` at a binary.
- **"exists but does not run"** on macOS: the toolchain shim's code signature went stale and the OS kills it on launch. Fix with `codesign --force --sign - ~/.aftman/bin/*` (aftman is the usual offender). The launcher works around this by using the tool-storage binary directly, so the LSP still starts.
- **Roblox globals missing in a Roblox project**: the workspace root needs one of the markers from the table above. Add `wally.toml`, a Rojo `*.project.json`, or a `globalTypes.d.luau`.
- **Definitions look outdated**: delete `~/.cache/claude-luau-lsp/globalTypes.d.luau`; the next launch re-downloads.

## Testing

```bash
python3 tests/lsp_smoke.py
```

Spawns the launcher as a real LSP server in throwaway workspaces and checks all five modes: bare, cached defs, project defs, stale-cache refresh, and refresh-failure fallback. Needs `python3`, a working `luau-lsp`, and network for the first cache fill.

## Windows

The launcher is a bash script. It works under WSL and Git Bash; native Windows spawning of `.sh` files is not supported by Claude Code's LSP host. Line endings are pinned to LF via `.gitattributes`.
