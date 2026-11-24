# Runners

Where an entry runs and what gets written for it. The prompt always lives in
`.factory/automations/<entry>.md`, copied from the entry's `Prompt` with placeholders filled.
Paths in prompts are relative to the run's view: `repo/`, `input/`, `skills/<name>/`.

Runs are local only and use the runner identity's existing `claude` subscription login; no API
key or token secret. Tell the user to check their plan's terms for unattended use; these runs
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
the profile's per-run caps (see [Budgets](../SKILL.md#rules)), `skills` with the skill dirs the
prompt loads (a project skill as its repo-relative path, so it is read from the tracked snapshot;
an installed one as its absolute resolved dir) and the step functions from the entry, `chmod +x`.
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
OnCalendar=Mon *-*-* 07:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

For `issue-pipeline` at `draft-pr`, `<minutes>` in the unit's `TimeoutStartSec` and the cron
`timeout` is the entry's `run_minutes` plus 10; the script keeps the per-stage `<minutes>`.

`<tool dirs>`: the directories of `command -v` for `claude`, `gh`, `git`, `python3` and the
Run recipe's tools, unresolved (a version-manager wrapper dispatches on its name). systemd and
cron start with a minimal `PATH`, without the login shell's.

User timers stop at logout unless `loginctl enable-linger "$USER"`; say so, do not run it.

```crontab
PATH=<tool dirs>:/usr/local/bin:/usr/bin:/bin
0 7 * * 1 timeout <minutes>m <repo-root>/.factory/automations/<entry>.sh >> <repo-root>/.factory/automations/<entry>.log 2>&1; echo "exit $?" >> <repo-root>/.factory/automations/<entry>.log
```

Propose `.factory/automations/*.log` for `.gitignore`. Apply crontab changes only after the user
confirms, with `crontab -e` or by editing the output of `crontab -l` and piping it back to
`crontab -`.

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

No `body` overlay: PR, ticket and link bodies are assembled model-free from the stage records;
steer their wording through `edit`, `reproduce`, `fix` or `verify`.

## Write levels

`report` needs nothing more. `comment` fills `post` and `post_check` from the entry, with the
destination approved by the user: GitHub through `gh`, or a source's `Write` line per `fix-issues`
[write back](../../fix-issues/references/triage.md#write-back) (an MCP write needs
`skills=("<skill-path:fix-issues>")`). `draft-pr` and `pr` need the profile's
`Agent PR review` allowing agent PRs (`pr` also allowing non-draft ones; an edit that changes
existing tests still makes the PR a draft, per [safety.md](safety.md#steps)) and a test script in the
profile, and Git 2.31 or later (the run script sets config through `GIT_CONFIG_COUNT`). Fill in
the run script:

- `<remote url>`: `git remote get-url --push <name>` of the remote whose push URL is `repo`, so
  fetch and push use that URL, not a name Git config can repoint; `branch` left as `factory/$entry` except for
  `pr-babysitting`.
- `test_cmd`: the profile's test script, self-contained (installs its own dependencies), run in
  the checkout; `allow`: the entry's path globs, confirmed by the user; `max_lines`;
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
(`sk-ant-`) replaced with `[redacted]`: `entry`, `started`, `ended` (UTC), `base`,
`start_commit`, `end_commit` (the start commit when nothing was committed), `diff_stat`, `gates`
(`passed` or the gate message, in order), `outcome` (`completed`, `no-change`, `published`,
`escalated`, `blocked`, `failed`), `reason` (the escalation reason, `ci-cap` or `ci-unknown`; else `null`),
`test_changes` (existing test files changed, deleted or renamed) and `dependency_change` (dependencies
disclosed), both `null` unless the gates passed, `exit_code`, `dry_run`, `calls`, `max_turns_hit` (calls that stopped at `--max-turns`), and the summed `turns`, `input_tokens`, `cache_write_tokens`,
`cache_read_tokens`, `output_tokens`, `cost_usd`. `issue-pipeline` adds
`items` (`id`, `outcome`, `reason`, `pr`, `start_commit`, `end_commit` (the fix, or the merged
commit verified), `diff_stat` (fixes only), `test_changes`, `dependency_change`). Usage comes from `claude -p --output-format json`
(`num_turns`, `total_cost_usd`, `usage`) for analyze, edit, the spec-writer and the `fix-issues` stages; a total is
`null` when any call did not report it. Agent fetch and write calls are not counted. A dry run records too, with `dry_run: true`: the file is local and smoke runs cost usage.
`agent-analytics` reads it.

## Smoke run

Run the entry once as the runner, in dry-run mode, before its automatic trigger is enabled:

- systemd: install the units and `systemctl --user daemon-reload`, then
  `systemctl --user set-environment FACTORY_DRY_RUN=1; systemctl --user start factory-<repo>-<entry>.service; systemctl --user unset-environment FACTORY_DRY_RUN`
  and read `journalctl --user -u factory-<repo>-<entry>.service -n 5` for the exit status and
  `journalctl --user -t factory-<repo>-<entry> -n 50` for the script's output (a short-lived
  process's lines can miss the unit tag). Only after a pass:
  `systemctl --user enable --now factory-<repo>-<entry>.timer`.
- cron: install a one-off line two minutes ahead, the real line with `FACTORY_DRY_RUN=1` before
  `timeout`. Wait for its `exit <n>` line in `<entry>.log`; pass needs `exit 0`. Then
  replace it with the real line.

Pass means: the run exited 0, a report from this run landed where the entry says, for entries
with a post step, `post_check` read the fixed destination with the runner's identity (or, for a
post-only destination with no `Fetch` line, the log shows `post_check: destination unchecked`),
and for `draft-pr` and `pr`, the edit and gates ran (the log shows `edit: no change` or no `gate:` line)
and the PR lookup read the destination. A gate failure exits 1 and publishes nothing.

`issue-pipeline` at `draft-pr` passes only when the log shows one item's
`<id> repro: outcome=reproduced` or `<id> repro: outcome=not-reproduced` line and no `gate:` line;
`pipeline: no candidates` is not a pass. With no pending item, the user files a canary: a trusted
or labelled issue describing behaviour that works, so the expected line is `not-reproduced`. The
dry run records every selected item as `deferred`, so the first real run processes it.
