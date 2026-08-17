---
name: file-pr
description: Use when the user asks to file, open, create, or raise a PR or pull request.
category: workflow
---

# File a PR

Write the PR a reviewer wants to read six months from now, when the reviewer is me
and I have forgotten why this branch exists.

## Before filing

- **Check** whether a PR for this branch already exists (`gh pr list --head <branch>`).
  Update it instead of opening a second one.
- **Read** the diff against the base branch, not just your own memory of the work:
  `git diff <base>...HEAD`. Confirm the contents match what was actually asked for.
- **Detect** the base branch — it is not always `main`. Some repos here target `develop`.
  `gh repo view --json defaultBranchRef -q .defaultBranchRef.name`, and check what
  recent merged PRs targeted.
- **Verify** before filing, not after: relevant lint, types, and tests pass locally. Do not
  open a PR on work you know is broken.
- **Open a real PR, not a draft**, so CI and any review automation runs. Draft only when
  explicitly asked, or when submitting a stack (see Related).

## Filing

Write the body to a temp file and pass it with `--body-file`. Do not inline a multi-line
body in `--body`; shells mangle the newlines and backticks.

```bash
gh pr create --base "$BASE" --title "feat: add profile editing" --body-file pr.md
```

Updating a PR that already exists:

```bash
gh pr edit <number> --title "..." --body-file pr.md
```

Report the PR number and URL when you are done.

## Title

Conventional Commits, lowercase, scoped where it helps. The title usually becomes the
squash commit message, so it has to stand on its own in `git log`.

Say what changed and why it matters, not which files moved.

- Bad: `perf: negotiate per-message deflate on the websocket`
- Good: `perf: cut websocket frame size by 70% with gzip`
- Good, from this repo's history: `refactor: centralize Convex auth gating in useAuthGate hook`

## Body

**Open with the problem, in the words I used when I asked for the work.** Then the fix.
Never lead with an inventory of what you changed — the diff already says that.

Shape:

```markdown
<1-3 sentences: what was broken or missing, and why it mattered.>

- <what changed>
- <what changed>
```

No `## Summary` / `## Testing` / `## Checklist` scaffolding. These are small PRs on repos
where CI already reports the checks; the ceremony adds nothing a reviewer reads.

Bad, both real examples from this account:

> Plan authored earlier but never written to the plans/ directory.

> - honour prefers-reduced-motion in both demos and the scanline
> - let the 100-column TUI frame scroll horizontally on narrow screens
> - complete tab/tabpanel ARIA wiring with a roving tabindex

The first says nothing. The second is a changelog with the reason amputated — a reader
cannot tell what was wrong before.

Good, real:

> Replace per-component `useConvexAuth()` + 'skip' ternaries with one shared `useAuthGate`
> hook, killing the recurring `ConvexError: Unauthenticated` bug class from authed queries
> firing before Better Auth loads the session.

That one sentence contains the symptom, the cause, and the fix.

## Attribution

End the body with the model and harness that wrote the change, so I can tell later which
setup produced which work:

```markdown
---
🤖 <model> via <harness>
```

State the model you are actually running as. If you genuinely do not know, write the
harness alone rather than guessing a model name.

## Scope

Do not let filing expand the change. If you notice unrelated problems while reading the
diff, mention them in your reply to me — not in the branch, and not in the PR body.

## Related

- Branching, commits, pushes, and untangling git state: the `git-workflow` skill.
- A chain of dependent PRs: [`../git-workflow/gh-stack.md`](../git-workflow/gh-stack.md).
  `gh stack submit` writes its own titles and bodies — pass `--open` so they are not drafts,
  then rewrite each one to the conventions above with `gh pr edit --body-file`.
