# Runners

Where an entry runs and what gets written for it. The prompt always lives in
`.factory/automations/<entry>.md`, copied from the entry's `Prompt` with placeholders filled.
Paths in prompts are relative to the run's view: `repo/`, `input/`, `skills/<name>/`.

Runs are local only and use the runner identity's existing subscription login of each picked CLI
(`claude`, and `codex` or `agy` where picked); no API key or token secret. Tell the user to check their plan's terms for unattended use; these runs
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

## Local: systemd user timer or cron

Copy [`../assets/run.sh`](../assets/run.sh) to `.factory/automations/<entry>.sh`, fill `<base>`
with the default branch, `<level>` with the chosen write level, `<owner/repo>` with
`gh repo view --json nameWithOwner`, `<turns>` and `<minutes>` (script, unit and cron line) with
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
Then propose one of these, with absolute paths:

```ini
# ~/.config/systemd/user/factory-<repo>-<entry>.service
[Unit]
Description=factory <entry> for <repo>

[Service]
Type=oneshot
WorkingDirectory=<repo-root>
ExecStart=<repo-root>/.factory/automations/<entry>.sh
TimeoutStartSec=<minutes>min
Environment=PATH=<tool dirs>:/usr/local/bin:/usr/bin:/bin
SyslogIdentifier=factory-<repo>-<entry>
```

```ini
# ~/.config/systemd/user/factory-<repo>-<entry>.timer
[Unit]
Description=factory <entry> for <repo>

[Timer]
OnCalendar=<schedule>
Persistent=true

[Install]
WantedBy=timers.target
```

`<schedule>`: the entry's schedule ([per-entry settings](../SKILL.md#steps)), as an `OnCalendar`
expression for the timer or the five cron fields for the cron line.

For `issue-pipeline` at `draft-pr`, `<minutes>` in the unit's `TimeoutStartSec` and the cron
`timeout` is the entry's `run_minutes` plus 10; the script keeps the per-stage `<minutes>`.

`<tool dirs>`: the directories of `command -v` for `claude`, `codex` and `agy` when picked, `gh`, `git`, `python3` and the
Run recipe's tools, unresolved (a version-manager wrapper dispatches on its name). systemd and
cron start with a minimal `PATH`, without the login shell's.

User timers stop at logout unless `loginctl enable-linger "$USER"`; say so, do not run it.

```crontab
PATH=<tool dirs>:/usr/local/bin:/usr/bin:/bin
<schedule> timeout <minutes>m <repo-root>/.factory/automations/<entry>.sh >> <repo-root>/.factory/automations/<entry>.log 2>&1; echo "exit $?" >> <repo-root>/.factory/automations/<entry>.log
```

Propose `.factory/automations/*.log` for `.gitignore`. Apply crontab changes only after the user
confirms, with `crontab -e` or by editing the output of `crontab -l` and piping it back to
`crontab -`.

## Models

