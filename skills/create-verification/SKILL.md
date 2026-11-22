---
name: create-verification
description: Generate a repo-local verification skill (`.agents/skills/verify-<app>/`) that launches and drives the app the way a user does and captures proof, plus the `.tender/verify.yaml` checks tender runs on every PR head. Use when asked to create a verify skill or verification contract for a repo, or when a repo has no scripted way to prove its UI, CLI or service works.
category: workflow
---

# Create verification

Adapted from pstack's [`create-verification-skill`](https://github.com/cursor/plugins/tree/main/pstack/skills/create-verification-skill) (MIT).

You produce two things, both committed to the repo:

- `.agents/skills/verify-<app>/`: the interactive part. An agent reads it cold, mid-task, having never seen the app, and uses it to launch, drive and prove a change.
- `.tender/verify.yaml` and `.tender/checks/`: the deterministic part. tender reads the contract from the base branch, runs it sandboxed and offline on each PR head, and holds Ready to merge and auto-merge until it passes. Its schema is in tender's `docs/config.md` under "Verify contract".

## 1. Interview the repo, not the user

Answer these from the code, CI config, manifests and README. Ask the user only what you cannot observe.

- **Surface:** what a user touches: web UI, CLI/TUI, desktop app, API, mobile app, library. Pick the primary one and note the rest.
- **Run:** the repo's own dev or start command, with its env vars, seed data and auth.
- **Ports and services:** every port the app listens on, and every database, queue or cache it needs. A service the repo already describes in a Compose file is reused; otherwise write one.
- **Drive:** existing harnesses first (Playwright/Cypress specs, expect scripts, curl-able routes, a debug port), then a generic recipe: a browser for web and Electron, tmux or a PTY for CLI/TUI, HTTP for services.
- **Observe:** screenshots, terminal transcripts, response bodies, logs, exit codes, DB state.
- **Isolate:** whether two instances can run side by side (ports, data dirs, profiles). If not, the skill says so and refuses to drive an instance it did not start.

If the checkout does not build or start as-is, fix that first or report it precisely: a skill written against a broken base teaches wrong steps. An irrelevant missing asset that blocks startup may be created by the skill, marked as verification scaffolding, and removed in cleanup.

## 2. Write the skill

Write `.agents/skills/verify-<app>/SKILL.md` with frontmatter `name: verify-<app>` and a `description` naming the app, its surface and when to use it; without it the skill never registers. For Claude Code, also link it: `ln -s ../../.agents/skills/verify-<app> .claude/skills/verify-<app>`. Each section below is grounded in what the interview found, with no placeholders left:

- **Launch:** the exact start command and the ready signal. Ready means usable, not just that a process answers: migrations and seed data done, from an empty data dir. Ports come from `TENDER_PORT_0`, `TENDER_PORT_1`, … when set (tender assigns them, and its sandbox allows no others), else a fixed default; never a hard-coded port alone. Services come from a Compose file that publishes each port as `127.0.0.1:${TENDER_PORT_<n>}:<container port>`, with no `include`, `extends` or `network_mode: host`. Under tender (`TENDER_PORT_0` set) tender has already started them outside the sandbox, so the skill never runs `docker`; locally it runs `docker compose -p verify-<app>-$$ -f <file> up -d --wait` itself. For a short-lived CLI or TUI, launch means build once, then start each drive in its own isolated PTY or tmux session.
- **Doctor:** one read-only check that the instance is worth driving: process up, right build, port owned by this run, auth valid. Run it first, and again whenever anything looks off.
- **Drive:** the harness recipe with this repo's real selectors, routes and commands. Prefer stable handles (ARIA labels, data attributes, prompt strings, route paths) over coordinates and tab order.
- **Evidence:** proof goes under `.tender/proof/<feature>/`, which `.gitignore` lists. Images and video tender can attach are `.png`, `.gif`, `.jpg`, `.jpeg`, `.webp`, `.svg`, `.mp4`, `.mov`, `.webm`; transcripts and response bodies sit next to them. Exercise the real user path, not internal setters or test-only endpoints. Capture the action and the resulting state, not just the final screen. Check side effects (files, rows, messages) alongside what is visible. Mock only where a production boundary already isolates the external system. A dry-run or test mode is verified by observing what it skips, not by trusting its name.
- **Cleanup:** tear down what this run started, never by process name. Cleanup removes instances and scratch state, never the evidence.
- **Helpers:** every script the skill ships is executable and its invocation is shown in the skill body.

## 3. Seed the feature map

Create `.agents/skills/verify-<app>/features/README.md` plus one file per user-facing feature, the top 3-5 from routes, commands, menus or docs, in the shape of [`references/feature-map-example/`](references/feature-map-example/). Each file says, from the user's point of view, what the feature is, how to reach it, how to drive it and what end state proves it, under four H2s: `Sub-features`, `How to get to it (user POV)`, `Driving it with <harness>`, `Gotchas`. If the seed data lacks a precondition a journey needs, the journey fails and the reason goes in `Gotchas`; never weaken the journey to pass. A proof that drives one convenient entry point is incomplete when the map lists others.

## 4. Write the contract

`.tender/verify.yaml`, checks in this order:

1. The repo's own fast checks, from CI config first, then manifests (test, typecheck, lint), one check each.
2. One smoke check per primary surface, `run: sh .tender/checks/<app>-smoke.sh`: it launches the app on `TENDER_PORT_0`, waits for ready, drives one mapped feature's journey without a human, writes its proof under `.tender/proof/`, cleans up, and exits non-zero on any failed assertion. The skill's Drive section reuses it rather than repeating it. Scripts under `.tender/checks/` are critical paths, so a PR cannot quietly weaken them.

```yaml
checks:
  - name: test
    run: bun test
  - name: smoke
    run: sh .tender/checks/<app>-smoke.sh
    timeout: 300
    needs: { ports: 1 }                    # add compose: <file> for services
    proof: [".tender/proof/*.svg"]
```

The sandbox is offline except for the check's own ports, with a private `TMPDIR` and no Docker: dependencies must already be in the clone or install offline from the read-only `~/.bun`, `~/.npm` and mise caches. A browser that starts locally may not start there (Chromium binds a Unix socket in `TMPDIR`, and socket paths are capped at 108 bytes), so unless a browser is proven under tender's verifier, the check's proof is an SVG built from the state it observed and screenshots stay in the skill. Anchor proof globs under `.tender/proof/` so the collector never walks `node_modules`. Validate with `bun <tender>/tender.ts check .` (`<tender>` is the tender clone; ask for it if unknown) and fix until it passes.

## 5. Prove it once

Run the generated skill end to end once: launch, doctor, drive ONE mapped feature, capture evidence, clean up, then confirm the evidence still exists where the skill says. Then run every contract check the way tender does: in a fresh clone of the commit, with `TENDER_PORT_0` set to a free port, needing nothing from the network. Run cleanup after every failed attempt, so broken runs strand no processes or ports. A skill or contract never executed is a draft. If you proved it in a stand-in (a container for a VM, a local stack for a remote one), list every step the stand-in did that the target will not.

## 6. Hand off

Commit `.agents/skills/verify-<app>/`, the `.claude/skills/` link, `.tender/verify.yaml`, `.tender/checks/` and the `.gitignore` line. tender reads the contract only from the base branch and never auto-merges `.tender/**`, so it takes effect once a human merges it there. Point the user at `maintain-verification` for keeping the map honest as the app changes.
