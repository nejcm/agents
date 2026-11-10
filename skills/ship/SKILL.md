---
name: ship
description: Use when the user says /ship or asks to take a task all the way to a merged PR — implement, cross-family review, verify, open the PR, get CI green, and hand off to the repo's merge gate.
category: workflow
---

# Ship

Invoking this skill is the user's approval, for this task only, to branch, commit, push,
open a PR, post the `agent-review` commit status, and add the `ship` label. It never
approves running `gh pr merge` yourself: the repo's merge gate (`.github/workflows/merge-gate.yml`)
decides whether to auto-merge, from the policy on the base branch.

## Setup (once per repo)

The gate is three files in this skill's `assets/`, vendored into each repo. Installing it is its
own task: ask first, then:

1. Copy `assets/merge-gate.yml` to `.github/workflows/`, `assets/merge-gate.sh` to
   `.github/scripts/` (executable), and `assets/merge-policy.json` to `.github/`.
2. Tailor the policy to the repo's layout: its auth, migration, infra and generated paths, its
   lockfiles, its test naming. Keep `"mode": "shadow"`.
3. Dry-run `GH_REPO=<owner/repo> .github/scripts/merge-gate.sh <n>` on 5 recent merged PRs and
   show the verdicts. Expect "missing opt-in label" and "agent-review is missing" on all of them.
4. Open the setup PR. It touches `.github/`, so a human merges it.
5. After it merges, ask before changing repo settings:
   `gh api -X PATCH repos/<owner/repo> -F allow_auto_merge=true`, then add the repo's CI check(s)
   and `merge-gate` as required status checks on the default-branch ruleset. Requiring
   `merge-gate` before the workflow is on the default branch blocks every PR.
6. Switch `"mode"` to `"enforce"` only when the user says the shadow verdicts look right.

**Upgrade**: when a repo's `# merge-gate vN` header is older than `assets/`, copy the workflow and
script over (never the policy) and open a PR. Bump the header in `assets/` with every gate change.

## Loop

1. **Branch** off the up-to-date default branch (`git-workflow`). Never ship from a dirty tree
   holding unrelated work.
2. **Build** with the staged pattern in `agent-orchestration`: plan if none is accepted,
   build, cross-family review/fix, live verify. Run the repo's lint, types and tests.
3. **Open the PR** with `file-pr`. Not a draft.
4. **Attest the review** only after the cross-family reviewer approves the exact head SHA:

   ```bash
   gh api "repos/{owner}/{repo}/statuses/$(git rev-parse HEAD)" \
     -f state=success -f context=agent-review -f description="<reviewer model> approved"
   ```

   Every later commit needs its diff reviewed and the status posted again on the new SHA.
5. **Opt in**: `gh pr edit <n> --add-label ship`. If the repo has no merge gate, offer Setup as a
   follow-up and report that this PR needs a manual merge.
6. **CI**: use the host's PR monitor when there is one (the Claude app's Auto-fix); otherwise
   `gh pr checks <n> --watch --fail-fast` as a background command. Fix only failures this branch
   caused, then repeat step 4.
7. **Read the verdict**: the PR's `ship:eligible` or `needs-human` label and the gate run's
   summary. Locally, `.github/scripts/merge-gate.sh <n>` prints the same reasons.

## Stop and report

Stop, leave the PR open, and report the reason when any of these happen:

- Review still has confirmed findings after 3 fix rounds.
- CI is still red after 2 fix attempts, or the failure is flaky/infra (rerun once, never "fix" it).
- The gate says `needs-human`. Quote its reasons; do not reshape the change to slip under them.

Never edit or delete existing tests, CI config, or the merge policy to get a pass. Never enable
auto-merge or merge by hand. End with: PR link, gate verdict, checks state, reviewer model.
