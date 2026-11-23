# Runners

Where an entry runs and what gets written for it. The prompt always lives in
`.factory/automations/<entry>.md`, copied from the entry's `Prompt` with placeholders filled.
Paths in prompts are relative to the run's view: `repo/`, `input/`, `skills/<name>/`.

## Analyze command

Every runner uses the isolated command in [`safety.md`](safety.md#steps). Before offering a
runner, check its Claude Code has the flags (`claude --help` lists `--restricted`, `--safe-mode`,
`--no-session-persistence`). Managed policy (settings files and drop-ins, OS or server policy,
managed plugins) survives `--safe-mode` and has several sources, so it is a precondition the
user confirms: no managed hooks or managed plugins apply to the runner's identity. Unconfirmed
means analyze is unavailable there. A GitHub-hosted runner has no managed policy. Record both
in the profile's runner line.

## Local: systemd user timer or cron

Copy [`../assets/run.sh`](../assets/run.sh) to `.factory/automations/<entry>.sh`, fill `<base>`
with the default branch, `skills` with the skill dirs the prompt loads (a project skill as its
repo-relative path, so it is read from the tracked snapshot; an installed one as its absolute
resolved dir) and the step functions from the entry, `chmod +x`. `repo/` and fetch's `git` reads use the local `<base>`
branch, as fresh as the user's last pull; the prompt states its SHA.
Then propose one of these, with absolute paths:

```ini
# ~/.config/systemd/user/factory-<repo>-<entry>.service
[Unit]
Description=factory <entry> for <repo>

[Service]
Type=oneshot
WorkingDirectory=<repo-root>
ExecStart=<repo-root>/.factory/automations/<entry>.sh
TimeoutStartSec=45min
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

User timers stop at logout unless `loginctl enable-linger "$USER"`; say so, do not run it.

```crontab
PATH=<dirs of claude, gh, git, python3 from command -v>
0 7 * * 1 <repo-root>/.factory/automations/<entry>.sh >> <repo-root>/.factory/automations/<entry>.log 2>&1; echo "exit $?" >> <repo-root>/.factory/automations/<entry>.log
```

Propose `.factory/automations/*.log` for `.gitignore`. Apply crontab changes only after the user
confirms, with `crontab -e` or by editing the output of `crontab -l` and piping it back to
`crontab -`.

## GitHub Actions (report-only)

Copy [`../assets/report.yml`](../assets/report.yml) to `.github/workflows/factory-<entry>.yml`
as a proposed diff: replace `ENTRY` with the entry name and `VERSION` with the installed
`claude --version`, pin each `uses:` to its tag's commit SHA
(`gh api repos/<owner>/<action>/commits/<tag> --jq .sha`, tag kept as a trailing comment), and
fill the view's skills (committed copies only, from `repo/`) and the fetch step from the entry;
the fetch step's `ref=HEAD` is the default-branch checkout. Event values reach the fetch step only
through `env:` (`TARGET`, `github.event.*`), never as `${{ }}` inside `run:`. Keep
`permissions:` to `contents: read` plus only what the fetch step reads (`actions: read` for CI
logs, `pull-requests: read` and `checks: read` for PR state, `issues: read`). Never grant a write
scope in v1. The prompt file and every skill it loads must be committed: a hosted runner sees only
the checkout. Print the secret setup step (`gh secret set ANTHROPIC_API_KEY`, run by the user)
without touching the value.

The template triggers on `workflow_dispatch` only. Its automatic trigger (`schedule`, `push`,
`workflow_run`) is a second proposed diff, applied after the smoke run passes.

## Smoke run

Run the entry once as the runner, in dry-run mode, before its automatic trigger is enabled:

- systemd: install the units and `systemctl --user daemon-reload`, then
  `systemctl --user set-environment FACTORY_DRY_RUN=1; systemctl --user start factory-<repo>-<entry>.service; systemctl --user unset-environment FACTORY_DRY_RUN`
  and read `journalctl --user -u factory-<repo>-<entry>.service -n 50`. Only after a pass:
  `systemctl --user enable --now factory-<repo>-<entry>.timer`.
- cron: install a one-off line two minutes ahead, the real line with `FACTORY_DRY_RUN=1` before
  the script path. Wait for its `exit <n>` line in `<entry>.log`; pass needs `exit 0`. Then
  replace it with the real line.
- GitHub Actions: with the dispatch-only workflow on the default branch,
  `gh workflow run factory-<entry>.yml [-f target=<a representative run ID or SHA range>]`. It
  prints the created run's URL; `gh run watch <id from that URL> --exit-status`, then read the
  job summary. No URL printed (older `gh`) means the smoke is not attested; upgrade `gh`.

Pass means: the run exited 0, a report from this run landed where the entry says, and for entries
with a post step, `post_check` read the fixed destination with the runner's identity.
