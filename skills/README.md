# Skills

Reusable, invocable capabilities that agents can call during a session. Each
skill lives in its own subdirectory with a `SKILL.md` and optional `config/`,
`references/`, `scripts/`, or `assets/` directories.

Skills contain procedures and output contracts. `agent-orchestration` owns
shared model selection and review routing; `model-dispatch` owns invocation
mechanics and the current ID registry in `references/models.md`. Keep role capabilities and tool permissions in `agents/`. Platform
model pins are host defaults; orchestration must select a supported mechanism
that satisfies the workload tier and reviewer family.

## Structure

```
skills/
  <skill-name>/
    SKILL.md          # Skill definition and instructions
    config/           # Tool configs used by the skill (optional)
    references/       # Reference documents the skill uses (optional)
```

## How It's Used

The build system copies `skills/` directly into `generated/[PLATFORM]/skills/`
at the repo root. No transformation is applied, so keep each `SKILL.md`
self-contained and avoid platform-specific assumptions unless documented.

## Adding a New Skill

1. Create `.ulis/global/skills/<name>/SKILL.md` with the skill instructions
2. Add a `config/` directory if the skill uses tool-specific configuration files
3. Add a `references/` directory for any reference documents the skill reads
4. Run `bun run build` from the repo root — the skill will be included automatically
5. Invoke it in OpenCode with the skill name
