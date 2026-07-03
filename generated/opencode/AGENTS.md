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

- **common/agents** (`~/.config/opencode/rules/common/agents.md`)
- **common/code-review** (`~/.config/opencode/rules/common/code-review.md`)
- **common/coding-style** (`~/.config/opencode/rules/common/coding-style.md`)
- **common/development-workflow** (`~/.config/opencode/rules/common/development-workflow.md`)
- **common/git-workflow** (`~/.config/opencode/rules/common/git-workflow.md`)
- **common/hooks** (`~/.config/opencode/rules/common/hooks.md`)
- **common/patterns** (`~/.config/opencode/rules/common/patterns.md`)
- **common/performance** (`~/.config/opencode/rules/common/performance.md`)
- **common/security** (`~/.config/opencode/rules/common/security.md`)
- **common/testing** (`~/.config/opencode/rules/common/testing.md`)
- **golang/coding-style** (`~/.config/opencode/rules/golang/coding-style.md`) — apply when working in **/*.go, **/go.mod, **/go.sum
- **golang/hooks** (`~/.config/opencode/rules/golang/hooks.md`) — apply when working in **/*.go, **/go.mod, **/go.sum
- **golang/patterns** (`~/.config/opencode/rules/golang/patterns.md`) — apply when working in **/*.go, **/go.mod, **/go.sum
- **golang/security** (`~/.config/opencode/rules/golang/security.md`) — apply when working in **/*.go, **/go.mod, **/go.sum
- **golang/testing** (`~/.config/opencode/rules/golang/testing.md`) — apply when working in **/*.go, **/go.mod, **/go.sum
- **typescript/coding-style** (`~/.config/opencode/rules/typescript/coding-style.md`) — apply when working in **/*.ts, **/*.tsx, **/*.js, **/*.jsx
- **typescript/hooks** (`~/.config/opencode/rules/typescript/hooks.md`) — apply when working in **/*.ts, **/*.tsx, **/*.js, **/*.jsx
- **typescript/patterns** (`~/.config/opencode/rules/typescript/patterns.md`) — apply when working in **/*.ts, **/*.tsx, **/*.js, **/*.jsx
- **typescript/security** (`~/.config/opencode/rules/typescript/security.md`) — apply when working in **/*.ts, **/*.tsx, **/*.js, **/*.jsx
- **typescript/testing** (`~/.config/opencode/rules/typescript/testing.md`) — apply when working in **/*.ts, **/*.tsx, **/*.js, **/*.jsx
