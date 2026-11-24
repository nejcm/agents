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
agent fetch, no managed permission allow rules for MCP tools and no managed auth setting
(`apiKeyHelper`, provider or token env). Unconfirmed means analyze, or agent fetch, is
unavailable there. Record both in the profile's runner line.

## Local: systemd user timer or cron

Copy [`../assets/run.sh`](../assets/run.sh) to `.factory/automations/<entry>.sh`, fill `<base>`
with the default branch, `<level>` with the chosen write level, `<owner/repo>` with
`gh repo view --json nameWithOwner`, `<turns>` and `<minutes>` (script, unit and cron line) with
the profile's per-run caps (see [Budgets](../SKILL.md#rules)), `skills` with the skill dirs the
prompt loads (a project skill as its repo-relative path, so it is read from the tracked snapshot;
an installed one as its absolute resolved dir) and the step functions from the entry, `chmod +x`.
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

## Write levels

`report` needs nothing more. `comment` fills `post` and `post_check` from the entry, with the
destination approved by the user. `draft-pr` and `pr` need the profile's
`Agent PR review` allowing agent PRs (`pr` also allowing non-draft ones) and a test script in the
profile, and Git 2.31 or later (the run script sets config through `GIT_CONFIG_COUNT`). Fill in
the run script:

- `<remote url>`: `git remote get-url --push <name>` of the remote whose push URL is `repo`, so
  fetch and push use that URL, not a name Git config can repoint; `branch` left as `factory/$entry` except for
  `pr-babysitting`.
- `test_cmd`: the profile's test script, self-contained (installs its own dependencies), run in
  the checkout; `allow`: the entry's path globs, confirmed by the user; `max_lines`.
- The entry's `Edit prompt` to `.factory/automations/<entry>.edit.md`.

The edit step and the test command run as the runner identity, under its own `claude` login, and
`publish` uses its `gh` login and `git push` credentials. So the edit step can read that login and
change Git config, `PATH` and the run script: only the isolated environment, holding a
fine-grained token scoped to this repo, bounds an injected model
([safety.md](safety.md#lethal-trifecta-rule)).

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
with a post step, `post_check` read the fixed destination with the runner's identity, and for
`draft-pr` and `pr`, the edit and gates ran (the log shows `edit: no change` or no `gate:` line)
and the PR lookup read the destination. A gate failure exits 1 and publishes nothing.
