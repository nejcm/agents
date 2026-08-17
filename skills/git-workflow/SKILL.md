---
name: git-workflow
description: Use when the user asks to branch, commit, push, rebase, set up stacked PRs, or untangle git state. Preserves unrelated work in progress. To open or write a PR use file-pr.
category: workflow
---

# Git Workflow

## Workflow

### 1. Inspect

```bash
git status --porcelain
git diff --stat
```

- **Confirm** the current branch.
- **Preserve** unrelated user changes.
- **Identify** staged, unstaged, and untracked files.
- **Check** divergence from the base branch.

### 2. Branch

```bash
git checkout -b feature/user-profiles
```

- **Start** from the intended base.
- **Update** the base when safe.
- **Require** a clean worktree when switching risks conflicts.
- **Follow** branch naming rules.

### 3. Commit

- **Stage** only intended files.
- **Review** the staged diff.
- **Keep** commits atomic.
- **Run** relevant lint, types, and fast tests.
- **Never** commit secrets, credentials, or debug code.

```bash
git add <files>
git diff --cached
git commit -m "feat: add profile editing"
```

**Format**

```text
<type>: <subject>

<body>

<footer>
```

**Types**

- `feat` — New feature
- `fix` — Bug fix
- `refactor` — Structural change
- `test` — Test change
- `docs` — Documentation
- `chore` — Maintenance

**Messages**

- **Use** specific, imperative subjects.
- **Explain** motivation in the body.
- **Link** issues or specs in the footer.
- **Avoid** generic subjects like `fix` or `update`.

### 4. Push

- **Run** the relevant full test suite.
- **Check** base-branch divergence.
- **Resolve** conflicts before pushing.
- **Keep** hooks enabled unless justified.
- **Never** force-push `main` or `master`.

### 5. Pull Request

Filing the PR itself — title, body, base branch, attribution — lives in the `file-pr`
skill. Use it rather than composing a PR body here.

### Stacked PRs

For large or dependent changes that should land as a chain of small reviewable PRs, use `gh stack` instead of a single branch/PR. See [gh-stack.md](./gh-stack.md) for setup, commands, and workflow.

## Safety

- **Never** overwrite unrelated changes.
- **Never** use destructive Git commands without approval.
- **Never** push broken or unverified code.
- **Avoid** generated files and large binaries.
- **Report** failed checks before continuing.

## Agent Responsibilities

- **Builder** — Branch, implement, test, commit, push.
- **Planner** — Inspect history and diffs.
- **Reviewer** — Review diffs, commits, and PR text.

## Results

**Success**

```json
{
  "operation": "push",
  "status": "success",
  "data": {
    "branch": "feature/user-profiles",
    "base": "main",
    "commits": 3,
    "files_changed": 5,
    "insertions": 234,
    "deletions": 45
  }
}
```

**Failure**

```json
{
  "operation": "commit",
  "status": "error",
  "error": {
    "type": "working_directory_not_clean",
    "message": "Unstaged changes remain.",
    "resolution": "Stage, stash, or exclude them."
  }
}
```

## Branch Names

```text
feature/short-description
bugfix/issue-number-description
hotfix/critical-issue
refactor/component-name
docs/update-readme
```