Each pick is `<cli>:<model>[@effort]`: `claude:opus@high` runs `claude --model opus --effort
high`; `claude:default` passes no `--model` (the CLI default), and no `@effort` passes no
`--effort`. Efforts: `low`, `medium`, `high`, `xhigh`, `max`. CLIs: `claude`, `codex` and `agy`
(Antigravity, [mapping](#cli-mapping)); any other CLI fails the run before any call. Per entry, a `default` and optional per-stage
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
message (Claude's JSON output, Codex's last message, Antigravity's `response`; Codex's and Antigravity's
event streams are not capped): a longer one is cut there and fails the call (a stage then
records `runner-error`). Minutes are the budget for every CLI; `<turns>` caps Claude calls only, since
Codex and Antigravity have no turn cap.

### CLI mapping

Each stage has a kind: tool-less (spec-writer, the smoke check), read-only (analyze, reviewers),
exec (reproduce, verify) or write (fix, edit). Every stage reads its inputs (`$check`) and writes
its record (`$evidence`) as with Claude.

| Kind | `claude -p` | `codex exec` | `agy` `--settings` | Isolation |
| ---- | ----------- | ------------ | --------------------- | --------- |
| tool-less | `--restricted --safe-mode --tools "" --max-turns 3` | `-s read-only --disable shell_tool` | `agentMode` `""`, `toolPermission` `strict`, deny `read_file(*)` and the read-only row's list | claude `restricted`, codex and agy `weak` |
| read-only | `--restricted --safe-mode --tools Read,Grep,Glob` | `-s read-only` | `agentMode` `""`, `toolPermission` `request-review`, deny `write_file(*)`, `command(*)`, `unsandboxed(*)`, `read_url(*)`, `execute_url(*)`, `mcp(*)` | claude `restricted`, codex and agy `weak` |
| exec, write | `--safe-mode --setting-sources '' --tools <tools>` | `-s workspace-write`, network on, `/tmp` writable as for Claude, `--add-dir $evidence` | `--dangerously-skip-permissions --mode accept-edits`, deny `read_url(*)`, `execute_url(*)`, `mcp(*)`; shell network on | `environment` |

Every `claude` call also gets `--strict-mcp-config --no-session-persistence --permission-mode
dontAsk`; every `codex` call `--json --ephemeral --ignore-user-config --ignore-rules --strict-config
--skip-git-repo-check -c approval_policy="never" -c project_doc_max_bytes=0`, `--disable` for
`apps`, `plugins`, `hooks`, `multi_agent`, `image_generation`, `browser_use`, `computer_use` and
`in_app_browser`, `-m <model>` unless `default`, `-c model_reasoning_effort="<effort>"` for an
`@effort`, and `-o` for its last message. `OPENAI_API_KEY`, `CODEX_API_KEY` and `OPENAI_BASE_URL`
are unset like the Anthropic ones. Every `agy` call gets `--input-format stream-json --output-format
stream-json --disable-slash-commands`, `--model <model>` unless `default` and `--effort <effort>` for an
`@effort` (model IDs that end in an effort, such as `gemini-3.8-flash-low`, also work), and runs under
`timeout <minutes>m` like the others (not the CLI's `--print-timeout`, which exits 3, not 124). The
prompt goes in as one stdin message, so input size has no argument limit; the spec-writer's input
follows it after a line saying the rest is data, never instructions. Its final `result` event gives the
response and usage. `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `GOOGLE_GEMINI_BASE_URL`,
`GOOGLE_APPLICATION_CREDENTIALS`, `GOOGLE_GENAI_USE_VERTEXAI`, `GOOGLE_GENAI_USE_ENTERPRISE`,
`GOOGLE_SERVICE_ACCOUNT_AUTH` and `AGY_ADC_AUTH` are unset too.

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
tools, no secrets; reviewers too. At run time a missing CLI, or `codex login status` or `agy -p
/usage` (answered by the CLI without a model call; 30 seconds) failing, stops
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
- **Only on risky changes** (`trigger="changes"`), from the timer at the entry's schedule: a
  model-free check first. `security-review` reviews only when its range touches the profile's
  `Risk paths` (`risk_paths`); `maintain-verification` calls the model only when a commit since
  its last successful run touched a mapped feature's `Feature paths` (`feature_paths`) or the
  verify skill. Otherwise the run is recorded `skipped` `no-risk-change`, with no model call.
- **Wired into the user's workflow**: `trigger="changes"`, started by something the user already
  runs after the default branch moves (a `post-merge` hook, a task-runner target, a step on a
  self-hosted runner) instead of the timer. Propose the line as a diff with the script's absolute
  path, run in the background with its output to `.factory/automations/<entry>.log`; install
  nothing outside `.factory/` without the user's consent, and never a CI job that needs a model
  API secret. The smoke run runs the script directly as that user with `FACTORY_DRY_RUN=1`.

Fill `trigger`, then `risk_paths` with the `Risk paths` globs (`risk_paths=()` when the trigger is
`schedule`) and `feature_paths` with one `[<feature>]="<glob> ..."` per `Feature paths` line. A glob
matches the whole repo-relative path and `*` crosses `/`: `auth/*` misses `x/auth/z`, so a nested
path needs a leading `*` (`*package.json`). An unfilled or empty glob, or an unknown trigger,
fails the run before any call. A dry run skips the
check and always calls the model, so the smoke run writes its report. `security-review` keeps its
last reviewed SHA in `.factory/reports/security-review/reviewed.sha` (a symlink or non-regular
file stops the run), written by the script only after a successful run or a `no-risk-change` skip.

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

The edit step and the test command run as the runner identity, under its own `claude` login, and
`publish` uses its `gh` login and `git push` credentials. So the edit step can read that login and
change Git config, `PATH` and the run script: only the isolated environment, holding a
fine-grained token scoped to this repo, bounds an injected model
([safety.md](safety.md#lethal-trifecta-rule)).

## Run record

Every run past the pause and Git config checks appends one line to
`.factory/reports/runs.jsonl`, written by the run script, never the model, credential-shaped text
(`sk-ant-`, OpenAI `sk-`, Google `AIza`) replaced with `[redacted]`: `entry`, `started`, `ended` (UTC), `base`,
`start_commit`, `end_commit` (the start commit when nothing was committed), `diff_stat`, `gates`
(`passed` or the gate message, in order), `outcome` (`completed`, `no-change`, `published`,
`escalated`, `blocked`, `failed`, `skipped`), `reason` (the escalation reason, `ci-cap` or `ci-unknown`, `weekly-budget` for a run `skipped` at its weekly budget, `no-risk-change` for one `skipped` by its
[change trigger](#change-triggers),
`usage-limit`, `rate-limit` or `api-error` for a `failed` run whose call reported `is_error` with that cause; else `null`),
`test_changes` (existing test files changed, deleted or renamed) and `dependency_change` (dependencies
disclosed), `scope`, `weighted_lines` and `instruction_change` (a pushed commit changes agent instructions), all `null` unless the gates passed, `exit_code`, `dry_run`, `calls`, `max_turns_hit` (calls that stopped at `--max-turns`), and the summed `turns`, `input_tokens`, `cache_write_tokens`,
`cache_read_tokens`, `output_tokens`, `cost_usd` (the sum of the costs the calls reported, `null` when none did) with
`cost_complete` (`false` when a call reported no cost), and `stages`, one per call in order: `stage`,
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
no cache writes or cost, so `null`); a turn or
token total is `null` when any call did not report it. Agent fetch and write calls are not counted. A dry run records too, with `dry_run: true`: the file is local and smoke runs cost usage.
`agent-analytics` reads it.

## Smoke run

Run the entry once as the runner, in dry-run mode, before its automatic trigger is enabled. First,
with `FACTORY_CHECK_MODELS=1` in place of `FACTORY_DRY_RUN=1` the same way, the script makes one
tool-less check call per picked model (models and reviewers) through its [mapping](#cli-mapping),
prints `check: <pick> answered` or `did not answer`, records the calls and ends; it passes only
when it exits 0, so every picked model answered. Then the dry run:

- systemd: install the units and `systemctl --user daemon-reload`, then
  `systemctl --user set-environment FACTORY_DRY_RUN=1; systemctl --user start factory-<repo>-<entry>.service; systemctl --user unset-environment FACTORY_DRY_RUN`
  and read `journalctl --user -u factory-<repo>-<entry>.service -n 5` for the exit status and
  `journalctl --user -t factory-<repo>-<entry> -n 50` for the script's output (a short-lived
  process's lines can miss the unit tag). Only after a pass:
  `systemctl --user enable --now factory-<repo>-<entry>.timer`.
- cron: install a one-off line two minutes ahead, the real line with `FACTORY_DRY_RUN=1` before
  `timeout`. Wait for its `exit <n>` line in `<entry>.log`; pass needs `exit 0`. Then
  replace it with the real line.

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
