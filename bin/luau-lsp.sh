#!/bin/bash
# Launcher for luau-lsp with Roblox auto-detection.
#
# Claude Code spawns this in the workspace root. If the workspace looks like
# a Roblox project, launch luau-lsp with Roblox API definitions (the project's
# own globalTypes.d.luau when present, otherwise a plugin-managed cached copy
# refreshed every 24h). Plain Luau workspaces get a bare `luau-lsp lsp`.
#
# LSP speaks over stdout — everything this script prints goes to stderr.

set -u

# Overridable for enterprise mirrors / tests.
GLOBAL_TYPES_URL="${CLAUDE_LUAU_LSP_TYPES_URL:-https://raw.githubusercontent.com/JohnnyMorganz/luau-lsp/main/scripts/globalTypes.d.luau}"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/claude-luau-lsp"
CACHE_DEFS="$CACHE_DIR/globalTypes.d.luau"
MAX_AGE_SECONDS=86400 # 24h

log() {
	echo "[claude-luau-lsp] $*" >&2
}

# ── Resolve the luau-lsp binary ──────────────────────────────────────────
# CLAUDE_LUAU_LSP_BIN override first, then PATH, then the common Roblox
# toolchain manager bins (the LSP spawn environment does not always source
# the user's shell profile). Every candidate is exec-validated: toolchain
# manager shims (aftman especially) can die with "Code Signature Invalid"
# on macOS while still looking perfectly executable.
works() {
	"$1" --version >/dev/null 2>&1
}

resolve_bin() {
	local candidate

	if [ -n "${CLAUDE_LUAU_LSP_BIN:-}" ]; then
		if works "$CLAUDE_LUAU_LSP_BIN"; then
			echo "$CLAUDE_LUAU_LSP_BIN"
			return 0
		fi
		log "WARNING: CLAUDE_LUAU_LSP_BIN ($CLAUDE_LUAU_LSP_BIN) does not run" \
			"— falling back to auto-detection"
	fi

	for candidate in \
		"$(command -v luau-lsp 2>/dev/null)" \
		"$HOME/.rokit/bin/luau-lsp" \
		"$HOME/.aftman/bin/luau-lsp" \
		"$HOME/.foreman/bin/luau-lsp"; do
		[ -n "$candidate" ] && [ -x "$candidate" ] || continue
		if works "$candidate"; then
			echo "$candidate"
			return 0
		fi
		log "WARNING: $candidate exists but does not run (broken toolchain" \
			"shim? On macOS try: codesign --force --sign - $candidate)"
	done

	# Last resort: toolchain manager shims can fail outside a directory tree
	# with a manifest (aftman.toml/rokit.toml) or die outright with a stale
	# code signature — the real binaries in tool storage still work. Newest
	# first by mtime. ponytail: mtime ordering, not semver; fine for a fallback.
	for candidate in $(ls -t \
		"$HOME/.rokit/tool-storage/JohnnyMorganz/luau-lsp/"*/luau-lsp \
		"$HOME/.aftman/tool-storage/JohnnyMorganz/luau-lsp/"*/luau-lsp \
		2>/dev/null); do
		if works "$candidate"; then
			log "WARNING: using $candidate directly (no working shim found)"
			echo "$candidate"
			return 0
		fi
	done

	return 1
}

LUAU_LSP_BIN="$(resolve_bin)" || {
	log "ERROR: no working luau-lsp found (checked CLAUDE_LUAU_LSP_BIN, PATH," \
		"~/.rokit/bin, ~/.aftman/bin, ~/.foreman/bin)."
	log "Install it: https://github.com/JohnnyMorganz/luau-lsp (e.g." \
		"'rokit add JohnnyMorganz/luau-lsp' or 'aftman add JohnnyMorganz/luau-lsp')"
	exit 1
}

# ── File age in seconds (GNU + BSD stat) ─────────────────────────────────
file_age() {
	local mtime
	if stat -f %m "$1" >/dev/null 2>&1; then
		mtime=$(stat -f %m "$1") # BSD/macOS
	else
		mtime=$(stat -c %Y "$1") # GNU/Linux
	fi
	echo $(($(date +%s) - mtime))
}

# ── Download definitions atomically; non-fatal on failure ────────────────
download_defs() {
	local dest="$1" tmp
	tmp="$(mktemp "${dest}.XXXXXX")" || return 1

	if curl -sfL --max-time 15 "$GLOBAL_TYPES_URL" -o "$tmp" && [ -s "$tmp" ]; then
		mv "$tmp" "$dest"
		return 0
	fi

	rm -f "$tmp"
	return 1
}

# ── Detect a Roblox workspace ────────────────────────────────────────────
is_roblox_workspace() {
	[ -f globalTypes.d.luau ] && return 0
	[ -f wally.toml ] && return 0
	# Any Rojo project file (default.project.json, place.project.json, ...)
	local f
	for f in *.project.json; do
		[ -e "$f" ] && return 0
	done
	return 1
}

if ! is_roblox_workspace; then
	log "plain Luau workspace — starting bare luau-lsp"
	exec "$LUAU_LSP_BIN" lsp "$@"
fi

# ── Roblox mode: pick definitions ────────────────────────────────────────
if [ -f globalTypes.d.luau ]; then
	# The project ships its own definitions — use them as-is, never modify.
	DEFS="globalTypes.d.luau"
	log "Roblox workspace — using project globalTypes.d.luau"
else
	mkdir -p "$CACHE_DIR"

	if [ ! -s "$CACHE_DEFS" ]; then
		log "downloading Roblox API definitions to cache..."
		if ! download_defs "$CACHE_DEFS"; then
			log "WARNING: could not download Roblox definitions and no cached" \
				"copy exists — starting WITHOUT Roblox globals. Check network" \
				"access to raw.githubusercontent.com."
			exec "$LUAU_LSP_BIN" lsp "$@"
		fi
	elif [ "$(file_age "$CACHE_DEFS")" -gt "$MAX_AGE_SECONDS" ]; then
		log "cached Roblox definitions are >24h old — refreshing..."
		download_defs "$CACHE_DEFS" \
			|| log "WARNING: refresh failed, using stale cached definitions"
	fi

	DEFS="$CACHE_DEFS"
	log "Roblox workspace — using cached definitions ($CACHE_DEFS)"
fi

# Note: --no-strict-dm-types is an `analyze`-only flag; `lsp` rejects it.
exec "$LUAU_LSP_BIN" lsp \
	--definitions="$DEFS" \
	"$@"
