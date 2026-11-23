---
name: automate-factory
description: Use when the user asks to schedule or automate recurring agent work for a repo set up with setup-factory (retros, analytics, PR babysitting, CI triage, coverage, security review, digests), or to add, change or re-check a factory automation
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
   - GitHub Actions: a GitHub remote and the profile's `CI` line.
2. **Suggest**: read each file in [`references/catalog/`](references/catalog/). For every entry
   whose requirements the profile meets, give one line: the entry and the profile fact that makes
   it worth running ("4 open PRs with review bots", "CI failed 9 of 40 runs on main"). List the
   rest once with the missing piece. An entry whose `Status` condition is unmet is listed, never
   offered.
3. **Pick**: the user picks by number. Ask nothing else in this round.
4. **Place** each pick: ask where to run it, offering only runners that are both in the entry's
   `Runners` and detected in step 1. Then ask only the entry's `Choices`.
5. **Write** per [`references/runners.md`](references/runners.md): the prompt to
   `.factory/automations/<entry>.md`, the run script to `.factory/automations/<entry>.sh`, and
   the runner config as a proposed diff. Fill each `<skill-path:<name>>` in the script's
   `skills` list with that skill's resolved directory, found by the lookup in
   [`../setup-factory/SKILL.md`](../setup-factory/SKILL.md#loading-other-skills); on a hosted
   runner only a committed project copy counts. A skill not found makes the entry unavailable on
   that runner. Also fill `<app>`, `<base>` and the entry's choices.
6. **Smoke run as the runner** (activation gate): its checkout, identity, tools and secrets, in
   dry-run mode, per [`references/runners.md`](references/runners.md#smoke-run). A run on this
   laptop does not prove a hosted runner. On failure, report the exact error, leave the entry
   `proposed`, and fix nothing silently.
7. **Record** each entry in the profile's `Automations` section: runner, trigger, files, smoke
   run date and result, status (`active`, `proposed`, `failed: <reason>`).

On a re-run, read the `Automations` section first, re-check detected runners, and offer changes
only to entries the user names or whose smoke run failed.

## Scope (v1)

- Written and activated: one local runner (systemd user timer or cron) and GitHub Actions for
  report-only entries.
- Later, not offered in v1: harness schedulers (Claude routines, Cursor Automations) and external
  services. They do not run the fetch and view steps these prompts depend on.
- No scheduled run edits code, pushes, opens PRs or replies to threads. Entries that lead to
  changes name an attended follow-up the user starts from the report. The one external write is
  the digest's post step, local only.

## Rules

- **Safety**: every automation follows [`references/safety.md`](references/safety.md), including
  the lethal-trifecta rule. An entry that cannot meet it on a runner is not offered there.
- **Writes**: freely only to `.factory/`. Runner config (workflow files, systemd units, crontab
  lines, scheduler settings) is shown as a proposed diff and applied only after the user confirms.
- **Secrets**: never ask for, read, store or write one. Name a secret by its variable or setting
  name only ("repo secret `ANTHROPIC_API_KEY`") and print the steps for the user to set it.
- **Budgets**: apply the profile's per-run budget with the harness's own cap where it has one
  (Claude Code `--max-budget-usd`; check `--help` for others); otherwise record the budget as
  unenforced.
- **Loading skills**: the run script copies the skills a prompt needs into the run's view, and
  the prompt reads `skills/<name>/SKILL.md` by path, never by invocation;
  `disable-model-invocation` blocks that.
