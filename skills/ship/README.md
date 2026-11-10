# ship

Takes a task to a merged PR: implement, cross-family review, verify, open the PR, get CI green,
then let a per-repo **merge gate** decide whether it auto-merges or waits for a human.

The agent never merges. It only records that a review passed and opts the PR in; the gate, running
on GitHub from the default branch, decides from a policy the PR cannot edit.

## Flow

```
/ship <task>
  └─ branch → staged build (agent-orchestration) → cross-family review/fix → verify
       └─ file-pr → agent-review=success status on HEAD → label `ship`
            └─ merge-gate.yml (GitHub) runs merge-gate.sh against merge-policy.json from main
                 ├─ eligible     → `ship:eligible`, merge-gate ✓, [enforce] auto-merge armed on that SHA
                 └─ not eligible → `needs-human` + reasons, merge-gate ✗ [enforce], you merge or not
  new push → no agent-review on the new SHA → gate disarms → agent re-reviews → re-attests
```

The loop stops and reports after 3 review rounds with open findings, 2 failed CI fixes, or a
`needs-human` verdict.

## Files

| Path | Role |
| ---- | ---- |
| `SKILL.md` | The procedure the agent follows: loop, setup, upgrade, stop conditions. |
| `assets/merge-policy.json` | Default rules, copied to `.github/` and tailored per repo. |
| `assets/merge-gate.sh` | Prints why a PR can't auto-merge (nothing = eligible). Read-only; runs locally too. |
| `assets/merge-gate.yml` | GitHub workflow that runs the script, sets labels and the `merge-gate` status, arms or disarms auto-merge. |

### `merge-policy.json`

| Key | Meaning |
| --- | ------- |
| `mode` | `shadow` only labels and summarises; `enforce` also arms/disarms GitHub auto-merge. |
| `max_changed_lines` | Additions + deletions allowed, excluding `exclude_from_size` files. |
| `max_files` | Files touched allowed. |
| `exclude_from_size` | Regexes not counted toward lines: lockfiles, snapshots, generated code. |
| `deny_paths` | Regexes that always need a human: CI, agent instructions, migrations, auth, manifests, lockfiles, Docker, `.env`, infra. Old and new names of renames both checked. |
| `test_paths` | Regexes for test files. Editing one that loses lines, or renaming/deleting it, blocks auto-merge; adding tests is fine. |

### `merge-gate.sh`

```bash
GH_REPO=owner/repo .github/scripts/merge-gate.sh <pr> [head-sha]
```

Blocks on: draft, no `ship` label, over size, protected path, rewritten test, or no
`agent-review` = `success` status on the head SHA.

### `merge-gate.yml`

- Triggers on `pull_request_target` (opened, push, reopened, labelled, unlabelled, ready) and on
  `agent-review` commit statuses.
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
   and add the CI check(s) plus `merge-gate` as required status checks on the default-branch ruleset.
   Requiring `merge-gate` before the workflow is on the default branch blocks every PR.
6. Watch `shadow` verdicts for a week or two; switch `mode` to `enforce` when you agree with them.

To take a PR over by hand at any point, remove the `ship` label.

## Upgrade

Both gate files carry a `# merge-gate vN` header. Bump it in `assets/` with every gate change.
When a repo's header is older, copy the workflow and script over (never its policy) in a PR.

## Limits

- `agent-review` is self-attested by the loop; GitHub doesn't verify a review happened.
- Merges armed with `GITHUB_TOKEN` don't trigger `push` workflows on the default branch. Use a
  GitHub App token in the workflow if post-merge CI must run.
- Open in enforce mode: a label removal racing an `agent-review` status, and a force-push back to
  an earlier SHA that already has `merge-gate` = success. Both need write access.
- Each repo vendors its own copy. If drift hurts, move the gate to a reusable workflow in this
  (public) repo and call it from a thin per-repo workflow.
