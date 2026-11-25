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
- Scripts: dev `<cmd>`, build `<cmd>`, test `<cmd>`, lint `<cmd>`, typecheck `<cmd>` (<file>), each
  runnable from the repo root; app or package <name at path / the repo root>
- Services: <db, queue, cache> (<source>)
- CI: <workflow files>; jobs <names>; triggers <events>
- Dependent repos: <name>: <why needed> (<source>)
- Agent config: <AGENTS.md, skills, MCP servers found>
- Agent setup: <plan step, phase splitting, independent review, CI round cap, dependency rule>:
  <present (<file>) / unknown (<skill>) / missing>
- Stage skill candidates: <triage / reproduce / fix / verify / review>: <skill dir> (<name or
  description match>) ... / none
- Feature workflow: <skill or step> → ... (<sources>) / missing: <step>
- Detected SDKs: <tool> (<file>)
- Open gaps: <unknown or contradiction> (<sources>)

## Integrations
Updated: <YYYY-MM-DD> (interview)

| Tool | Purpose | Reached via | Status |
| ---- | ------- | ----------- | ------ |
| <GitHub> | <issues, PRs> | <`gh` logged in> | <available / unavailable: reason> |

- Fetch <tool>: prefix `<prefix>`; <`gh` | mcp `<server>` tools `<tool>`, ... | cli `<command>`>;
  query <project, labels, states, lookback>; id `<field>`; extras <fields>;
  trust <trusted | label `<name>` (`gh` only) | none (default)>; confirmed <date>
- Write <tool>: prefix `<prefix>`; <ticket | comment | status | post>: <cli `<command>` | mcp
  `<server>` tool `<tool>` body `<argument / none>` item `<argument / none>` args `<fixed JSON>`>;
  destination <team, channel, state, or the item>; confirmed <date>

## Interview
Updated: <YYYY-MM-DD> (interview)

- Issue sources: <answer>
- Results and escalations: <destination>
- Deploy targets: <environments; agent access>
- Budgets: <per run: <minutes> min, <turns> turns; pipeline run <minutes> min, <n> items; per week
  <USD / none>>
- Agent PR review: <who; PRs allowed or not; drafts only or ready ones too>
- Environment: <isolated | not isolated>
- Risk paths: <glob> ... / none
- Resolved gaps and contradictions: <gap>: <decision>

## Run
Updated: <YYYY-MM-DD> (run) at <short SHA>

- Prerequisites: <tools, versions, dependent repo paths and SHAs>
- Isolation: <data dir, DB, ports, test accounts>
- Start, in order: `<cmd>` ...
- Ready when: <check and what it proved>
- Teardown: `<cmd>` ...
- Timings: cold start <s>, ready <s>
- Test recipe: `<install or bootstrap cmd> && <test cmd>` from the repo root of a fresh checkout;
  needs <env var names, services / nothing>; <ran in step 3 / as CI job <name> runs it / not run>
  / unavailable: <reason>
- Known gaps: <list or none>

## Verification
Updated: <YYYY-MM-DD> (verification)

- Skill: `verify-<app>` at `.cursor/skills/verify-<app>/`
- Harness discovery: Claude Code <confirmed / unconfirmed / copy>, Codex <...>, Cursor <...>
- Features mapped: <list>
- Feature paths <feature>: <glob> ... (one line per mapped feature; <feature> its feature file's
  name, letters, digits, `.`, `_`, `-` only)
- Proof run: <feature>, evidence at <path>

## Agent analytics
Updated: <YYYY-MM-DD> (analytics)

- Period: <all local history / since date>; report `.factory/reports/<date>-agents.md`
- Sessions: <harness> <n or not found>, ... (every harness the report lists)
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
  reason; managed policy confirmed none <yes/no>>
- <entry>: <runner>, schedule <cron-like value>; models default <cli:model[@effort]>[, <stage>
  <cli:model[@effort]> ...]; extra skills <dirs / none>; trigger <schedule / changes / workflow: <what starts it>>
  (`security-review`, `maintain-verification`); level <report / comment / draft-pr / pr>; files <paths>; smoke
  run <YYYY-MM-DD> <pass / fail: error>; status <active / proposed / failed: reason>; for
  `issue-pipeline` at draft-pr: flow <fix / repro-only>, verify_fixed <on / off>, reviewers
  <cli:model[@effort] ...>, merge_level <draft / ready / merge>, needs_human <test-change dependency refactor>
- <entry> stage <triage / reproduce / fix / verify / review>: <skill dir>; confirmed <YYYY-MM-DD>;
  smoke run <YYYY-MM-DD> <pass / fail: error>. No line: the built-in stage.
```
