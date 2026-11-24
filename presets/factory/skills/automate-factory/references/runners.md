# Runners

Where an entry runs and what gets written for it. The prompt always lives in
`.factory/automations/<entry>.md`, copied from the entry's `Prompt` with placeholders filled.
Paths in prompts are relative to the run's view: `repo/`, `input/`, `skills/<name>/`.

Model auth is subscription first: local runners use the runner identity's existing `claude`
login; hosted runs use `CLAUDE_CODE_OAUTH_TOKEN`. Tell the user to check their plan's terms for
unattended use; these runs draw on the plan's usage limits.

## Analyze command

Every runner uses the isolated command in [`safety.md`](safety.md#steps). Before offering a
runner, check its Claude Code has the flags (`claude --help` lists `--restricted`, `--safe-mode`,
`--no-session-persistence`). Managed policy (settings files and drop-ins, OS or server policy,
managed plugins) survives `--safe-mode` and has several sources, so it is a precondition the
user confirms: no managed hooks or managed plugins apply to the runner's identity, and, for
agent fetch, no managed permission allow rules for MCP tools and no managed auth setting
(`apiKeyHelper`, provider or token env). Unconfirmed means analyze, or agent fetch, is
unavailable there. A GitHub-hosted runner has no managed policy. Record both
in the profile's runner line.

## Local: systemd user timer or cron

Copy [`../assets/run.sh`](../assets/run.sh) to `.factory/automations/<entry>.sh`, fill `<base>`
with the default branch, `<auth>` with `subscription` or `api-key`, `<level>` with the chosen write
level, `<owner/repo>` with `gh repo view --json nameWithOwner`, `<turns>`, `<minutes>` (script
and unit) and, on API-key auth, `<usd>` with the profile's per-run caps (see
[Budgets](../SKILL.md#rules)), `skills` with the skill dirs the prompt loads (a project skill as
its repo-relative path, so it is read from the tracked snapshot; an installed one as its absolute
resolved dir) and the step functions from the entry, `chmod +x`. `repo/` and fetch's `git` reads
use the local `<base>` branch, as fresh as the user's last pull; the prompt states its SHA.
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

`<tool dirs>`: the directories of `command -v` for `claude`, `gh`, `git`, `python3` and the
Run recipe's tools, unresolved (a version-manager wrapper dispatches on its name). systemd and
cron start with a minimal `PATH`, without the login shell's.

User timers stop at logout unless `loginctl enable-linger "$USER"`; say so, do not run it.

```crontab
PATH=<tool dirs>:/usr/local/bin:/usr/bin:/bin
0 7 * * 1 <repo-root>/.factory/automations/<entry>.sh >> <repo-root>/.factory/automations/<entry>.log 2>&1; echo "exit $?" >> <repo-root>/.factory/automations/<entry>.log
```

Propose `.factory/automations/*.log` for `.gitignore`. Apply crontab changes only after the user
confirms, with `crontab -e` or by editing the output of `crontab -l` and piping it back to
`crontab -`.

## Write levels

`report` needs nothing more. `comment` fills `post` and `post_check` from the entry, with the
destination approved by the user. `draft-pr` and `pr` are local only and need: Linux with `bwrap`
and unprivileged user namespaces, `fix-issues` installed (the script sources its
[`jail.sh`](../../fix-issues/assets/jail.sh)), the profile's `Agent PR review` allowing agent
PRs (`pr` also allowing non-draft ones), and a test script in the profile. Fill in the run script:

- `remote` (the remote whose push URL is `repo`), `branch` left as `factory/$entry` except for
  `pr-babysitting`.
- `test_cmd`: the profile's test script, self-contained (installs its own dependencies), run in
  the jail with no secret; `allow`: the entry's path globs, confirmed by the user; `max_lines`.
- `jail_tools`: `jail_resolve claude <the Run recipe's tools>` lines the user confirms, as in
  `fix-issues` [Dispatch](../../fix-issues/SKILL.md#dispatch).
- `<skill-path:fix-issues>` with its resolved directory.
- The entry's `Edit prompt` to `.factory/automations/<entry>.edit.md`.

The jail passes no file from `HOME`, so the edit step needs the model token in the runner's
environment: the user runs `claude setup-token` and writes `CLAUDE_CODE_OAUTH_TOKEN=<token>`
(or `ANTHROPIC_API_KEY` on API-key auth) to a file outside the repo, mode `0600`, e.g.
`~/.config/factory/env`. systemd: `EnvironmentFile=%h/.config/factory/env` in `[Service]`;
cron: `set -a; . ~/.config/factory/env; set +a;` before the script path. Never read or write it.
`publish` uses the runner identity's own `gh` login and `git push` credentials, outside the jail.

## GitHub Actions (report and comment)

Copy [`../assets/report.yml`](../assets/report.yml) to `.github/workflows/factory-<entry>.yml`
as a proposed diff: replace `ENTRY` with the entry name, `VERSION` with the installed
`claude --version`, `MINUTES` and `TURNS` with the profile's per-run caps, pin each `uses:` to
its tag's commit SHA
(`gh api repos/<owner>/<action>/commits/<tag> --jq .sha`, tag kept as a trailing comment), and
fill the view's skills (committed copies only, from `repo/`) and the fetch step from the entry;
the fetch step's `ref=HEAD` is the default-branch checkout. Event values reach the fetch step only
through `env:` (`TARGET`, `github.event.*`), never as `${{ }}` inside `run:`. Keep
`permissions:` to `contents: read` plus only what the fetch step reads (`actions: read` for CI
logs, `pull-requests: read` and `checks: read` for PR state, `issues: read`). Never grant the report
job a write scope. The prompt file and every skill it loads must be committed: a hosted runner
sees only the checkout. Print the secret setup steps, run by the user, without touching the value:
`claude setup-token` (subscription), then `gh secret set CLAUDE_CODE_OAUTH_TOKEN`. An API key
is the alternative: `gh secret set ANTHROPIC_API_KEY`, that name in the analyze step's `env:`
instead of the OAuth one, and `--max-budget-usd`.

For `comment`, keep the template's `publish` job and fill `NUMBER` with the destination issue
or PR the user approves; its `issues: write` (`pull-requests: write` and `gh pr comment` for a
PR) is the workflow's only write scope. For `report`, delete the job.

The template triggers on `workflow_dispatch` only. Its automatic trigger (`schedule`, `push`,
`workflow_run`) is a second proposed diff, applied after the smoke run passes.

## Smoke run

Run the entry once as the runner, in dry-run mode, before its automatic trigger is enabled:

- systemd: install the units and `systemctl --user daemon-reload`, then
  `systemctl --user set-environment FACTORY_DRY_RUN=1; systemctl --user start factory-<repo>-<entry>.service; systemctl --user unset-environment FACTORY_DRY_RUN`
  and read `journalctl --user -u factory-<repo>-<entry>.service -n 5` for the exit status and
  `journalctl --user -t factory-<repo>-<entry> -n 50` for the script's output (a short-lived
  process's lines can miss the unit tag). Only after a pass:
  `systemctl --user enable --now factory-<repo>-<entry>.timer`.
- cron: install a one-off line two minutes ahead, the real line with `FACTORY_DRY_RUN=1` before
  the script path. Wait for its `exit <n>` line in `<entry>.log`; pass needs `exit 0`. Then
  replace it with the real line.
- GitHub Actions: with the dispatch-only workflow on the default branch,
  `gh workflow run factory-<entry>.yml -f dry-run=true [-f target=<a representative run ID or SHA range>]`. It
  prints the created run's URL; `gh run watch <id from that URL> --exit-status`, then read the
  job summary. No URL printed (older `gh`) means the smoke is not attested; upgrade `gh`.

Pass means: the run exited 0, a report from this run landed where the entry says, for entries
with a post step, `post_check` read the fixed destination with the runner's identity, and for
`draft-pr` and `pr`, the edit and gates ran (the log shows `edit: no change` or no `gate:` line)
and the PR lookup read the destination. A gate failure exits 1 and publishes nothing.
