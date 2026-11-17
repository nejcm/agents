---
name: file-ticket
description: Use when the user asks to file, open, create, or raise a ticket, issue, or bug report in the repo's tracker (GitHub issues, Linear, or another).
category: workflow
---

# File a ticket

File one ticket a stranger can act on, in the tracker this repo actually uses. Never file a
duplicate, never guess the target.

## Target

1. If the repo has `.tender/config.yaml`, its `tracker` block names the target
   (`tracker.linear.project`, `tracker.linear.team`). If tender is on the machine,
   `bun <tender>/tender.ts check .` prints the resolved `tracker` (`null` if none); optional.
2. No `tracker` block: infer from the repo. A GitHub remote with issues enabled
   (`gh repo view --json nameWithOwner,hasIssuesEnabled`) means GitHub issues.
3. Still ambiguous (issues disabled, several candidates, a Linear team but no project): ask.

State the target in one line before searching.

## Tool

Use what this session can reach, best first:

- A tracker MCP server already connected (e.g. Linear's `list_issues`, `create_issue`, `create_comment`).
- The tracker's CLI, if installed and authenticated: `gh` (`gh auth status`), `linear`
  (check `linear --help` for the exact flags; do not guess them).
- Nothing reaches the target: say which tracker and what was missing, print the drafted
  title and body, and stop. Do not install tools or add MCP servers.

## Search first

Search open and recently closed tickets for the same problem, by the error text, symbol,
and two or three plain keywords:

```bash
gh issue list --repo "$REPO" --state all --search "<keywords>" --limit 20 \
  --json number,title,state,closedAt,url
```

A match: show it to the user and ask before acting. On yes, add one comment with the new
evidence instead of filing; a closed match is reopened only if the user says so.

## Draft

Title: one line, the symptom, not the fix. No Conventional Commit prefix unless the tracker uses one.

Body, short:

```markdown
<What is wrong, and what was expected.>

**Reproduce**
1. <step>

**Evidence**
- `path/to/file.ts:42`
- <exact error text, in a code block if multi-line>

**Scope**: <where the fix likely lives, or what is out of scope.>
```

Drop a section that has nothing real in it. No speculation presented as fact; mark a guess
as a guess. Never mention coding agents or AI in the title, body, or comment.

## Labels

None by default. Add `agent` only when the user asks, and `host:<host>` only when the user
names a host. Never add tender markers (`tender-intake: …`, `tender-guardrail: …`) or other
lines that pose as tender's.

## Filing

Write the body to a temp file outside the repo and pass it as a file; never inline a
multi-line body in a shell argument.

```bash
BODY=$(mktemp)   # write the drafted body into "$BODY"
gh issue create --repo "$REPO" --title "..." --body-file "$BODY" [--label agent]
gh issue comment <number> --repo "$REPO" --body-file "$BODY"
```

With an MCP tool, pass the body as the tool's description/body argument. Report the ticket
or comment URL when done.

## Related

- Opening a PR for the fix: the `file-pr` skill.
