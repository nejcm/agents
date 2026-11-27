# Live test checklist

Run before merging changes to the run scripts, oncue specs or setup checks. Unit tests cover the
logic; this covers the scheduler, the platform tools and real model calls. Past results live in git
history (`mac-test-report*.md`, `linux-live-test-report.md`).

## Rules

- A throwaway GitHub repo only. Seed commits and issues there; never merge, close or delete its PRs.
- Subscription auth only, no API keys. Cap model spend (about $1 is enough); sum `cost_usd` in
  `.factory/reports/runs.jsonl`.
- Don't change tracked files, global agent config, or run `ulis install`. Run `oncue.mjs`, never
  read it. Uninstall every job you install and show `oncue list` empty at the end.
- Nothing posted to GitHub by hand mentions AI or agents.

## Setup

- macOS: Homebrew `bash` and `python` (3.11 or later) as detected by automate-factory step 1. The
  tool shell may have `/bin` first, so run tests with `PATH=/opt/homebrew/bin:$PATH`.
- A scratch clone of the throwaway repo with a hand-written `.factory/profile.md`.
- To prove no GNU `timeout` is needed, set the job spec's `PATH` by hand without `gtimeout`
  (`--capture-path` adds `/opt/homebrew/bin`).

## Steps

1. **Environment.** Record OS version, `bash` and `python3` paths and versions under the login PATH,
   node or bun, `claude`, `gh`, and the head SHA.
2. **Unit tests.** `python3 -m unittest discover -s presets/factory/skills/<skill>/tests` for
   automate-factory, fix-issues and agent-analytics; `bash -n` on `assets/run.sh` and
   `assets/issue-pipeline.sh`.
3. **Compatibility check.** setup-factory's check under the login PATH; with a requirement hidden it
   names it with an install hint.
4. **Smoke steps** (the `runners.md` recipe: plain `run`, poll `runs.jsonl`):
   - success: a dry run records `exit_code 0`;
   - budget: `weekly_usd` below the week's spend records `exit_code 1`, `calls 0`, "weekly budget
     reached";
   - no record: with `.factory/pause` and `minutes` 1 the poll gives up and `<entry>.log` says why.
5. **Secret hiding.** Job `env` with `FAKE_TOKEN`, `DB_URL` and `GUM_LOG_KEY_FOREGROUND`, and a
   `claude` shim that dumps `env`. One `FACTORY_CHECK_MODELS=1` run: the first two are absent and
   gated `env: unset`, the `GUM_` one is kept, `SSH_AUTH_SOCK` is absent.
6. **issue-pipeline at draft-pr.** Seed a one-line bug and its issue; issues with open fix PRs log
   `pr-exists`. The new issue gets a draft PR with gates `passed`, `test_changes 0`,
   `verify: outcome=confirmed`, no deleted test lines, and a Tests section saying the new tests fail
   on base and pass on the fix. Grep `<entry>.log` for sed, date, stat, mktemp, sort, awk and grep
   errors.
7. **Watch double fire.** Two dry fires of a watch entry on the same SHA and day write
   `<date>-<fire>.md` and `<date>-<fire>-2.md`.
8. **SIGTERM.** Stop the job during `claude -p` (`launchctl kill TERM` or `bootout`; `systemctl
   --user stop` on Linux): recorded `failed`, `exit_code 143` (on launchd within its 5-second
   kill), empty lock, no stray processes.
9. **Cleanup.** `oncue list` empty; list the issues, PRs and commits created on the throwaway repo.

## Report

Head SHA, a step table with pass or fail, the commands and output behind each result, bugs with
file:line and a minimal repro, what was not run and why, and total spend.
