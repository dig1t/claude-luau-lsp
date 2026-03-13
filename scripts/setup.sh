#!/bin/bash
set -euo pipefail

cd "$CLAUDE_PROJECT_DIR"

# Download globalTypes.d.luau if missing or older than 24 hours
TYPES_FILE="globalTypes.d.luau"
NEEDS_DOWNLOAD=false

if [ ! -f "$TYPES_FILE" ]; then
	NEEDS_DOWNLOAD=true
elif [ "$(uname)" = "Darwin" ]; then
	if [ $(($(date +%s) - $(stat -f %m "$TYPES_FILE"))) -gt 86400 ]; then
		NEEDS_DOWNLOAD=true
	fi
else
	if [ $(($(date +%s) - $(stat -c %Y "$TYPES_FILE"))) -gt 86400 ]; then
		NEEDS_DOWNLOAD=true
	fi
fi

if [ "$NEEDS_DOWNLOAD" = true ]; then
	curl -sL "https://raw.githubusercontent.com/JohnnyMorganz/luau-lsp/main/scripts/globalTypes.d.luau" > "$TYPES_FILE"
fi

# Generate sourcemap if rojo is available
if command -v rojo &> /dev/null; then
	if [ ! -f "sourcemap.json" ] || [ "$NEEDS_DOWNLOAD" = true ]; then
		rojo sourcemap --include-non-scripts --output sourcemap.json 2>/dev/null || true
	fi
fi
