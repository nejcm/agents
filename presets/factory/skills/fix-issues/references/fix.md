# Fix and verify

A bounded fix for a reproduced item, then proof from a separate stage that the same trusted check
fails on base and passes on the patch. The fix stage is the only one that edits, and only its
checkout; the coordinator commits what it leaves.

## Gate

Fix only when all hold, checked by the coordinator:

- The repro line is `repro: outcome=reproduced` and the user confirmed the evidence shows the
  broken state.
- For a GitHub issue,
  `gh issue view <id> --repo "$repo" --json closedByPullRequestsReferences --jq '.closedByPullRequestsReferences[].number'`
  lists no PR other than this work's claimed draft; for a `<prefix>-<id>` item, triage's `ref`
  and the branch check in [Claims](../SKILL.md#claims) stand in. Another one: the user decides whether it is a
  fix artifact for [verify mode](reproduce.md#verify-an-existing-fix); never author over it.
- The profile allows agent PRs, or the user accepts a local commit as the outcome.

## Fix

`start` is `$base_sha`, or the claimed draft's checked head. Checkout:
`git worktree add --detach "$item/patch" "$start"`, so no local branch exists to collide on a
retry. In the jail its `.git` is read-only and the repo is hidden, so the stage has no `git`.

Inputs in `$check`: `spec.md`, `repro.md`, the profile's `Run` and `Scripts` as `run.md`, the
`debugging` skill's `SKILL.md`, and the verify skill of `$start`; per
[Dispatch](../SKILL.md#dispatch). Role per `orchestration`: Builder, sized by the likely change.
The stage follows the target repo's `AGENTS.md` and:

1. Follows `debugging`: root cause from runtime evidence, competing hypotheses eliminated before
   editing.
2. Writes a failing test first when the repo has a cheap local test target for the path; otherwise
   says why not.
3. Makes the smallest change that fixes the root cause. No unrelated cleanup, no edits to the
   verify skill, no deleted or weakened tests.
4. Runs the profile's test, lint and typecheck scripts and writes `$evidence/fix.md`: root cause,
   change, tests, what it skipped, and last `fix: outcome=changed` or `fix: outcome=stopped`.

It stops when the change outgrows the budget or touches more than the spec's feature and its
direct dependencies.

On `fix: outcome=changed`, the coordinator commits with the repo's hooks off, since the stage
could edit them:

```bash
git -C "$item/patch" add -A
git -C "$item/patch" -c core.hooksPath=/dev/null commit -q -m "fix: <feature> (<#id or prefix-id>)"
commit=$(git -C "$item/patch" rev-parse HEAD)
```

## Verify

A fresh Verifier stage, never the fix stage's session, with `$dir=$item/verify` holding `base/`
and `patch/` exports of `before=$(git merge-base "$base_sha" "$commit")` and `$commit`. Inputs
in `$check`: `spec.md`, `repro.md`, `run.md`, and the verify skill of `before`. The check is
defined by base: the journey is read from `$check`, `repro.md`'s steps are run as written, and
`base/` runs first.

1. On `base/`: the check twice; the broken state both times.
2. On `patch/`, same data and environment: the check twice; the expected state both times, the
   same state value cross-checked.
3. The profile's test, lint and typecheck scripts pass on `patch/`.
4. Smoke the blast radius: neighbouring journeys in the feature map that share the changed code.

It writes `$evidence/verify.md`: pass or fail per step, evidence paths, commands run, and last
`verify: outcome=confirmed` only when all four pass, else `insufficient` or `inconclusive` as in
[verify mode](reproduce.md#verify-an-existing-fix). A compile, unit test or plausible diff alone
is not a pass.

Not confirmed: rerun the fix stage once in the same checkout with `verify.md` in its inputs,
commit, and verify again in a fresh stage. A second failure ends the item with the repro report
and no PR.

## Before post

The user reviews `git -C "$item/patch" diff "$before" "$commit"` and the evidence; the coordinator
does not read them. Then post per [Writes](../SKILL.md#writes).
