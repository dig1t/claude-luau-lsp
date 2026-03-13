# claude-luau-lsp

Luau LSP plugin for Claude Code. Provides type checking, go-to-definition, hover info, and other language intelligence for `.luau` and `.lua` files.

## Prerequisites

[luau-lsp](https://github.com/JohnnyMorganz/luau-lsp) must be installed and in your `$PATH`.

Typically installed via [Aftman](https://github.com/LPGhatguy/aftman) or [Foreman](https://github.com/Roblox/foreman):

```bash
aftman add JohnnyMorganz/luau-lsp
```

## Installation

```bash
claude plugin marketplace add dig1t/claude-luau-lsp
claude plugin install luau-lsp@claude-luau-lsp
```

## What it does

Starts `luau-lsp` as a language server for `.luau` and `.lua` files, giving Claude Code access to type checking, go-to-definition, hover info, find references, and other LSP features.

## Roblox projects

For Roblox development, you'll want to pass additional args to luau-lsp. Create a project-level plugin by adding `.claude-plugin/plugin.json` to your project:

```json
{
  "name": "my-project-lsp",
  "version": "1.0.0",
  "description": "Luau LSP with Roblox types",
  "lspServers": {
    "luau": {
      "command": "luau-lsp",
      "args": [
        "lsp",
        "--definitions=globalTypes.d.luau",
        "--no-strict-dm-types"
      ],
      "extensionToLanguage": {
        ".luau": "luau",
        ".lua": "luau"
      }
    }
  }
}
```

Then download Roblox type definitions to your project root:

```bash
curl -sL "https://raw.githubusercontent.com/JohnnyMorganz/luau-lsp/main/scripts/globalTypes.d.luau" -o globalTypes.d.luau
```

For Rojo projects, luau-lsp auto-detects `sourcemap.json` in the workspace root. Generate one with:

```bash
rojo sourcemap --include-non-scripts --output sourcemap.json
```

You can automate both by adding a SessionStart hook to your project's `.claude/settings.json`.
