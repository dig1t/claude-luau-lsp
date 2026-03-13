# claude-luau-lsp

Luau LSP plugin for Claude Code. Provides type checking, go-to-definition, hover info, and other language intelligence for Roblox (`.luau`) files.

## Prerequisites

- [luau-lsp](https://github.com/JohnnyMorganz/luau-lsp) must be installed and in your `$PATH`
- [Rojo](https://github.com/rojo-rbx/rojo) (optional, for sourcemap generation)

Both are typically installed via [Aftman](https://github.com/LPGhatguy/aftman) or [Foreman](https://github.com/Roblox/foreman):

```bash
aftman add JohnnyMorganz/luau-lsp
aftman add rojo-rbx/rojo
```

## Installation

```bash
claude plugin marketplace add dig1t/claude-luau-lsp
claude plugin install luau-lsp@claude-luau-lsp
```

## What it does

- Starts `luau-lsp` as a language server for `.luau` files
- On session start, downloads Roblox global type definitions (`globalTypes.d.luau`) if missing or stale
- On session start, generates a Rojo sourcemap (`sourcemap.json`) if Rojo is available
