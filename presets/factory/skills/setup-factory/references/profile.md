# Profile format

`.factory/profile.md` in the target repo. One H2 per phase-owned section (`Automations` belongs to
`automate-factory`), each with an `Updated` date. A phase rewrites only its own section. Every
fact names its source; a missing value is `unavailable: <reason>`. No secrets, ever.

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

- Fetch <tool>: prefix `<prefix>`; <`gh` | mcp `<server>` tools `<tool>`, ... | cli `<command>`>;
  query <project, labels, states, lookback>; id `<field>`; extras <fields>; confirmed <date>

## Interview
Updated: <YYYY-MM-DD> (interview)

- Issue sources: <answer>
- Results and escalations: <destination>
- Deploy targets: <environments; agent access>
- Budgets: <auth: subscription | api-key; per run: <minutes> min, <turns> turns[, $<usd>]; per week; allowed models>
- Agent PR review: <who; PRs allowed or not; drafts only or ready ones too>
- Environment: <isolated | not isolated>
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

- Period: <all local history / since date>; report `.factory/reports/<date>-agents.md`
- Sessions: Claude Code <n>, Codex <n>, Cursor <n or not found>
- Tokens: uncached input <n>, cache write <n>, cache read <n>, output <n>
- Cost: <USD, harness estimate, from n of m sessions / unavailable>
- Failed tool calls: <harness> <n> of its <n> tool calls; retries <n>; escalations <n>
- Sessions per merged PR: <n / unavailable: reason>
- Unavailable: <harness>: <metrics>

## Baselines
Updated: <YYYY-MM-DD> (baselines) at <short SHA>

- CI <workflow> <push to default / pull_request>: median <s>, max <s> over <n> runs, <SHA range>
  (`gh run list`)
- Steps: <job> / <step>: <s> (run <id>, `gh run view --json jobs`)
- Bundle size: <bytes> from artifact `<name>`, run <id> at <SHA> / unavailable: <reason>
- Local build / test: <s> (<warm or cold>) / unavailable: <reason>

## Automations
Updated: <YYYY-MM-DD> (automate-factory)

- Runners: systemd user <yes/no>, cron <yes/no>, isolated analyze <Claude Code version / no:
  reason; managed policy confirmed none <yes/no>>, GitHub Actions <yes/no> (<command or source>)
- <entry>: <runner>, <trigger>; level <report / comment / draft-pr / pr>; files <paths>; smoke
  run <YYYY-MM-DD> <pass / fail: error>; status <active / proposed / failed: reason>
```
