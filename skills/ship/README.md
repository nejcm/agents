# ship

Takes a task to a merged PR: implement, cross-family review, verify, open the PR, get CI green,
then let a per-repo **merge gate** decide whether it auto-merges or waits for a human.

The agent never merges. It only records that a review passed and opts the PR in; the gate, running
on GitHub from the default branch, decides from a policy the PR cannot edit.

## Flow

```
/ship <task>  → lane: fix | bug | feature
  ├─ fix:     branch → build → cross-family review/fix → verify if runnable → file-pr
  ├─ bug:     branch → debugging: failing test first → as fix
  └─ feature: plan → questions + one approval → branch → per phase: fresh builder → review/fix → verify → commit
              (draft PR after phase 1, CI only) → final whole-branch review → ready
       └─ agent-review=success status on HEAD (+ door call: one-way → no `ship` label, human merges)
            └─ babysit-pr: wait for CI + review bots → fix failures and confirmed bot findings → re-attest
                 └─ clean → label `ship`
                      └─ merge-gate.yml (GitHub) runs merge-gate.sh against merge-policy.json from main
                           ├─ eligible     → `ship:eligible`, merge-gate ✓, [enforce] auto-merge armed on that SHA
                           └─ not eligible → `needs-human` + reasons, merge-gate ✗ [enforce], you merge or not
  push after opt-in → no agent-review on the new SHA → gate disarms until a re-review re-attests
  base merge after opt-in → same patch id → gate re-attests and re-arms
```

After plan approval the loop runs to completion. It stops only for a human reviewer's comment, a
`needs-human` verdict, an irreversible or product decision it can't infer, or a fix loop at its
bound. Conflicts, a branch behind its base, a missing bot review and pre-existing or flaky CI are
handled or reported, not stops.

## Files

| Path | Role |
| ---- | ---- |
| `SKILL.md` | The procedure the agent follows: loop, setup, upgrade, stop conditions. |
| `agents/openai.yaml` | Codex metadata; disables implicit invocation. |
| `assets/merge-policy.json` | Default rules, copied to `.github/` and tailored per repo. |
| `assets/merge-gate.sh` | Prints why a PR can't auto-merge (nothing = eligible). Read-only; runs locally too. |
| `assets/merge-gate.yml` | GitHub workflow that runs the script, sets labels and the `merge-gate` status, arms or disarms auto-merge. |

### `merge-policy.json`

| Key | Meaning |
| --- | ------- |
| `mode` | `shadow` only labels and summarises; `enforce` also arms/disarms GitHub auto-merge. |
| `max_changed_lines` | Additions + deletions allowed, excluding `exclude_from_size` files. A ceiling against a runaway agent (default 1000); below it the agent's review decides. |
| `max_files` | Files touched allowed (default 40). |
| `exclude_from_size` | Regexes not counted toward lines: lockfiles, snapshots, generated code. |
| `deny_paths` | Regexes that always need a human: CI, agent instructions, migrations, auth, manifests, lockfiles, Docker, `.env`, infra, test-runner configs. Old and new names of renames both checked. |
| `test_paths` | Regexes for test files and snapshots. Editing one that loses lines, deleting it, renaming it from or into a test path, or adding a skip/focus marker (`.only(`, `.skip(`, `xit(`, `@pytest.mark.skip`, `t.Skip(`, `#[ignore]`) blocks auto-merge; adding tests is fine. |

### `merge-gate.sh`

```bash
GH_REPO=owner/repo .github/scripts/merge-gate.sh <pr> [head-sha]
```

Blocks on: draft, a base other than the default branch (stacked PR), changes requested in review, no `ship` label, over size, protected path,
rewritten test, added skip/focus marker, or no `agent-review` = `success` status on the head SHA whose
description names the PR diff's `git patch-id --verbatim`.

### `merge-gate.yml`

- Triggers on `pull_request_target` (opened, push, reopened, labelled, unlabelled, ready), on
  `agent-review` commit statuses, and on `merge_group`, where it only reports `merge-gate` on the
  queue's SHA.
