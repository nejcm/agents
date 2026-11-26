# Runners

Where an entry runs and what gets written for it. The prompt always lives in
`.factory/automations/<entry>.md`, copied from the entry's `Prompt` with placeholders filled.
Paths in prompts are relative to the run's view: `repo/`, `input/`, `skills/<name>/`.

Runs are local only and use the runner identity's existing subscription login of each picked CLI
(`claude`, and `codex`, `agy` or `agent` where picked); no API key or token secret. Tell the user to check their plan's terms for unattended use; these runs
draw on the plan's usage limits. A self-hosted GitHub Actions runner on the user's own machine is
possible but not provided.

## Analyze command

Every runner uses the isolated command in [`safety.md`](safety.md#steps). Before offering a
runner, check its Claude Code has the flags (`claude --help` lists `--restricted`, `--safe-mode`,
`--no-session-persistence`). Managed policy (settings files and drop-ins, OS or server policy,
managed plugins) survives `--safe-mode` and has several sources, so it is a precondition the
user confirms: no managed hooks or managed plugins apply to the runner's identity, and, for
agent fetch and agent write, no managed permission allow rules for MCP tools and no managed auth
setting (`apiKeyHelper`, provider or token env). Unconfirmed means analyze, or agent fetch and
write, is
unavailable there. Record both in the profile's runner line.

## Local: oncue job

Copy [`../assets/run.sh`](../assets/run.sh) to `.factory/automations/<entry>.sh`, fill `<base>`
with the default branch, `<level>` with the chosen write level, `<owner/repo>` with
`gh repo view --json nameWithOwner`, `<turns>` and `<minutes>` (script and job spec) with
the profile's per-run caps (see [Budgets](../SKILL.md#rules)), `<weekly usd>` with its per-week
budget in USD (empty for none), `models` with the entry's [model picks](#models), `skills` with the
skill dirs the prompt loads plus the entry's extra skills (a project skill as its repo-relative
path, so it is read from the tracked snapshot; an installed one as its absolute resolved dir; no
two with the same directory name), and the step functions from the entry, `chmod +x`. Each extra
skill also gets one line at the end of the entry's prompt and edit prompt: `Also follow
skills/<name>/SKILL.md where it applies.` For `issue-pipeline` at `draft-pr`, its directory name
also goes into `extra_skills`, and the script adds that line to each reproduce, fix and verify
stage and reviewer prompt, with the skill copied into the stage's inputs (the tool-less
spec-writer reads no skills). A [stage skill](#stage-skills) goes into `skills` the same way.
These values come from the profile and the entry's choices; the profile is the source of truth,
so a changed value regenerates the entry ([re-run](../SKILL.md#re-run)).
`repo/` and fetch's `git` reads use the local `<base>` branch, as fresh as the user's last pull;
the prompt states its SHA.
Then write the job spec to `.factory/automations/<entry>.job.json`, with absolute paths, and
propose it as a diff:

```json
{
  "namespace": "factory-<repo>",
  "name": "<entry>",
  "description": "factory <entry> for <repo>",
  "command": ["<bash>", "<repo-root>/.factory/automations/<entry>.sh"],
  "cwd": "<repo-root>",
  "log": "<repo-root>/.factory/automations/<entry>.log",
  "schedule": <schedule>,
  "timeout": <minutes>
}
```

On macOS, oncue's launchd backend refuses `timeout`, so the spec omits it: model calls and test
runs keep their own `timeout`, but nothing bounds the whole run.

`<bash>`: the absolute path of the bash 4 or later found in [step 1](../SKILL.md#steps), as found, not
resolved (Homebrew's link survives `brew upgrade`), so the job does not depend on which `bash` its `PATH`
finds first.

`<oncue>` is `node <skill dir>/assets/oncue.mjs` (Node 18.3 or later) or the same with `bun`, `<skill
dir>` this skill's resolved directory; run without arguments it prints its usage. Never read the
bundle. `<oncue> render <spec>` prints the scheduler files a spec makes, changing nothing. Node or bun is
needed only to install and manage jobs: the scheduled job runs `[<bash>, script]`, not `<oncue>`.

`<repo>`: `<name>-<hash>`, so two checkouts get different namespaces. `<name>` is the repo
root's directory name, lowercased, each run of characters other than `a-z` and `0-9` replaced by
`-`, cut to 16 characters, leading and trailing `-` removed (empty: `<repo>` is `<hash>` alone);
`<hash>` the first 6 characters of `git rev-parse --show-toplevel | tr -d '\n' | sha256sum` (`shasum -a 256` where
`sha256sum` is missing, as on older macOS). A
namespace holds 31 characters.

`<schedule>`: the entry's schedule ([per-entry settings](../SKILL.md#steps)) as an oncue schedule,
local time: `{"kind": "interval", "minutes": <n>}`, or `{"kind": "calendar", "at": [...]}` with one
`{"weekday", "hour", "minute"}` or `{"day", "hour", "minute"}` entry per slot (`weekday` `mon` to
`sun`; omitted `weekday` and `day` mean every day, omitted `hour` every hour). "Daily, 08:00 on
weekdays" is five entries, `mon` to `fri` at `hour` 8, `minute` 0; "hourly on weekdays, 09:00 to
18:00" one entry per weekday and hour. A schedule neither can express gets the nearest one, shown to
the user. A [watch](#watch-trigger) entry: `{"kind": "interval", "minutes": <interval>}`.
On launchd, an interval that divides 60 fires on the clock (minutes 0, n, 2n and so on of each hour), so
the first fire can come sooner than n minutes after install; any other interval counts from install.

`<minutes>` in the spec's `timeout` is the per-run minutes; for
`issue-pipeline` at `draft-pr`, the entry's `run_minutes` plus 10, while the script keeps the per-stage `<minutes>`. oncue accepts 1 to
10080.

After the user confirms, the [smoke run](#smoke-run) installs it, and after a pass:
`<oncue> install .factory/automations/<entry>.job.json --capture-path <tools>`, `<tools>`
comma-separated: `claude`, `codex`, `agy` and `agent` when picked, `gh`, `git`, `python3`, the Run
recipe's tools, and after them every tool above whose `command -v` is in `/usr/bin` or `/bin`.
The job sees no login-shell `PATH`; `--capture-path` sets one from each tool's `PATH` directory in that order, unresolved (a
version-manager wrapper dispatches on its name), then `/usr/local/bin:/usr/bin:/bin`, so a system
directory listed early would shadow a newer `python3` or a version manager's copy. It prints
`installed`, or `unchanged` when the job already matches. Remove an entry with `<oncue> uninstall
factory-<repo> <entry>` (`removed`, or `not installed`).

A [workflow-wired](#change-triggers) entry gets no job spec and no oncue job: its line in the user's
workflow is its runner, removed (after the user confirms) when the entry is removed or moves to a
schedule; moving to the workflow uninstalls its job.

On Linux, user jobs stop at logout unless `loginctl enable-linger "$USER"`; say so, do not run it.
On macOS, a launchd agent runs only while the user is logged in.

Propose `.factory/automations/*.log` for `.gitignore`.

## Models

Each pick is `<cli>:<model>[@effort]`: `claude:opus@high` runs `claude --model opus --effort
high`; `claude:default` passes no `--model` (the CLI default), and no `@effort` passes no
`--effort`. Efforts: `low`, `medium`, `high`, `xhigh`, `max`. CLIs: `claude`, `codex`, `agy`
(Antigravity) and `agent` (Cursor, [mapping](#cli-mapping)); any other CLI fails the run before any call. Cursor
has no effort flag: its model IDs carry the effort (`agent:gpt-5.6-sol-high`), and an `agent` pick with
`@effort` fails the run. Per entry, a `default` and optional per-stage
overrides fill `declare -A models=([default]=<pick> [<stage>]=<pick> ...)`; a stage without its own
runs `default`. Stages: `analyze` and, at `draft-pr` and `pr`, `edit`; `issue-pipeline` at
`draft-pr` adds `spec`, `reproduce`, `fix`, `verify`, and `review` as its `reviewers=(...)` list,
in place of `edit`. Agent fetch and write are Claude only: they run `default` when it is a `claude`
pick, else the `claude` CLI default. The picks are the allowed set: `run_model`
builds every call from them and refuses a model not picked for its stage, an unknown stage or an
invalid pick fails the run before any call, and a pending merge's recorded verdicts must match the
current `reviewers`. `weekly-agent-analytics` has no model.
Every counted call (analyze, edit, spec, each stage, each reviewer) runs under its timeout
(`<minutes>`; 5 for the tool-less spec-writer) and keeps at most `8 * summary_cap` bytes of its final
message (Claude's JSON output, Codex's last message, Antigravity's `response`, Cursor's `result`; the
Codex and Antigravity event streams and Cursor's JSON are not capped): a longer one is cut there and fails the call (a stage then
records `runner-error`). Minutes are the budget for every CLI; `<turns>` caps Claude calls only, since
Codex, Antigravity and Cursor have no turn cap.

### CLI mapping

Each stage has a kind: tool-less (spec-writer, the smoke check), read-only (analyze, reviewers),
exec (reproduce, verify) or write (fix, edit). Every stage reads its inputs (`$check`) and writes
its record (`$evidence`) as with Claude.

| Kind | `claude -p` | `codex exec` | `agy` `--settings` | `agent -p` | Isolation |
| ---- | ----------- | ------------ | --------------------- | ---------- | --------- |
| tool-less | `--restricted --safe-mode --tools "" --max-turns 3` | `-s read-only --disable shell_tool` | `agentMode` `""`, `toolPermission` `strict`, deny `read_file(*)` and the read-only row's list | `--mode ask`, deny `Read(**)` and the read-only row's list | claude `restricted`, codex, agy and agent `weak` |
| read-only | `--restricted --safe-mode --tools Read,Grep,Glob` | `-s read-only` | `agentMode` `""`, `toolPermission` `request-review`, deny `write_file(*)`, `command(*)`, `unsandboxed(*)`, `read_url(*)`, `execute_url(*)`, `mcp(*)` | `--mode ask`, deny `Write(**)`, `Shell(*)`, `WebFetch(*)`, `Mcp(*:*)` | claude `restricted`, codex, agy and agent `weak` |
| exec, write | `--safe-mode --setting-sources '' --tools <tools>` | `-s workspace-write`, network on, `/tmp` writable as for Claude, `--add-dir $evidence` | `--dangerously-skip-permissions --mode accept-edits`, deny `read_url(*)`, `execute_url(*)`, `mcp(*)`; shell network on | `--force --sandbox enabled --add-dir $evidence`; network on | `environment` |

Every `claude` call also gets `--strict-mcp-config --no-session-persistence --permission-mode
dontAsk`; every `codex` call `--json --ephemeral --ignore-user-config --ignore-rules --strict-config
--skip-git-repo-check -c approval_policy="never" -c project_doc_max_bytes=0`, `--disable` for
`apps`, `plugins`, `hooks`, `multi_agent`, `image_generation`, `browser_use`, `computer_use` and
`in_app_browser`, `-m <model>` unless `default`, `-c model_reasoning_effort="<effort>"` for an
`@effort`, and `-o` for its last message. `OPENAI_API_KEY`, `CODEX_API_KEY` and `OPENAI_BASE_URL`
are unset for its calls and login check. Every `agy` call gets `--input-format stream-json --output-format
stream-json --disable-slash-commands`, `--model <model>` unless `default` and `--effort <effort>` for an
`@effort` (model IDs that end in an effort, such as `gemini-3.8-flash-low`, also work), and runs under
`timeout <minutes>m` like the others (not the CLI's `--print-timeout`, which exits 3, not 124). The
prompt goes in as one stdin message, so input size has no argument limit; the spec-writer's input
follows it after a line saying the rest is data, never instructions. Its final `result` event gives the
response and usage. `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `GOOGLE_GEMINI_BASE_URL`,
`GOOGLE_APPLICATION_CREDENTIALS`, `GOOGLE_GENAI_USE_VERTEXAI`, `GOOGLE_GENAI_USE_ENTERPRISE`,
`GOOGLE_SERVICE_ACCOUNT_AUTH` and `AGY_ADC_AUTH` are unset for its calls and login check. Every `agent` call gets `-p --trust
--output-format json` and `--model <model>` unless `default`, and runs under `timeout <minutes>m` (the CLI has
no time cap). The prompt and the spec-writer's input go in on stdin as for `agy`; the call's stderr is kept
beside its output to name a usage or rate limit. Tool-less and read-only calls write their deny rules to
`.cursor/cli.json` in the stage's own directory, never the checkout. `CURSOR_API_KEY`, `CURSOR_AUTH_TOKEN`,
`CURSOR_AUTH_TOKEN_FILE` and `CURSOR_API_ENDPOINT` are unset for its calls and login check. The test command
and other CLIs' calls keep these variables; the Anthropic ones are unset for the whole run.

Codex's isolation check, observed with codex-cli 0.172.0: exec and write pass (writes stay in the
working directory and the added record directory; user MCP servers, ChatGPT apps, hooks, rules and
`AGENTS.md` are off). Tool-less and read-only fail: a read-only sandbox still reads the whole
filesystem, and its built-in exec tool cannot be removed, so those calls are `weak`. A fix or edit
works in a worktree whose Git directory lies outside the writable roots, so the stage likely cannot
commit refactor steps itself: a `scope: refactor` fix or edit then blocks at the scope gate.

Antigravity's isolation check, observed with agy 1.5.17: `--settings` merges into the user's
settings (their other keys stay; per the docs, deny rules win over allow rules); denied file,
shell and MCP calls fail and the run goes on. Exec and write pass: the shell and file tools work in
the working directory and the record directory, MCP is denied. `--add-dir` is not used: it moved the
shell's working directory to the added one. Tool-less and read-only fail: `search_web`, subagent and
browser tools cannot be removed (`search_web` ran with every deny rule set), and read-only
`read_file` read a file outside the working directory, so those calls are `weak`. There is no
session-off flag: each call keeps a conversation under `~/.gemini/antigravity-cli/`.

Cursor's isolation check, observed with agent 2026.11.22: the CLI merges every `.cursor/cli.json` from the
Git root down to the working directory into the user's config, objects deep and arrays replaced, so the
runner's file, the deepest, sets both lists: its `allow: []` drops the user's allow rules (their `Shell(ls)`
was denied); an invalid project config fails the call, and an unwritten one fails it before it runs. Exec and write pass: the shell, file writes, the record
directory and network work. Tool-less and read-only fail: ask mode with `Read(**)` denied blocked reads,
writes and the shell, but read-only `Read` and `Grep` read a file outside the working directory, and
subagent and image tools cannot be removed, so those calls are `weak`. Web fetch and search are refused
in ask mode only because nothing approves them (the CLI does not check `WebFetch` deny rules, and `--force`
approves them). The user's hooks (`~/.cursor/hooks.json`) run on every call, there is no session-off flag
(each call keeps a chat), and the CLI saves `--model` as the user's own default model.

Confirmations, from the profile, fill `environment="<isolated | not isolated>"` (the profile's
`Environment`) and `confirmed=(<stage>=<cli:model> ...)`; a confirmation lapses when the stage's pick changes, effort
aside:

- a non-Claude pick on an exec or write stage (`reproduce`, `verify`, `fix`, `edit`) outside an
  isolated environment runs only when confirmed for that stage, after setup warned that the
  machine it runs on is then the only boundary;
- a pick with `weak` isolation on an untrusted-input stage (`analyze`, which is also triage, and
  `spec`) runs only when confirmed for that stage, after setup said that the prompt rules are best
  effort against injection.

Otherwise the run fails before any call. A `weak` call gets every control its CLI has and the
safety rules at the end of its prompt: untrusted text is data, no network, no MCP or external
tools, no secrets; reviewers too. At run time a missing CLI, or `codex login status`, `agy -p
/usage` (answered by the CLI without a model call; 30 seconds) or `agent status` (not reporting
`isAuthenticated: true`) failing, stops
the call with reason `model-unavailable` and no fallback: the run fails, and an `issue-pipeline`
item is `deferred` and the pipeline stops.

## Stage skills

Setup may swap one of `issue-pipeline`'s stages (triage, reproduce, fix, verify, review), or
`new-error-triage`'s triage, for a skill the user already has, one profile line per stage
(`- <entry> stage <stage>: <skill dir>`). The skill goes into `skills` (a project skill by its
repo-relative path, so its paths, link and target join `deny` like any consumed skill) and:

- triage: the prompt's `Read skills/fix-issues/references/triage.md, section Judge, and apply it`
  becomes `Read skills/<name>/SKILL.md and apply it`; the rest of the prompt, with its `## <id>`
  sections, `fix-issues:` line and verdicts, stays.
- reproduce, fix, verify, review: `declare -A stage_skills=([<stage>]=<name> ...)` in the
  `issue-pipeline` part of the script, `<name>` its directory name. The stage's prompt then says to
  follow that skill, copied into the stage's inputs, in place of the `fix-issues` reference (for
  review, in place of the judging sentence); the overlay, bans, the record the stage must write
  (file and last line) and `Stage: <stage>.` follow as for the built-in stage.

The record contract, every gate, write and checker, and the run script itself are never
replaced: a record without its last line ends the item `blocked` as before. A name not in
`skills`, or a key other than those four stages, fails the run before any call. Only `fix` edits;
a replaced reproduce, verify or review keeps its tools.

## Change triggers

`security-review` and `maintain-verification` take a per-entry `trigger`, asked with the other
per-entry settings:

- **On a schedule** (`trigger="schedule"`): every run calls the model, as before.
- **Only on risky changes** (`trigger="changes"`), from the oncue job at the entry's schedule: a
  model-free check first. `security-review` reviews only when its range touches the profile's
  `Risk paths` (`risk_paths`); `maintain-verification` calls the model only when a commit since
  its last successful run touched a mapped feature's `Feature paths` (`feature_paths`) or the
  verify skill. Otherwise the run is recorded `skipped` `no-risk-change`, with no model call.
- **Wired into the user's workflow**: `trigger="changes"`, started by something the user already
  runs after the default branch moves (a `post-merge` hook, a task-runner target, a step on a
  self-hosted runner) instead of an oncue job. Propose the line as a diff with the script's absolute
  path, run in the background with its output to `.factory/automations/<entry>.log`; install
  nothing outside `.factory/` without the user's consent, and never a CI job that needs a model
  API secret. Its [smoke run](#smoke-run) runs the script directly, with no oncue job.

Fill `trigger`, then `risk_paths` with the `Risk paths` globs (`risk_paths=()` when the trigger is
`schedule`) and `feature_paths` with one `[<feature>]="<glob> ..."` per `Feature paths` line. A glob
matches the whole repo-relative path and `*` crosses `/`: `auth/*` misses `x/auth/z`, so a nested
path needs a leading `*` (`*package.json`). An unfilled or empty glob, or an unknown trigger,
fails the run before any call. A dry run skips the
check and always calls the model, so the smoke run writes its report. `security-review` keeps its
last reviewed SHA in `.factory/reports/security-review/reviewed.sha` (a symlink or non-regular
file stops the run), written by the script only after a successful run or a `no-risk-change` skip.
`failed-ci-triage` and `pr-babysitting` take a [watch trigger](#watch-trigger) instead.

## Watch trigger

An entry whose catalog step defines `detect` may take `trigger="watch"`: its oncue job runs every
`interval` minutes (default 2) and a model-free `detect` exits at once when nothing is new. Watch
changes when an entry runs, never what it may write: the write level, destinations, gates,
credential check, size cap, pause, claims, draft default, `weekly_usd` and the loop cap
([safety.md](safety.md#steps)) still apply. `watch` on an entry without `detect` fails the run
before any call. Fill the run script's watch line, before the weekly budget check, and put the
entry's `detect` after it:

```bash
trigger="watch" daily_cap=<daily cap> window="<window>" notify=(<notify command>)
```

- `daily_cap`: fires per local day (default 6), counted from `runs.jsonl` records with `trigger`
  `watch`, `dry_run` false and `events`. At the cap the first capped tick appends `daily fire cap
  reached: <n>` to the day's report; later ticks that day are silent.
- `window`: optional, local time, `<days> HH:MM-HH:MM`, end excluded; days `daily`, `mon` to `sun`,
  ranges like `mon-fri` (`fri-mon` wraps), comma-separated; a window that ends at or before its
  start (overnight) fails the run. Outside it a tick is silent.
- `notify`: optional command; after the record it runs with `<entry>: <fire> <outcome>` as its
  last argument, under 60 seconds, its non-zero exit logged and ignored; never in a dry run.

A tick: pause, then a lock (`.factory/tmp/<entry>.lock`, a file holding the owner PID, read and
written only under `flock`; held by a live PID the tick exits 0 silently, an owner gone is taken
over with one log line; cleared in the `EXIT` trap), the window, then
`detect`, all before the weekly budget check, snapshot or any model call. `detect` runs in a
subshell with `set -e` and prints one line per new event, `<fire> <key> [<value>]` (letters,
digits, `.`, `_`, `-`; `value` defaults to `-`): `<fire>` names the fire and its report, `<key>`
the event in the seen ledger. The first fire with an unsettled event fires, with all of its
events; the rest wait for a later tick. Nothing new: exit 0, no record, log line or report. A
non-zero `detect` records one `failed` run with reason `detect-error`, unless one was recorded in
the last hour (then silent); a weekly-budget skip of a watch fire is recorded at most hourly too.

The seen ledger, `.factory/reports/<entry>/seen.tsv` (a symlink or non-regular file stops the
run), is append-only: `<key>\t<state>\t<value>\t<started>`, the latest line per key wins. A fire
appends `failed` for its events after the weekly budget check, and `done` in the `EXIT` trap only
when the run exited 0, so a crash or kill counts as an attempt. An event whose key is `done` or
`given-up` at the same value is skipped; a new value fires again. After three `failed` lines at one
value the next tick appends `given-up` and the report line `given-up: <key> after 3 failed
attempts`. `detect` may itself call `seen <key> done [<value>]` for an event it settles without a
fire. The ledger is kept when the trigger changes or the entry is removed.

Each fire writes its own report, `.factory/reports/<entry>/<date>-<fire>.md`; analyze, `edit`
and the `comment` level's body check read only that fire's report (`$report_md`). The run record
adds `trigger` and `events` (the fire's keys). `FACTORY_CHECK_MODELS=1` takes the lock and skips
`detect`; `FACTORY_DRY_RUN=1` runs `detect` but ignores the window, cap and ledger and writes no
ledger line, and with no event logs `no event to analyze` and exits 0. In both a held lock fails
the run loudly instead of exiting 0.

## Prompt overlays

`.factory/automations/<entry>.<name>.local.md` belongs to the user; generation never writes it.
The run script appends it to one prompt, after the default and before the record format the
script adds, so it adds guidance only: record formats, checkers and gates still apply, and its
text reaches no command, path or destination.

| Name | Prompt it extends |
| ---- | ----------------- |
| `judge` | analyze, `<entry>.md`; at `comment` this also shapes the posted report |
| `edit` | the `draft-pr` and `pr` edit step, `<entry>.edit.md` |
| `spec` | `issue-pipeline` spec-writer, `issue-pipeline.spec.md` |
| `reproduce`, `fix`, `verify` | `issue-pipeline` stages of that name, verify mode included |
| `review` | `issue-pipeline` shadow reviewers |

No `body` overlay: PR, ticket and link bodies are assembled model-free from the stage records;
steer their wording through `edit`, `reproduce`, `fix` or `verify`.

## Write levels

`report` needs nothing more. `comment` fills `post` and `post_check` from the entry, with the
destination approved by the user: GitHub through `gh`, or a source's `Write` line per `fix-issues`
[write back](../../fix-issues/references/triage.md#write-back) (an MCP write needs
`skills=("<skill-path:fix-issues>")`). `draft-pr` and `pr` need the profile's
`Agent PR review` allowing agent PRs (`pr` also allowing non-draft ones; an edit that changes
existing tests still makes the PR a draft, per [safety.md](safety.md#steps)) and a `Test recipe` in the
profile's `Run` section (`unavailable` or missing: offer `report` and `comment` only, and say `setup-factory`'s run phase records it), and Git 2.31 or later (the run script sets config through `GIT_CONFIG_COUNT`). Fill in
the run script:

- `<remote url>`: `git remote get-url --push <name>` of the remote whose push URL is `repo`, so
  fetch and push use that URL, not a name Git config can repoint; `branch` left as `factory/$entry` except for
  `pr-babysitting`.
- `test_cmd`: the profile's `Test recipe`, self-contained (installs its own dependencies), run in
  a fresh worktree of the checkout, never the bare `test` script; `allow`: the entry's path globs, confirmed by the user; `ceiling` (default 10000);
  `dep_files=1` only for entries that fix source code (`failed-ci-triage`, `pr-babysitting`,
  `issue-pipeline`), so their edits may add a disclosed dependency through manifests and lockfiles
  outside `allow` ([safety.md](safety.md#steps)); every other entry keeps `0`.
- The entry's `Edit prompt` to `.factory/automations/<entry>.edit.md`.

The edit step and the test command run as the runner identity, the edit under the picked CLI's login, and
`publish` uses its `gh` login and `git push` credentials. So the edit step can read that login and
change Git config, `PATH` and the run script: only the isolated environment, holding a
fine-grained token scoped to this repo, bounds an injected model
([safety.md](safety.md#lethal-trifecta-rule)).

## Run record

Every run past the pause and Git config checks, except a silent [watch](#watch-trigger) tick,
appends one line to
`.factory/reports/runs.jsonl`, written by the run script, never the model, credential-shaped text
(`sk-ant-`, OpenAI `sk-`, Google `AIza`) replaced with `[redacted]`: `entry`, `started`, `ended` (UTC), `base`,
`start_commit`, `end_commit` (the start commit when nothing was committed), `diff_stat`, `gates`
(`passed` or the gate message, in order), `outcome` (`completed`, `no-change`, `published`,
`escalated`, `blocked`, `failed`, `skipped`), `reason` (the escalation reason, `ci-cap` or `ci-unknown`, `weekly-budget` for a run `skipped` at its weekly budget, `no-risk-change` for one `skipped` by its
[change trigger](#change-triggers), `model-unavailable` for a `failed` run whose picked CLI was missing or logged out,
`usage-limit`, `rate-limit` or `api-error` for a `failed` run whose call reported `is_error` with that cause, `detect-error` for a [watch](#watch-trigger) tick whose `detect` failed; else `null`),
`test_changes` (existing test files changed, deleted or renamed) and `dependency_change` (dependencies
disclosed), `scope`, `weighted_lines` and `instruction_change` (a pushed commit changes agent instructions), all `null` unless the gates passed, `exit_code`, `dry_run`, `calls`, `max_turns_hit` (calls that stopped at `--max-turns`), and the summed `turns`, `input_tokens`, `cache_write_tokens`,
`cache_read_tokens`, `output_tokens`, `cost_usd` (the sum of the costs the calls reported, `null` when none did) with
`cost_complete` (`false` when a call reported no cost), `trigger` (the entry's, else `null`), `events` (a
[watch](#watch-trigger) fire's event keys, else `null`), and `stages`, one per call in order: `stage`,
`cli`, `model` (`default` for the CLI default), `family` (from the model name, the CLI's name for `default`: `claude`, `opus`,
`sonnet`, `haiku`, `fable` are `anthropic`, `gpt` and `o<digit>` `openai`, `gemini` `google`, else
`unknown`), `effort`, `isolation` (`restricted`: confined to its directory, no shell;
`environment`: a shell, bounded by the environment; `weak`: reads beyond its directory, see
[CLI mapping](#cli-mapping)), `exit`, `turns`, the four token counts and `cost_usd`, each `null`
when not reported. `issue-pipeline` adds
`items` (`id`, `outcome`, `reason`, `pr`, `start_commit`, `end_commit` (the fix, or the merged
commit verified), `diff_stat` (fixes only), `test_changes`, `dependency_change`, `scope`, `weighted_lines`, `instruction_change`, `reviews`
(`model`, the reviewer's pick, its `cli` and `family`, `verdict`, `valid`: false when the output had no verdict line)); a revert
opened after a red factory merge adds item `revert-<id>`, outcome `escalated`, reason `main-red`. Usage comes from `claude -p --output-format json`
(`num_turns`, `total_cost_usd`, `usage`) for analyze, edit, the spec-writer, the `fix-issues` stages and reviewers, and from
Codex's `turn.completed` events (`input_tokens` less `cached_input_tokens`, `cached_input_tokens` as cache reads,
`cache_write_input_tokens`, `output_tokens`; no turns or cost, so `null`, and the run's `cost_complete` is `false`), and
from Antigravity's final `result` event (`num_turns`, `usage.input_tokens`, `usage.cache_read_tokens`, `usage.output_tokens`;
no cache writes or cost, so `null`), and from Cursor's JSON (`usage.inputTokens`, `cacheReadTokens`,
`cacheWriteTokens`, `outputTokens`; no turns or cost, so `null`); a turn or
token total is `null` when any call did not report it. Agent fetch and write calls are not counted. A dry run records too, with `dry_run: true`: the file is local and smoke runs cost usage.
`agent-analytics` reads it.

## Smoke run

Run the entry once as the runner before the real job is installed, in two steps, each with one
variable set: `FACTORY_CHECK_MODELS=1`, then `FACTORY_DRY_RUN=1` (below). A scheduled entry runs
them through oncue: each step installs a copy of the [job
spec](#local-oncue-job) with the variable added to its `env` and `schedule` set to `{"kind":
"manual"}`, on stdin (`<oncue> install - --capture-path <tools>`). A `manual` job has no timer, so
nothing starts it but `run`, and installing it over an entry's live job pauses that schedule until
the real spec is installed again. The step then runs `<oncue> run factory-<repo> <entry> --wait`,
which waits for that run and exits with its exit code (124, `timed out`, past `timeout`; never on launchd). Exit 2 to 4
with an `oncue:` line on stderr is oncue's own error: report it. On launchd, `--wait` returns at once, with
exit 4 or the previous run's exit code, so there `run` goes without `--wait` (it prints `started`), and
`launchctl print gui/$(id -u)/factory-<repo>.<entry>` is polled until `runs` is above its value before
`run` and `state = not running`; `last exit code` is then the run's exit code. The run's output is what it
appended to `<entry>.log`.

First, `FACTORY_CHECK_MODELS=1`: the script makes one tool-less check call per picked model (models
and reviewers) through its [mapping](#cli-mapping), prints `check: <pick> answered` or `did not
answer`, records the calls as a dry run and ends; it passes only when it exits 0, so every picked
model answered. At the weekly budget it fails before any call. Then `FACTORY_DRY_RUN=1`, the dry
run. A [watch](#watch-trigger) entry runs both through the same `manual` copy of its interval job;
its dry run ignores the window, cap and seen ledger, and `detect` hands it the most recent
matching event, so analyze and `post_check` run as for a schedule. With no event in 30 days it
passes on `detect` alone, logs `no event to analyze`, and the entry is recorded `active
(unexercised)`. A tick of the live job holding the lock fails the step: run it again. After both pass, a scheduled entry installs the real spec (`installed`); after a failure, or
when the smoke run is abandoned, `<oncue> uninstall factory-<repo> <entry>`.

A [workflow-wired](#change-triggers) entry installs no oncue job: each step runs
`.factory/automations/<entry>.sh` directly as that user, from the repo root, with the variable set;
its exit status and output are the command's own. After both pass,
apply the workflow line; after a failure, apply nothing.

Pass means: the run exited 0, a report from this run landed where the entry says (a dry run
skips the [change trigger](#change-triggers) check), for entries
with a post step, `post_check` read the fixed destination with the runner's identity (or, for a
post-only destination with no `Fetch` line, the log shows `post_check: destination unchecked`),
and for `draft-pr` and `pr`, the edit and gates ran (the log shows `edit: no change` or no `gate:` line)
and the PR lookup read the destination. A gate failure exits 1 and publishes nothing.

`issue-pipeline` at `draft-pr` passes only when the log shows one item's
`<id> repro: outcome=reproduced` or `<id> repro: outcome=not-reproduced` line and no `gate:` line;
`pipeline: no candidates` is not a pass. With no pending item, the user files a canary: a trusted
or labelled issue describing behaviour that works, so the expected line is `not-reproduced`. The
dry run records every selected item as `deferred`, so the first real run processes it. A
[stage skill](#stage-skills) passes only when its stage ran: a triage skill leaves a valid
`fix-issues:` line in the report, a reproduce skill the log's `repro:` line, a fix or verify skill
`<id> verify: outcome=confirmed`, a review skill `<id> review:` lines. Those last three need a
canary that reproduces (a real open bug); without one the entry stays `proposed`, or runs with
the built-in stage if the user drops the swap.
