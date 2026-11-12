# Agents

Canonical execution profiles shared across all AI tools. Each file is a Markdown document with YAML frontmatter that controls how the agent is configured per tool.

Agents are for named, isolated execution with model selection, tool policy, or
platform-specific routing. Reusable procedures belong in `skills/`: keep the
body thin and point it at the skill (see `security.md`).

## File Format

```markdown
---
description: "One-line purpose"
model: opus | sonnet | haiku
temperature: 0.0–1.0
tools:
  read: true
  write: false
  edit: false
  bash: false
  search: true
tags: [core, read-only]

opencode:
  mode: subagent
  rate_limit_per_hour: 20
claude:
  mapping: rule | skill | skip
codex:
  mapping: instruction | skip
cursor:
  mapping: skip
---

[Full agent prompt — shared across all tools]
```

### Fields

| Field            | Values                    | Description                                                   |
| ---------------- | ------------------------- | ------------------------------------------------------------- |
| `model`          | `opus`, `sonnet`, `fable` | Claude alias; other hosts resolve the latest ID at dispatch   |
| `temperature`    | `0.0–1.0`                 | Lower = more deterministic. Use `0.0` for migrations/security |
| `tools.*`        | `true/false`              | Which tools this agent may use                                |
| `skills`         | skill names               | Skills preloaded into the agent (Claude Code `skills:`)       |
| `claude.mapping` | `rule`, `skill`, `skip`   | How the agent appears in Claude Code                          |
| `codex.mapping`  | `instruction`, `skip`     | How the agent appears in Codex                                |

Codex role profiles omit `model` so the caller can pass the family's latest
ID, resolved as in `model-dispatch`. Omitting the field alone inherits
configured defaults or the parent; the orchestrator must pass the selected ID.

## How It's Used

The build system reads these files and generates:

- **OpenCode** → agent blocks in `opencode.json` + copied to `generated/opencode/agents/`
- **Claude Code** → orchestration table in `generated/claude/rules/common/agents.md`
- **Codex** → embedded as instruction sections in `generated/codex/config.toml`
- **Cursor** → `generated/cursor/agents/*.mdc` (subagents only; the main thread gets procedures from skills)