- Re-attests `agent-review` on a head whose `gh pr diff` patch id matches one an earlier commit of
  the PR was approved with, so base merges don't need a new review.
- `pull_request_target` runs the default branch's workflow, script and policy, and the job only
  checks out `.github/` from there. PR code is never run, which is why it can hold write tokens.
- Posts `merge-gate` on every evaluated head: success for non-`ship` PRs and eligible PRs, failure
  for ineligible `ship` PRs in enforce mode. As a required check it forces re-evaluation after
  every push.
- Arms auto-merge with `--match-head-commit`; disarms only auto-merge it armed itself.

## Install in a repo

`ship` offers this when a repo has no gate. By hand:

1. Copy `assets/merge-gate.yml` → `.github/workflows/`, `assets/merge-gate.sh` →
   `.github/scripts/` (executable), `assets/merge-policy.json` → `.github/`.
2. Tailor `deny_paths`, `test_paths` and `exclude_from_size` to the repo. Keep `shadow`.
3. Dry-run the script on recent merged PRs and check the verdicts make sense.
4. Merge the setup PR by hand (it touches `.github/`, so it can't auto-merge).
5. Then, in this order: enable auto-merge (`gh api -X PATCH repos/<owner/repo> -F allow_auto_merge=true`),
   and add the CI check(s) plus `merge-gate` as required status checks on the default-branch ruleset,
   pinning `merge-gate` to the GitHub Actions app (`integration_id` 15368) so a token posting the status by hand can't pass it.
   Then either the merge queue (org-owned public repos, or private on Enterprise Cloud; add
   `merge_group:` to each required CI workflow) or "Require branches to be up to date before merging".
   Requiring `merge-gate` before the workflow is on the default branch blocks every PR.
6. Watch `shadow` verdicts for a week or two; switch `mode` to `enforce` when you agree with them.

To take a PR over by hand at any point, remove the `ship` label.

## Upgrade

Both gate files carry a `# merge-gate vN` header. Bump it in `assets/` with every gate change.
When a repo's header is older, copy the workflow and script over (never its policy) in a PR.
Policy default changes (the size ceiling, new `deny_paths`/`test_paths` entries) reach only new
installs, and the ruleset source pin is a repo setting: apply both to an existing repo by hand.

## Limits

- `agent-review` is self-attested by the loop; GitHub doesn't verify a review happened. Its
  description carries the approved `git patch-id --verbatim`, which the gate recomputes from the PR
  diff and re-attests across base merges, so a base merge that leaves the patch unchanged needs no
  new review. That catches stale attestations, not forged ones. Diffs too large for GitHub's diff
  API always block. Patch ids ignore line numbers, so the same edit moved to an identical context
  keeps its id, and patch-id equality doesn't catch a semantic clash with the new base; required
  CI on the merged head does.
- Once a PR is in the merge queue the gate can't pull it: `--disable-auto` is a no-op there and the
  queue run reports `merge-gate` success. To stop a queued PR, remove it from the queue by hand.
- Without a merge queue, a PR that falls behind after the loop ends waits until someone runs
  `gh pr update-branch`; the gate then re-attests and re-arms it.
- Merges armed with `GITHUB_TOKEN` don't trigger `push` workflows on the default branch. Use a
  GitHub App token in the workflow if post-merge CI must run.
- The gate guards against mistakes, not a hostile or prompt-injected agent: with the same token it can
  drop `ship` and merge, or post `agent-review` itself. The real boundary is a required human approval.
- Reviews fire no gate event: a changes-requested review after the gate passed doesn't disarm armed
  auto-merge, and an approval or dismissal doesn't clear `needs-human`, until the next push, label or
  status. No safe trigger exists (`pull_request_review` runs the PR's own workflow with a write token).
- Each repo vendors its own copy. If drift hurts, move the gate to a reusable workflow in this
  (public) repo and call it from a thin per-repo workflow.
