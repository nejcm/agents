---
name: maintain-verification
description: Periodic pass that keeps a repo's verification skill, feature map and `.tender/verify.yaml` honest - every feature read from source and driven live, at most one PR of proven corrections. Ends clean, changed or blocked. Use when asked to maintain, audit or refresh a verify skill or verification contract.
category: workflow
---

# Maintain verification

Adapted from pstack's [`maintain-verification-skill`](https://github.com/cursor/plugins/tree/main/pstack/skills/maintain-verification-skill), MIT, Copyright (c) 2026 Lauren Tan; license in [`LICENSE`](LICENSE).

A feature map rots the moment the app changes. This is the upkeep loop for a skill made by `create-verification`, or any repo-local verification skill with a feature map. The unit of rigor is the feature: every feature file covered from source and exercised live, not every sentence.

## Outcomes

Say which one:

- **clean:** every feature got source and live coverage, and every contract check passes; nothing to ship. No branch, no PR.
- **changed:** one PR ships proven corrections to the skill, map, harness or contract.
- **blocked:** coverage could not finish, or a proven fix could not ship safely. Say exactly what blocked it.

## Edit scope

Only the verification skill's own directory (`SKILL.md`, `features/`, its scripts), `.tender/verify.yaml` and `.tender/checks/`. Never product code: a behavior the map describes that the app no longer has is doc drift (fix the map) or a product regression (report it, don't paper over it). A contract change never makes a check weaker to pass; tender never auto-merges `.tender/**`, so a human sees it.

## Pass

0. **Locate the target.** The repo-local skill with Launch/Drive sections and a feature map, usually `.agents/skills/verify-*/` (or `.claude/skills/verify-*`, `.cursor/skills/verify-*`). Several → ask which; none → stop and point at `create-verification` rather than inventing one.
1. **Index hygiene.** Read the map README and glob its siblings. Fix missing, extra, duplicate or dead entries.
2. **Source wave.** One read-only subagent per feature file, run concurrently (pick models with `orchestration`); without subagents, read each feature in turn. Each explains how the feature works from source, flags likely drift with citations, and returns one live recipe: summary / source entry points / drift or none / recipe. Readers never drive the app or edit files.
3. **Reconcile.** Every feature file has a summary. Merge overlapping recipes into as few app states as practical. Spot-check cited drift; don't re-prove clean claims. Sweep recent churn for user-facing surfaces missing from the map, and require a concrete source path before calling one missing. Check the contract still matches the repo: each CI or manifest check it mirrors still exists under the same command.
4. **Contract run.** Run every `.tender/verify.yaml` check on the base branch the way tender does: a fresh clone at `origin/<base>`, `TENDER_PORT_*` set to free ports, nothing from the network. A failure is drift (fix it under edit scope) or a product regression (report it).
5. **Live pass.** Required even when source looks clean. You own all driving, following the skill's own launch model: one long-lived instance driven serially for servers and UIs, a fresh isolated session per drive for short-lived CLIs. Exercise every feature at least once and hold three invariants whatever fails: (1) never drive an instance you haven't doctored since it last surprised you: doctor before the first drive, on each fresh session, and after any failed drive, and reset or relaunch where doctor can't see the failure; (2) evidence captured so far survives every cleanup, checked at its location under `.tender/proof/`; (3) nothing a drive started outlives its use. A doctor failure caused by skill drift is fixed under edit scope and retried once, restarting only what the fix invalidated, before calling the pass blocked. A feature is `verified-unreachable` only with the concrete prerequisite (auth, entitlement, OS, external state) and the route attempted; a prerequisite the map omits is drift. Any harness fix is re-driven live before it ships. Final teardown comes after the last drive, re-proofs included.
6. **Triage.** Wrong or missing user-POV description: doc drift, fix it. Working behavior the harness can't drive: harness gap, fix it (scripts executable, invocation in the skill body). Broken app behavior: product gap, report it and keep it out of the PR.
7. **Ship or stop.** For changed: re-read every changed file, rerun step 4 for any contract change, then one PR. For clean or blocked: no PR; report the outcome and coverage honestly.

Keep short run notes (features covered, unreachable prerequisites, confirmed drift, outcome) outside the repo; don't commit them.
