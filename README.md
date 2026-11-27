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
| [`extensions.yaml`](./extensions.yaml) | External CLI extension installs |
| [`agents/`](./agents/) | Agent definitions (Markdown with YAML frontmatter) |
| [`skills/`](./skills/) | Reusable skill definitions (`SKILL.md`) |
| [`commands/`](./commands/) | OpenCode slash commands |
| [`presets/`](./presets/) | Skill presets (`react-web`, `react-native`, `web-growth-audit`, `factory`) |
| [`raw/`](./raw/) | Platform-native fragments copied verbatim into generated output |
| [`hooks/`](./hooks/) | Lifecycle event hooks |
| [`tools/`](./tools/) | Build-time helper scripts |
| [`tender/`](./tender/) | [tender](https://github.com/nejcm/agent-workflow) profile: task types and their instructions; not part of ULIS |

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
- **Skills**: create a directory under [`skills/`](./skills/) with a `SKILL.md`; use them for reusable procedures rather than execution policy.
- **Slash commands**: add a Markdown file under [`commands/`](./commands/).
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
- `factory` — prepare a repo for unattended agent work (see [Factory preset](#factory-preset))

Apply a preset at install time:

```bash
ulis install --global --source . --preset react-web --yes
```

## Factory preset

[`presets/factory/`](./presets/factory/) bundles four skills and pstack's verification skills:

- `setup-factory` — explores a repo, interviews only for gaps, runs the app for real, generates a
  verify skill, and writes `.factory/profile.md` in that repo
- `agent-analytics` — agent usage numbers (sessions, tokens, cost, retries) from the factory's
  run records, then local Claude Code, Codex, Cursor and Antigravity transcripts
- `automate-factory` — schedules recurring runs (retros, PR babysitting, triage, digests) from a
  catalog as local oncue jobs, so it needs Linux with a systemd user manager or macOS, `node` (18.3
  or later) or `bun` for oncue to install and manage jobs, bash 4 or later and `python3` 3.11 or
  later (setup-factory checks these first; on macOS: Homebrew, whose installer adds the Command Line
  Tools, then `brew install bash python gh node`, `bun` can replace `node`, plus one model CLI,
  `claude` for agent fetch and write); report-only by default, comments and gated PRs when opted in.
  Local edit steps run as you, so run them in an isolated VM or container holding only a repo-scoped
  token. Each stage runs the model you pick on `claude`, `codex`, `agy` or `agent` (Cursor); a
  non-Claude CLI runs exec and write stages outside an isolated environment, or untrusted input at
  weak isolation, only after a recorded confirmation.
  `failed-ci-triage` and `pr-babysitting` can `watch` instead of running on a schedule: their job
  polls every few minutes with no model call and fires only on a new default-branch failure or a
  settled, actionable PR change, capped per day; a `comment` still goes only to the PR fixed at
  setup.
  `issue-pipeline` at `draft-pr` turns items from trusted sources into verified draft PRs,
  at most 3 per run by default. They stay unmerged unless the entry's `merge_level` is `merge`:
  then a later run squash-merges a PR only after two or more reviewers approve, CI is green on
  the gated commit and nothing needs a human, and opens a draft revert PR if `main`'s CI goes red
  after it. Every run past the pause and Git config checks appends one redacted line to
  `.factory/reports/runs.jsonl`. Changed, deleted or renamed tests and new dependencies are
  disclosed with a reason and force a draft; a run that would guess escalates instead, and a PR
  stops getting pushes after two red CI rounds (see
  [safety.md](./presets/factory/skills/automate-factory/references/safety.md#steps)). Change settings, prompt guidance or flow variants
  by asking setup-factory to "change my factory"; what stays locked is in
  [safety.md](./presets/factory/skills/automate-factory/references/safety.md#what-the-user-can-change)
- `fix-issues` — triages, reproduces, fixes and verifies tracker issues in a staged pipeline;
  writes tickets, comments and status back to GitHub, or to any tracker through a CLI or MCP tool
  recorded at setup

Its skills only run when invoked explicitly.

ULIS resolves preset names only from `~/.ulis/presets/` and its bundled presets, so link this one
once, then install:

```bash
mkdir -p ~/.ulis/presets
ln -s /path/to/this/repo/presets/factory ~/.ulis/presets/factory
ulis install --global --source . --preset factory
```

The verification skills used to live in the root [`skills.yaml`](./skills.yaml). ULIS does not
track external installs, so copies from an earlier install stay until you remove them.

## Important notes

- Generated output is ignored by Git. Run `ulis build` to regenerate it.
- YAML config files reference the published ULIS schemas, so autocomplete works with the global CLI installation.
- Back up existing tool configs before running `ulis install --global`, or use `--backup`.
- This configuration is a living baseline. Review generated files in `generated/` before installing if you have existing customizations.

## Firecrawl web research

The global install includes a lean Firecrawl skill for all targets. Its wrapper
invokes the globally installed CLI, keeps page content in the OS temporary
directory, and only returns search metadata or a local file path to the agent.

Install the CLI, authenticate, then run the normal global install:

```bash
npm install -g firecrawl-cli
firecrawl login
ulis install --global --source . --yes
```

For non-interactive environments, set `FIRECRAWL_API_KEY` instead of using
`firecrawl login`. No Firecrawl MCP server or official all-agent skill install is
required.

## Context7 docs lookup

Library docs come from the `find-docs` skill, which calls the Context7 CLI. No
Context7 MCP server is configured. Run once per machine:

```bash
npx ctx7@latest setup
```

## Links

- [ULIS CLI repository](https://github.com/nejcm/ulis)
- [ULIS documentation](https://nejcm.github.io/ulis/)
