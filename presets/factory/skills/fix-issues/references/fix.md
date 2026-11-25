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

Unattended (`issue-pipeline` at `draft-pr`), no one confirms the evidence: the reproduced line,
an empty `closedByPullRequestsReferences` for a GitHub issue, and the claim checks are the gate;
the base-first verify stage and review of the draft stand in for the user.

## Fix

`start` is `$base_sha`, or the claimed draft's checked head. Checkout:
`git -c core.hooksPath=/dev/null -c core.fsmonitor=false worktree add --detach "$item/patch" "$start"`, detached so no
local branch collides on a retry. The stage leaves its changes uncommitted; the coordinator commits them.

Inputs in `$check`: `spec.md`, `repro.md`, the profile's `Run` and `Scripts` as `run.md`, the
`debugging` skill's `SKILL.md`, and the verify skill of `$start`; per
[Dispatch](../SKILL.md#dispatch). Role per `orchestration`: Builder, sized by the likely change.
The stage follows the target repo's `AGENTS.md` and:

1. Follows `debugging`: root cause from runtime evidence, competing hypotheses eliminated before
   editing.
2. Writes a failing test first when the repo has a cheap local test target for the path; otherwise
   says why not.
3. Makes the smallest change that fixes the root cause. No unrelated cleanup, no edits to the
   verify skill, no weakened tests; a deleted or renamed test gets a stated reason. Prefers existing
   code and the standard library; adds a package only for substantial functionality, naming why.
4. Runs the profile's test, lint and typecheck scripts and writes `$evidence/fix.md`: root cause,
   change, tests, what it skipped, and last `fix: outcome=changed` or `fix: outcome=stopped`.

It stops when the change outgrows the budget or touches more than the spec's feature and its
direct dependencies. When going on would mean guessing (credentials, production access, a
requirement the spec leaves open, work past its feature), the stage, fix or verify, says what is
missing and ends with `escalated: <credentials|prod-access|ambiguous|out-of-scope>` in place of
the outcome line, per [escalate](reproduce.md#escalate).

On `fix: outcome=changed`, the coordinator commits with hooks and fsmonitor off, since the stage
could set them:

```bash
git -c core.hooksPath=/dev/null -c core.fsmonitor=false -C "$item/patch" add -A
git -c core.hooksPath=/dev/null -c core.fsmonitor=false -C "$item/patch" commit -q -m "fix: <feature> (<#id or prefix-id>)"
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
[verify mode](reproduce.md#verify-an-existing-fix). A compile, unit test, code review or plausible
diff alone is not a pass.

Not confirmed: rerun the fix stage once in the same checkout with `verify.md` in its inputs,
commit, and verify again in a fresh stage. A second failure ends the item with the repro report
and no PR. Unattended has no rerun: the item ends `blocked`, and the coordinator posts the spec and
repro record as its one comment.

## Before post

The user reviews `git -C "$item/patch" diff "$before" "$commit"` and the evidence; the coordinator
does not read them. Then post per [Writes](../SKILL.md#writes).
