# Reproduce

Show the exact symptom twice through the app's real surface, driven by the repo's verify skill.
No confirmed reproduction, no fix. The stage runs per [Dispatch](../SKILL.md#dispatch) in
`$item/repro`, a `git archive "$base_sha"` export that is discarded afterwards; it runs and
observes, never edits.

## Inputs

In `$check`: `spec.md`, the profile's `Run` section as `run.md`, and the verify skill of
`$base_sha` (`.cursor/skills/verify-<app>/SKILL.md` and `features/<feature>.md`). Role per
`model-orchestration`: Verifier.

## Steps

1. **Bring up** the app with the verify skill's launch and the `Run` recipe's isolation. Confirm
   it is the right app, data set and feature state from stable markers, not window order or a
   title.
2. **Name** the correct final state and the broken final state from the spec before acting.
3. **Drive** the feature's journey through the real surface: clicks, typing, navigation, CLI
   calls, HTTP requests, whatever the surface is. State inspection may confirm an observation; it
   never injects or forces the symptom.
4. **Observe** the broken final state, capture it (screenshot, output, log excerpt) into
   `$evidence/repro/`, and cross-check one real state value when the surface allows.
5. **Reset** enough state to make a second attempt independent, then repeat 3 and 4. Confirmed
   means the same broken state twice. An expected dialog, loading state or setup step is not the
   symptom.
6. **Tear down** with the verify skill's cleanup and confirm the evidence survived it.

At most three attempts at the path within the budget. The record, in the file and with the last
line the stage prompt states ([Records](../SKILL.md#records)), holds the exact steps and commands
run (the check verify will rerun), both final states, the state value and evidence paths. Outcome:

- `reproduced`: the broken state, twice.
- `not-reproduced`: the path ran and the expected state appeared. Report it; no fix.
- `blocked`: the feature map, launch, data or a precondition was missing; say which above the
  line. Never substitute a unit test, source reading or a forced state for the surface.

[Escalate](#escalate) instead when a human must supply something.

The coordinator reads only the record's last line. The user reads the report and evidence; a correction they give reruns the stage once.

## Verify an existing fix

For verdict `fixed`. The artifact owns the fix: never edit it, add a competing patch or open
another PR. Run code only from a commit someone with write access put in `$repo`.

1. **Qualify** the projection's `ref`, model-free, and pin `before` and `after` SHAs:
   - PR `#<n>`: `gh api "repos/$repo/pulls/<n>" --jq '"\(.state) \(.merged) \(.base.ref) \(.head.repo.full_name) \(.head.sha) \(.merge_commit_sha) \(.commits)"'`.
     The base ref must be `$base`.
     - Merged: `after` is `merge_commit_sha`, and `git merge-base --is-ancestor "$after" "$base_sha"`
       must pass. `before` is `$after^1` when `after` has two parents or the PR has one commit;
       otherwise the merge strategy is ambiguous: ask the user for `before`, which must be an
       ancestor of `after` on `$base`, or report `blocked: ambiguous baseline`.
     - Open (`state` is `open`): the head repo must be `$repo`; pushing a branch there takes
       write access, so fork heads never qualify. A closed, unmerged PR never qualifies.
       `git fetch "$remote_url" "refs/pull/<n>/head"`, check `FETCH_HEAD` is the
       head SHA; `after` is that SHA, `before` is `git merge-base "$base_sha" "$after"`.
   - Commit `<sha>`: `after=$(git rev-parse --verify "<sha>^{commit}")`, an ancestor of
     `$base_sha`; `before` is `$after^1`.

   Anything else, or a failed check: `blocked: untrusted fix artifact`. Unattended
   (`issue-pipeline`), the coordinator does this step with merged PRs and commits only, and the
   stage, prompted `Stage: verify.`, does step 2 alone.
2. **Measure** in one fresh Verifier stage, `$dir=$item/verify` holding `base/` and `patch/`
   exports of `before` and `after`, same data and environment. Inputs as above, with the verify
   skill of `before`: the reproduce steps, run twice on `base/` first, then twice on `patch/`,
   with the verify skill and journey read from `$check` for both.

The stage's record ([Records](../SKILL.md#records)) ends with its outcome:

- `confirmed`: broken twice on `base/`, expected state twice on `patch/`.
- `insufficient`: broken on both; the artifact did not resolve the symptom.
- `inconclusive`: the baseline did not reproduce, a build could not run, or the evidence does not
  show the discriminating state. It names the half that could not be measured and claims nothing.

The outcome, both SHAs and the artifact link may become the run's one comment on the issue. No PR.

## Escalate

Any stage, when going on would mean guessing: say what is missing above the last line, and make
the last line `escalated: <reason>` in place of the outcome line. Reasons: `credentials` (a secret
or account), `prod-access` (production data or systems), `ambiguous` (the spec leaves the right
behaviour open), `out-of-scope` (the fix reaches past the spec's feature). The item stops there.
Attended, the coordinator shows the user the record; unattended, `issue-pipeline` ends it
`escalated` (final, never deferred) and posts the record once as the ticket comment.
