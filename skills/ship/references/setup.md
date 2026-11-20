# Merge gate setup

Paths are relative to the ship skill's directory. Optional, once per repo.

Local mode needs no setup. Installing the gate moves enforcement onto GitHub: it runs from the
default branch where the agent can't edit it, and required checks back it. The gate is three
files in this skill's `assets/`, vendored into each repo. Installing it is its own task: ask
first, then:

1. Copy `assets/merge-gate.yml` to `.github/workflows/`, `assets/merge-gate.sh` to
   `.github/scripts/` (executable), and `assets/merge-policy.json` to `.github/`.
2. Tailor the policy to the repo's layout: its auth, migration, infra and generated paths, its
   lockfiles, its test naming. Keep `"mode": "shadow"`.
3. Dry-run `GH_REPO=<owner/repo> .github/scripts/merge-gate.sh <n>` on 5 recent merged PRs and
   show the verdicts. Expect "missing opt-in label" and "agent-review is missing" on all of them.
4. Open the setup PR. It touches `.github/`, so a human merges it.
5. After it merges, ask before changing repo settings:
   `gh api -X PATCH repos/<owner/repo> -F allow_auto_merge=true`, then add the repo's CI check(s)
   and `merge-gate` as required status checks on the default-branch ruleset, with `merge-gate`'s
   source pinned to GitHub Actions (`{"context":"merge-gate","integration_id":15368}`), so
   auto-merge only lands code CI tested against the current base:
   - **Org-owned public repo, or private on Enterprise Cloud**: turn on the merge queue and add
     `merge_group:` to every CI workflow behind a required check. PRs never need updating.
   - **Otherwise** (personal repos have no merge queue): turn on "Require branches to be up to
     date before merging".

   Requiring `merge-gate` before the workflow is on the default branch blocks every PR.
6. Switch `"mode"` to `"enforce"` only when the user says the shadow verdicts look right.

## Upgrade

When a repo's `# merge-gate vN` header is older than `assets/`, copy the workflow and
script over (never the policy) and open a PR. From v3 or v4, also add the new `deny_paths` and
`test_paths` entries from `assets/merge-policy.json` to the repo's policy, and ask before pinning
`merge-gate` to `integration_id` 15368 in the ruleset. v5 reads 12-character patch ids, so re-attest
open PRs approved under v4 with a full-length id. v6 adds local mode (`MERGE_GATE_LOCAL`,
`MERGE_POLICY`) and changes nothing in GitHub mode.
