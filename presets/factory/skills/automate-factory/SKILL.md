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
   - oncue: Linux, `node` (18.3 or later) or `bun` on `PATH`, and `<oncue> list factory-<repo>`
     exits 0, so systemd answers ([runners.md](references/runners.md#local-oncue-job)).
   - Isolated analyze for local runners: Claude Code with the flags and no managed hooks, per
     [`references/runners.md`](references/runners.md#analyze-command).
   - Other CLIs: `codex`, `agy` and `agent` versions and logins (`codex login status`, `agy -p /usage`,
     `agent status`).
2. **Suggest**: read each file in [`references/catalog/`](references/catalog/). For every entry
   whose requirements the profile meets, give one line: the entry and the profile fact that makes
   it worth running ("4 open PRs with review bots", "CI failed 9 of 40 runs on main"). List the
   rest once with the missing piece.
3. **Pick**: the user picks by number. Ask nothing else in this round.
4. **Place** each pick: ask where to run it, offering only runners that are both in the entry's
   `Runners` and detected in step 1. Then ask its write level, `report` as the default, offering
   only the entry's `Write levels` that the runner and profile allow
   ([`references/runners.md`](references/runners.md#write-levels)), and only the entry's
   `Choices`. Then the per-entry settings, as one table for all picks with suggested defaults,
   where one answer accepts every default and the user names only what to change (budgets stay
   in the profile's `Interview` section):
   - schedule: in words, default the entry's `Trigger`, converted to an oncue
     schedule ([runners.md](references/runners.md#local-oncue-job)) and shown back;
   - models: a `default` pick and optional per-stage picks, `<cli>:<model>[@effort]` with the
     effort inside the pick, default `claude:default`, only the stages the entry and level run
     ([runners.md](references/runners.md#models)); none for `weekly-agent-analytics`. CLIs `claude`,
     `codex`, `agy` (Antigravity) and `agent` (Cursor; effort in the model ID), any stage. For an
     `agent:<model>` pick, tell the user that Cursor saves each run's model as their own default
     model, so `agent:default` then means whatever the last `agent:<model>` run left; for `issue-pipeline` reviewers, recommend one Claude plus one
     other-family pick. When a non-Claude pick is made, say its runs report no cost (the weekly
     budget counts only reported cost) and ask, per affected stage, for the recorded confirmation
     in [CLI mapping](references/runners.md#cli-mapping): an exec or write stage outside an
     isolated `Environment` (warn that the machine is then the only boundary), and analyze or spec
     at `weak` isolation (say the prompt's safety rules are best effort against injection). A
     confirmation covers that stage and pick only, so a changed pick asks again. A declined
     confirmation leaves that pick out, never swapped for another model;
   - extra skills: skill dirs the entry's analyze and edit steps, and `issue-pipeline`'s
     reproduce, fix and verify stages and reviewers, also read (not the tool-less spec-writer),
     default none, each with a directory name no other skill of the entry has;
   - stage skills, `issue-pipeline` and `new-error-triage` only: per stage the entry runs (triage,
     and at `draft-pr` reproduce, fix, verify, review), the built-in (default) or a user skill
     in its place ([runners.md](references/runners.md#stage-skills)). Offer the profile's
     `Stage skill candidates` for that stage; the user confirms each swap, and a confirmed one
     is used only after this entry's smoke run passes with it;
   - trigger, `security-review` and `maintain-verification` only: on a schedule (default), only
     on risky changes, or wired into the user's existing workflow
     ([runners.md](references/runners.md#change-triggers)). For `security-review`, risky
     changes need the profile's confirmed `Risk paths`; without them, offer the schedule only and
     say `setup-factory` records them;
   - trigger, `failed-ci-triage` and `pr-babysitting` only: `watch` (suggested) or the entry's
     schedule ([runners.md](references/runners.md#watch-trigger)). For `watch`: `interval` in
     minutes (default 2, the job's schedule), `daily_cap` fires per local day (default 6),
     `window` (`failed-ci-triage` none, `pr-babysitting` `mon-fri 09:00-18:00`), `notify` (default
     empty; suggest `notify-send factory` when `notify-send` is on `PATH`); `pr-babysitting` also
     `drafts` (`skip` default, or `include`). For `pr-babysitting` at `comment`, say before the
     user picks `watch`: the comment goes only to the PR fixed at setup (`target`), so a fire
     about any other PR writes its local report and posts nothing; to watch many PRs, suggest
     `report` with `notify`.
5. **Write** per [`references/runners.md`](references/runners.md): the prompt to
   `.factory/automations/<entry>.md`, the run script to `.factory/automations/<entry>.sh`, and the
   oncue job spec to `.factory/automations/<entry>.job.json` as a proposed diff (none for a
   workflow-wired entry); for `draft-pr` and `pr`, the entry's `Edit prompt` to
   `.factory/automations/<entry>.edit.md` and the fixed values per [Write
   levels](references/runners.md#write-levels). For `issue-pipeline` at `draft-pr`, instead of the
   edit prompt: its `Spec prompt` to `.factory/automations/issue-pipeline.spec.md`, and
   [`assets/issue-pipeline.sh`](assets/issue-pipeline.sh) inserted into the script after `publish`.
   A stage skill per [runners.md](references/runners.md#stage-skills).
   Never write a `*.local.md` [overlay](references/runners.md#prompt-overlays). Fill each
   `<skill-path:<name>>` in the script's `skills` list with that skill's resolved directory, found by the lookup in
   [`../setup-factory/SKILL.md`](../setup-factory/SKILL.md#loading-other-skills). A skill not
   found makes the entry unavailable on that runner. Also fill `<app>`, `<base>` and the entry's
   choices. For `failed-ci-triage` and `pr-babysitting`, fill their first block's settings at
   either trigger: `<trigger>` (`watch` or `schedule`), `<daily cap>` a number (6 when
   `schedule`), `<window>` (empty for none), `<notify command>` its words (empty for none), and
   `workflows`, or `drafts` (`skip` when `schedule`), `author` (empty for all open) and `target`
   (empty at `report`); a `watch` entry also fills `<remote url>`
   ([runners.md](references/runners.md#write-levels)) at every level. For an agent-fetched source, write `<prefix>.fetch.md` and, for MCP,
   `<prefix>.mcp.json` per `fix-issues`
   [agent fetch](../fix-issues/references/triage.md#agent-fetch); show the MCP file for
   confirmation, since it names the commands the server runs.
   For a `comment` post to a destination other than GitHub, the source's `Write` line's
   `<prefix>.post.sh`, or its MCP write tool, per
   [write back](../fix-issues/references/triage.md#write-back).
6. **Smoke run as the runner** (activation gate): its checkout, identity and tools, one
   tool-less check call per picked model (the entry is enabled only when every one answered), then
   dry-run mode, per [`references/runners.md`](references/runners.md#smoke-run). On failure, report the
   exact error, leave the entry `proposed`, and fix nothing silently. `issue-pipeline` at
   `draft-pr` needs one item through reproduce; with none pending, ask the user to file a canary.
   A stage skill needs its stage in the smoke run ([runners.md](references/runners.md#smoke-run)).
   A `watch` entry's dry run takes the latest matching event, ignoring window, cap and seen
   ledger; with none in 30 days it passes on `detect` alone and is recorded `active (unexercised)`.
7. **Record** each entry in the profile's `Automations` section: runner, schedule, model picks,
   confirmations,
   extra skills, one `stage` line per stage skill, trigger, files, smoke run date and result, write level, `issue-pipeline`'s `flow`,
   `verify_fixed`, `reviewers`,
   `merge_level` and `needs_human`, for `watch` `interval`, `daily_cap`, `window` and `notify`,
   `pr-babysitting`'s `drafts`, status
   (`active`, `active (unexercised)`, `proposed`, `failed: <reason>`).

## Re-run

Read the `Automations` section first, re-check detected runners, and offer changes only to
entries the user names or whose smoke run failed. To change an entry:

1. Regenerate its files (step 5) into a scratch directory from the current profile, never
   writing `*.local.md`: the before copy.
2. Write the change where it lives: a setting (schedule, model picks and their confirmations, extra skills, stage skills, trigger, write level,
   destination, trust, `label`, `interval`, `daily_cap`, `window`, `notify`, `drafts`,
   `run_minutes`, `cap`, `flow`, `verify_fixed`, `ceiling`, `reviewers`,
   `merge_level`, `needs_human`, budgets, `weekly_usd`) to the profile, or guidance to the entry's
   [overlay](references/runners.md#prompt-overlays). Prompts, record formats, gates and the
   deny list are not settings.
3. Regenerate only that entry's files again from the changed profile. A file in
   `.factory/automations/` that differs from the before copy is hand-edited: show that diff and
   settle it with the user (guidance into an overlay, a value into the profile, or drop it).
   Never overwrite it silently.
4. Show the diff of the regenerated files, the job spec included, apply after the user confirms,
   and mark the entry `proposed`. An overlay alone regenerates nothing.
5. Smoke run (step 6) and record (step 7); the entry is `active` again only after a pass (for a
   scheduled entry, the final `install` prints `installed`).

To remove an entry, after the user confirms: `<oncue> uninstall factory-<repo> <entry>`, or for a
workflow-wired entry its workflow line ([runners.md](references/runners.md#local-oncue-job)), and
delete its line from the `Automations` section; its files stay.

## Scope

- Written and activated: one local oncue job (systemd user on Linux; the run script needs bash and
  GNU `timeout`), under the user's subscription login of each picked CLI (`claude`, `codex`, `agy`, `agent`).
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
  post or publish step. The oncue job spec is shown as a proposed diff and installed only after
  the user confirms.
- **Secrets**: never ask for, read, store or write one. Name a secret by its variable or setting
  name only ("`LINEAR_API_KEY` env var") and print the steps for the user to set it.
- **Budgets**: every run gets the profile's per-run caps, default 30 minutes and 200 turns when
  unset; minutes are the budget, turns only stop a looping run: `--max-turns` (print mode; absent from `--help` but accepted and validated), the
  minutes as `timeout` on every model call, and as the job spec's `timeout`. `issue-pipeline` at `draft-pr` also
  has a run cap, `run_minutes` (default 240): no item starts without time for its stages, and the
  job spec's `timeout` is `run_minutes` plus 10; and an item cap, `cap` (default 3).
  Refactor, old-test and new-test runs and a revert's test runs also wait for time left in `run_minutes`. The
  profile's per-week budget is `weekly_usd` (empty: no limit): before any model call, a run sums
  `cost_usd` over every `runs.jsonl` record started in the last 7 days (a missing cost counts as 0
  and is noted, as is a run with a call that reported no cost) and, at or over it, exits 0 with
  one `weekly budget reached` report line and no other write (a `FACTORY_CHECK_MODELS=1` run fails instead); a call that reported no cost adds
  nothing to the sum. Model picks are per entry and stage ([runners.md](references/runners.md#models)); an unfilled or
  invalid value fails the run before any call.
- **Pause**: `.factory/pause` in the target repo makes every run exit 0 before any work, and
  stops `issue-pipeline` before its next item; delete it to resume.
- **Loading skills**: the run script copies the skills a prompt needs into the run's view, and
  the prompt reads `skills/<name>/SKILL.md` by path, never by invocation;
  `disable-model-invocation` blocks that.
- **oncue**: [`assets/oncue.mjs`](assets/oncue.mjs) is a bundled scheduler CLI; run it with `node`
  or `bun`, never read it.
