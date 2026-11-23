# Profile format

`.factory/profile.md` in the target repo. One H2 per phase-owned section, each with an `Updated`
date. A phase rewrites only its own section. Every fact names its source; a missing value is
`unavailable: <reason>`. No secrets, ever.

```markdown
# Factory profile: <repo name>

## Repo
Updated: <YYYY-MM-DD> (explore) at <short SHA>

- Purpose: <one line> (README.md)
- Surfaces: <primary>; also <others> (<source>)
- Stack: <languages, frameworks, runtime versions> (<source>)
- Package manager: <name> (<lockfile>)
- Scripts: dev `<cmd>`, build `<cmd>`, test `<cmd>`, lint `<cmd>`, typecheck `<cmd>` (<file>)
- Services: <db, queue, cache> (<source>)
- CI: <workflow files>; jobs <names>; triggers <events>
- Dependent repos: <name>: <why needed> (<source>)
- Agent config: <AGENTS.md, skills, MCP servers found>
- Detected SDKs: <tool> (<file>)
- Open gaps: <unknown or contradiction> (<sources>)

## Integrations
Updated: <YYYY-MM-DD> (interview)

| Tool | Purpose | Reached via | Status |
| ---- | ------- | ----------- | ------ |
| <GitHub> | <issues, PRs> | <`gh` logged in> | <available / unavailable: reason> |

## Interview
Updated: <YYYY-MM-DD> (interview)

- Issue sources: <answer>
- Results and escalations: <destination>
- Deploy targets: <environments; agent access>
- Budgets: <per run, per week; allowed models>
- Agent PR review: <who; PRs allowed or not>
- Resolved gaps and contradictions: <gap>: <decision>

## Run
Updated: <YYYY-MM-DD> (run) at <short SHA>

- Prerequisites: <tools, versions, dependent repo paths and SHAs>
- Isolation: <data dir, DB, ports, test accounts>
- Start, in order: `<cmd>` ...
- Ready when: <check and what it proved>
- Teardown: `<cmd>` ...
- Timings: cold start <s>, ready <s>
- Known gaps: <list or none>

## Verification
Updated: <YYYY-MM-DD> (verification)

- Skill: `verify-<app>` at `.cursor/skills/verify-<app>/`
- Harness discovery: Claude Code <confirmed / unconfirmed / copy>, Codex <...>, Cursor <...>
- Features mapped: <list>
- Proof run: <feature>, evidence at <path>

## Agent analytics
Updated: <YYYY-MM-DD> (analytics)

<baseline summary from agent-analytics>

## Baselines
Updated: <YYYY-MM-DD> (baselines) at <short SHA>

<measured numbers with source; unavailable ones with reason>
```
