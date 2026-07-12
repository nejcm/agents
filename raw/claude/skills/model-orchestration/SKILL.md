---
name: model-orchestration
description: Claude Code execution mechanics for multi-model orchestration — dispatch order, orchestration patterns, the Codex CLI (codex exec / codex exec review) and its wrapper pattern for running GPT-5.6, delegation packets, result verification, and long-running work. Use when implementing an approved plan or design, or when starting any medium-to-high complexity task that may warrant delegation, parallel work, plan→build→judge, an independent review, or shelling out to GPT-5.6 via Codex. Complements the always-on `@rules/model-routing.md` policy, which owns roles, effort, and model preferences.
---
# Model Orchestration

Claude Code-specific mechanics for the platform-agnostic model-routing policy.
Role, effort, and model preferences live in `@rules/model-routing.md`; this
skill covers how to actually dispatch, delegate, and run Codex here. Where they
conflict, the user's instructions and repository rules win.

Model names are preferences, not guarantees. Before dispatching, discover the
installed CLIs, available models, supported effort levels, and tool access.
Never invent a model ID, provider, effort level, permission mode, or
capability. If a preferred model is unavailable, use the next capable one and
disclose the fallback.

## Dispatch Mechanics

Use the first capable mechanism:

1. A host-native subagent or workflow with the required model, effort, tools,
   and isolation. Claude models (Sonnet 5, Opus 4.8, Fable 5) run directly via
   the `model` parameter.
2. A non-interactive CLI such as `codex exec` or `claude -p`.
3. Local execution, with any lost specialization or independence disclosed.

Limits: at most three automatic delegates, at most one per role unless scopes
differ, and no duplicate work without a specific reason. Parallelize
independent read-only work; sequence dependent phases. Retry a failed
delegation once with a concrete correction, then stop and re-plan. Describe a
review as independent only when another model actually performed it.

## Orchestration Patterns

Choose the smallest pattern that provides the needed benefit:

- **Specialist delegate** — one bounded task requiring different expertise or
  tools.
- **Parallel fan-out** — independent read-only surveys or reviews, followed by
  synthesis.
- **Plan → build → judge** — high-risk or ambiguous work needs independent
  evaluation after implementation.
- **Second opinion** — a read-only, cross-family challenge to a material
  decision or conclusion.

For cross-family staged work, assign each family the role it is strongest at,
keep phases sequential, and prevent self-review (example: ask Fable to produce
an implementation plan, ask GPT to implement the accepted plan, then ask Fable
to review the diff against the plan and repo rules). If a requested family is
unavailable, use the next capable model and disclose the reduced independence.

Do not use plan → build → judge as a default for all non-trivial work. Use a
second opinion when explicitly requested or when a decision is high-impact,
disputed, hard to reverse, security-sensitive, or held with low confidence.
Never claim a second opinion unless a separate model actually ran.

## GPT-5.6 runs only through the Codex CLI

- Entry points are `codex exec` and `codex exec review` with `-m gpt-5.6-sol`.
  In an interactive session, a direct shell call is the default path; the
  wrapper pattern below applies only inside workflows and subagents where shell
  is not first-class. For work they don't cover (investigation, data analysis),
  run `codex exec -m gpt-5.6-sol -s read-only` with a self-contained prompt.
- Workflow and subagent `model` parameters only accept Claude models, so wrap
  Codex: spawn a thin agent with `model: 'sonnet'`, `effort: 'low'` whose
  prompt writes a self-contained Codex prompt, runs `codex exec` via shell, and
  returns the report. Use the wrapper's `schema` option when structured output
  is useful.
- Prefix every wrapper label with `gpt-5.6:`, e.g.
  `{label: 'gpt-5.6:review-auth'}`. The workflow UI shows the wrapper's Claude
  model, so the label is the only indication of the real worker.
- Codex runs can exceed shell 10-minute timeout: set an explicit longer
  timeout, or run in the background and poll for the report artifact.
- Parallel Codex implementation wrappers must use `isolation: 'worktree'`;
  never give parallel writers the same worktree.
- Workflow token budgets count only Claude tokens. Codex usage is invisible to
  `budget.spent()`; track it separately when a budget matters.

## Calling Codex

Verify syntax with the installed `codex --help`, `codex exec --help`, and
`codex exec review --help`. Use a self-contained, direct prompt; do not prompt
Codex as if it were Claude. Write results to an artifact file so they survive
long runs and wrapper timeouts. Wrappers must create `$ARTIFACT_DIR` before
invoking Codex.

Investigation (read-only):

```bash
codex exec -m gpt-5.6-sol -C "$PWD" -s read-only \
  -o "$TEMP_DIR/result.md" "<focused investigation prompt>"
```

Implementation: use an isolated worktree and `-s workspace-write`. State the
permitted files, required behavior, exclusions, and verification.

Review — select exactly one target (`--uncommitted`, `--base <branch>`, or
`--commit <sha>`). A focus prompt cannot be combined with a target flag; the
CLI rejects it:

```bash
# Target-flag mode (no prompt argument):
codex exec review -m gpt-5.6-sol --uncommitted -o "$TEMP_DIR/review.md"

# Focus mode (prompt, no target flag) — describe the target in the prompt:
codex exec review -m gpt-5.6-sol -o "$TEMP_DIR/review.md" \
  "Review the uncommitted changes to src/foo.ts for <focus>."
```

`--uncommitted` also reviews untracked files; expect noise findings on local
scratch/settings files (e.g. `.claude/settings.local.json`) and discard them
rather than acting on them.

Computer use: state the flow, environment, expected evidence, screenshot or
video requirements, and whether edits are allowed. Confirm the invoked Codex
environment actually has the needed tools; CLI availability alone does not
prove computer-use availability.

On timeout, inspect the process and artifact before retrying. Retry once with
a concrete correction, then re-plan. If a review that inspected its target
finds no issues, accept that; do not rerun to force findings. If a diff was
already reviewed (and findings triaged) this session and has not changed,
cite that review instead of dispatching another. Reports must name the
inspected target and state clearly when there are no findings.

## Delegation Packet

Send only the context required for the assignment — no whole-codebase dumps or
raw transcripts:

```text
Objective: <specific outcome>
Success criteria: <observable result>
Role: <planner | builder | reviewer/judge | cheap worker>
Effort: <supported effort>
Context: <compressed facts, relevant files, commands, or links>
Constraints: <repository rules, user requirements, safety, scope, budget>
Workspace/mode: <read-only or isolated writable worktree>
Do not: <explicit exclusions>
Verify with: <tests, checks, or evidence>
Return: outcome, evidence, changed files, checks, confidence, blockers
```

## Handle Results

Require each delegate to return: outcome and key evidence; changed files, if
any; verification performed and its results; confidence and unresolved
uncertainty; blockers or degraded fallbacks.

Verify important claims against repository tools, tests, or primary sources.
Summarize results instead of forwarding raw transcripts. Between staged
phases, preserve the objective, constraints, accepted plan, diff or result
report, and unresolved risks. If delegation or verification fails after one
corrected retry, stop integration and re-plan.

Treat duration and change size as risk signals, not proof of quality: a fix
that takes unexpectedly long or touches broad architecture deserves more
scrutiny, and a quick fix still requires verification. Ask the user when a
product or safety decision cannot be inferred safely.

## Long-Running Work

For a long-running goal, keep a plan checklist with observable completion
criteria and update it as work lands. A persistence request does not authorize
new external effects: rebasing, closing or merging PRs, changing branches, and
deploying require the user's explicit authority. Preserve human control of
production even when staging and merges are automated.
