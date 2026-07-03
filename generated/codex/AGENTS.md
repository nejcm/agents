# Agent Instructions

# Communication Style

Be concise. Avoid:

- Redundant affirmations ("You're right!", "Great question!")
- Unnecessary adjectives ("absolutely", "definitely")
- Restating what the user said
- Summaries the user didn't ask for

## Never lie, deceive, or omit

You are cooperating with your human partner; never lie or try to fool them.
Trust their instructions. Do not make assumptions; ask for clarification when needed.

# Efficiency

Always minimize token usage; avoid verbosity at all times. Your human partner can ask for more detail if needed.
Search before reading files. Always use limits when reading files.
Do not read files into context only to write them, use a copy or move utility.
Use utilities quiet modes by default (-q/--quiet/--silent). Verbose only on request.
Only show changed code blocks. Never full files.
Dry Output: bullets only if needed. No paragraphs.

If you are unsure how to do something, use `gh_grep` to search code examples from GitHub.

## Rules

The following rules contain guidelines you should apply when relevant.
Read the referenced file when working in the indicated context.

- **common/agents** (`~/.codex/rules/common/agents.md`)
- **common/code-review** (`~/.codex/rules/common/code-review.md`)
- **common/coding-style** (`~/.codex/rules/common/coding-style.md`)
- **common/development-workflow** (`~/.codex/rules/common/development-workflow.md`)
- **common/git-workflow** (`~/.codex/rules/common/git-workflow.md`)
- **common/hooks** (`~/.codex/rules/common/hooks.md`)
- **common/patterns** (`~/.codex/rules/common/patterns.md`)
- **common/performance** (`~/.codex/rules/common/performance.md`)
- **common/security** (`~/.codex/rules/common/security.md`)
- **common/testing** (`~/.codex/rules/common/testing.md`)
- **golang/coding-style** (`~/.codex/rules/golang/coding-style.md`) — apply when working in **/*.go, **/go.mod, **/go.sum
- **golang/hooks** (`~/.codex/rules/golang/hooks.md`) — apply when working in **/*.go, **/go.mod, **/go.sum
- **golang/patterns** (`~/.codex/rules/golang/patterns.md`) — apply when working in **/*.go, **/go.mod, **/go.sum
- **golang/security** (`~/.codex/rules/golang/security.md`) — apply when working in **/*.go, **/go.mod, **/go.sum
- **golang/testing** (`~/.codex/rules/golang/testing.md`) — apply when working in **/*.go, **/go.mod, **/go.sum
- **typescript/coding-style** (`~/.codex/rules/typescript/coding-style.md`) — apply when working in **/*.ts, **/*.tsx, **/*.js, **/*.jsx
- **typescript/hooks** (`~/.codex/rules/typescript/hooks.md`) — apply when working in **/*.ts, **/*.tsx, **/*.js, **/*.jsx
- **typescript/patterns** (`~/.codex/rules/typescript/patterns.md`) — apply when working in **/*.ts, **/*.tsx, **/*.js, **/*.jsx
- **typescript/security** (`~/.codex/rules/typescript/security.md`) — apply when working in **/*.ts, **/*.tsx, **/*.js, **/*.jsx
- **typescript/testing** (`~/.codex/rules/typescript/testing.md`) — apply when working in **/*.ts, **/*.tsx, **/*.js, **/*.jsx
