# gh stack

GitHub CLI extension for stacked branches/PRs: an ordered chain of branches on top of trunk, each with its own small PR based on the branch below it. Use for large or dependent work that should land as separate reviewable PRs instead of one big diff. Stacks are strictly linear — use a separate stack per independent line of work.

## Setup (one-time)

```bash
gh extension install github/gh-stack
git config rerere.enabled true         # remember conflict resolutions
git config remote.pushDefault origin   # required if repo has >1 remote
```

## Commands

- `gh stack init <branch>` — start a stack, checkout its branch
- `gh stack add <branch>` — add the next layer on top of the current branch
- `gh stack submit --auto` — push all branches, open draft PRs (`--open` for review-ready)
- `gh stack view --json` — machine-readable stack state (use over `--short`, which is for humans)
- `gh stack sync [--prune]` — fetch, reconcile with GitHub, rebase, push; `--prune` deletes local branches for merged PRs
- `gh stack rebase --upstack [--continue|--abort]` — replay branches above onto a change; use after editing a lower layer
- `gh stack checkout <target>|up|down|top|bottom` — navigate the stack
- `gh stack merge <pr#|stack#> --yes [--squash|--merge|--rebase]` — merge a PR and everything below it (or a whole stack); all-or-nothing
- `gh stack unstack --local` — drop the local stack link (keeps the stack on GitHub); needed before re-checking-out a conflicting PR

## Workflow

1. `gh stack init auth` → commit → `gh stack add api` → commit → `gh stack add frontend` → commit
2. `gh stack submit --auto` → `gh stack view --json` to confirm
3. To fix a lower layer: `gh stack checkout <branch>` → commit → `gh stack rebase --upstack` → `gh stack top` → `gh stack push`
4. Periodically: `gh stack sync --prune`
5. Land: `gh stack merge <target> --yes`

## Gotchas

- Always pass non-interactive flags (`--json`, `--auto`, `--yes`) — commands detect TTY and otherwise open blocking prompts/TUIs.
- Always pass `--remote <name>` on push/submit/sync/rebase/link unless `pushDefault` is configured.
- No non-interactive reorder/removal — `gh stack modify` is TUI-only; restructure via `unstack` + `init` instead.
- PR titles/bodies are auto-generated; edit after with `gh pr edit`.
- Exit codes: `3` = rebase conflict (resolve, `git add`, `rebase --continue`), `6` = branch in multiple stacks, `9` = stacked PRs not enabled on repo.
- Divergent local/remote stacks: `sync` aborts cleanly rather than guessing — resolve manually.
