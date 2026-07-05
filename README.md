# agents

Global [ULIS](https://github.com/nejcm/ulis) configuration source for AI coding assistants.

This repo is a single source of truth that generates native config for:

- [Claude Code](https://claude.ai/code)
- [OpenCode](https://opencode.ai)
- [Codex](https://github.com/openai/codex)
- [Cursor](https://cursor.com)
- [ForgeCode](https://forgecode.dev/docs/)

## What is ULIS?

ULIS (Unified LLM Interface Specification) is a CLI that lets you write agent configuration once and publish it to multiple AI tools. See the [`nejcm/ulis`](https://github.com/nejcm/ulis) repo for full documentation.

## Repo layout

The tree mirrors a global `~/.ulis/` source directory:

| Path | Purpose |
| ---- | ------- |
| [`config.yaml`](./config.yaml) | Project identity and version |
| [`mcp.yaml`](./mcp.yaml) | MCP server definitions |
| [`permissions.yaml`](./permissions.yaml) | Per-platform read/write/bash rules |
| [`skills.yaml`](./skills.yaml) | External skill installs |
| [`plugins.yaml`](./plugins.yaml) | Plugin installs |
| [`commands.yaml`](./commands.yaml) | One-shot setup commands |
| [`agents/`](./agents/) | Agent definitions (Markdown with YAML frontmatter) |
| [`skills/`](./skills/) | Reusable OpenCode skills (`SKILL.md`) |
| [`commands/`](./commands/) | OpenCode slash commands |
| [`rules/`](./rules/) | Shared coding rules |
| [`presets/`](./presets/) | Stack-specific skill presets (`react-web`, `react-native`, `web-growth-audit`) |
| [`raw/`](./raw/) | Platform-native fragments copied verbatim into generated output |
| [`hooks/`](./hooks/) | Lifecycle event hooks |
| [`tools/`](./tools/) | Build-time helper scripts |

## Quick start

Install the ULIS CLI:

```bash
bun add -g @nejcm/ulis
# or
npm i -g @nejcm/ulis
```

Build configs without installing:

```bash
ulis build --source .
```

Generated output lands in [`generated/`](./generated/) (gitignored).

Install to global tool directories:

```bash
ulis install --global --source . --yes
```

This deploys to `~/.claude/`, `~/.codex/`, `~/.cursor/`, `~/.config/opencode/`, and `~/.forge/`.

## Adding configuration

- **Agents**: add a Markdown file under [`agents/`](./agents/) with YAML frontmatter.
- **Skills**: create a directory under [`skills/`](./skills/) with a `SKILL.md`.
- **Slash commands**: add a Markdown file under [`commands/`](./commands/).
- **Rules**: add Markdown files under [`rules/`](./rules/) or a language-specific folder.
- **Raw platform overrides**: place files in [`raw/<platform>/`](./raw/) to copy them verbatim into generated output.

Each directory has its own `README.md` with format details.

## Platform support

| Platform | Generated target | Notes |
| -------- | ---------------- | ----- |
| OpenCode | `generated/opencode/` | Native `opencode.json` + skills/commands |
| Claude Code | `generated/claude/` | Rules, agents, and MCP config |
| Codex | `generated/codex/` | `config.toml` + instructions |
| Cursor | `generated/cursor/` | Rules and MCP allowlists |
| ForgeCode | `generated/forgecode/` | ForgeCode-compatible output |

## Presets

[`presets/`](./presets/) contains stack-specific skill bundles that can be layered on top of this base config:

- `react-web` — React, Next.js, shadcn/ui, frontend design
- `react-native` — React Native, Expo, best practices
- `web-growth-audit` — SEO, quality audit, optimization

Apply a preset at install time:

```bash
ulis install --global --source . --preset react-web --yes
```

## Important notes

- Generated output is ignored by Git. Run `ulis build` to regenerate it.
- Back up existing tool configs before running `ulis install --global`, or use `--backup`.
- This configuration is a living baseline. Review generated files in `generated/` before installing if you have existing customizations.

## Links

- [ULIS CLI repository](https://github.com/nejcm/ulis)
- [ULIS documentation](https://nejcm.github.io/ulis/)
