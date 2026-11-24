---
name: automate-factory
description: Use when the user asks to schedule or automate recurring agent work for a repo set up with setup-factory (retros, analytics, PR babysitting, CI, issue and error triage, coverage, security review, digests), or to add, change or re-check a factory automation
category: workflow
disable-model-invocation: true
---

# Automate factory

Turn a repo's factory profile into scheduled agent runs. Suggest catalog entries that fit, let the
user pick, place each pick on a runner, and activate it only after a smoke run as that runner.
Run from the target repo's root.

Needs `.factory/profile.md` from `setup-factory`. Without it, say so and stop.

## Steps

1. **Read** the profile. Detect runners, facts only, and record them in the profile's
   `Automations` section ([`../setup-factory/references/profile.md`](../setup-factory/references/profile.md)):
   - systemd timer: `systemctl --user is-system-running` prints `running` or `degraded`.
   - cron: `command -v crontab`.
   - Isolated analyze for local runners: Claude Code with the flags and no managed hooks, per
     [`references/runners.md`](references/runners.md#analyze-command).
2. **Suggest**: read each file in [`references/catalog/`](references/catalog/). For every entry
   whose requirements the profile meets, give one line: the entry and the profile fact that makes
   it worth running ("4 open PRs with review bots", "CI failed 9 of 40 runs on main"). List the
   rest once with the missing piece.
3. **Pick**: the user picks by number. Ask nothing else in this round.
4. **Place** each pick: ask where to run it, offering only runners that are both in the entry's
   `Runners` and detected in step 1. Then ask its write level, `report` as the default, offering
   only the entry's `Write levels` that the runner and profile allow
   ([`references/runners.md`](references/runners.md#write-levels)), and only the entry's
   `Choices`.
5. **Write** per [`references/runners.md`](references/runners.md): the prompt to
   `.factory/automations/<entry>.md`, the run script to `.factory/automations/<entry>.sh`, and the
   runner config as a proposed diff; for `draft-pr` and `pr`, the entry's `Edit prompt` to
   `.factory/automations/<entry>.edit.md` and the fixed values per [Write
   levels](references/runners.md#write-levels). For `issue-pipeline` at `draft-pr`, instead of the
   edit prompt: its `Spec prompt` to `.factory/automations/issue-pipeline.spec.md`, and
   [`assets/issue-pipeline.sh`](assets/issue-pipeline.sh) inserted into the script after `publish`. Fill each `<skill-path:<name>>` in the script's
   `skills` list with that skill's resolved directory, found by the lookup in
   [`../setup-factory/SKILL.md`](../setup-factory/SKILL.md#loading-other-skills). A skill not
   found makes the entry unavailable on that runner. Also fill `<app>`, `<base>` and the entry's
   choices. For an agent-fetched source, write `<prefix>.fetch.md` and, for MCP,
   `<prefix>.mcp.json` per `fix-issues`
   [agent fetch](../fix-issues/references/triage.md#agent-fetch); show the MCP file for
   confirmation, since it names the commands the server runs.
   For a `comment` post to a destination other than GitHub, the source's `Write` line's
   `<prefix>.post.sh`, or its MCP write tool, per
   [write back](../fix-issues/references/triage.md#write-back).
6. **Smoke run as the runner** (activation gate): its checkout, identity and tools, in dry-run
   mode, per [`references/runners.md`](references/runners.md#smoke-run). On failure, report the
   exact error, leave the entry `proposed`, and fix nothing silently. `issue-pipeline` at
   `draft-pr` needs one item through reproduce; with none pending, ask the user to file a canary.
7. **Record** each entry in the profile's `Automations` section: runner, trigger, files, smoke
   run date and result, write level, status (`active`, `proposed`, `failed: <reason>`).

On a re-run, read the `Automations` section first, re-check detected runners, and offer changes
only to entries the user names or whose smoke run failed.

## Scope

- Written and activated: one local runner (systemd user timer or cron), under the user's
  `claude` subscription login.
- Write levels: `report`, the default; `comment`; `draft-pr` and `pr`, per
  [`references/safety.md`](references/safety.md#steps).
- Later, not offered: harness schedulers (Claude routines, Cursor Automations) and external
  services, which do not run the fetch and view steps these prompts depend on.
- Not offered: GitHub-hosted runners, which need a Claude token as a repo secret.

## Rules

- **Safety**: every automation follows [`references/safety.md`](references/safety.md), including
  the lethal-trifecta rule. An entry that cannot meet it on a runner is not offered there. A
  `draft-pr` or `pr` edit step runs as the user; only the isolated environment bounds it.
- **Writes**: freely only to `.factory/`. A run writes elsewhere only through its write level's
  post or publish step. Runner config (systemd units, crontab lines) is shown as a proposed
  diff and applied only after the user confirms.
- **Secrets**: never ask for, read, store or write one. Name a secret by its variable or setting
  name only ("`LINEAR_API_KEY` env var") and print the steps for the user to set it.
- **Budgets**: every run gets the profile's per-run caps, default 30 minutes and 50 turns when
  unset: `--max-turns` (print mode; absent from `--help` but accepted and validated), and the
  minutes as `TimeoutStartSec` (systemd) or `timeout` (cron). `issue-pipeline` at `draft-pr` also
  has a run cap, `run_minutes` (default 240): no item starts without time for its stages, and the
  unit or cron timeout is `run_minutes` plus 10.
- **Pause**: `.factory/pause` in the target repo makes every run exit 0 before any work, and
  stops `issue-pipeline` before its next item; delete it to resume.
- **Loading skills**: the run script copies the skills a prompt needs into the run's view, and
  the prompt reads `skills/<name>/SKILL.md` by path, never by invocation;
  `disable-model-invocation` blocks that.
