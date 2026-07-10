@AGENTS.md

## Personal Preferences

### Commands

- Do not start a development server; assume one is already running.
- Do not run build commands unless specifically requested.
- Prefer focused checks — type checking, linting, and relevant tests — and run them before declaring work complete.

### Code Style

- Prefer concise, simple solutions. If a problem has a materially simpler solution, propose it.

### General

- If a request is too broad to execute reliably at once, stop and say so instead of guessing at scope.

## Model Orchestration

Claude Code-specific mechanics for the model-routing policy imported above.
Where they conflict, this file wins.

Model names are preferences, not guarantees. Before dispatching, discover the
installed CLIs, available models, supported effort levels, and tool access.
Never invent a model ID, provider, effort level, permission mode, or
capability. If a preferred model is unavailable, use the next capable one and
disclose the fallback.

### Model Defaults

Rankings are relative preferences from 1–10; higher is better.

- **Intelligence**: how difficult a problem the model can solve unsupervised.
- **Taste**: judgment in code quality, architecture, API design, UI/UX, and
  copy.
- **Cost**: effective cost efficiency in this environment (constrained usage,
  latency, tokens), not list price. A constraint and tiebreaker, never a
  reason to accept weak output.

| Model               | Cost | Intelligence | Taste | Default work                                                                                       |
| ------------------- | ---: | -----------: | ----: | -------------------------------------------------------------------------------------------------- |
| GPT-5.6 (via Codex) |    9 |            8 |     5 | Implementation, mechanical changes, migrations, data analysis, logs, large documents, computer use |
| Sonnet 5            |    5 |            5 |     6 | Thin Codex wrapper agents and bounded coordination                                                 |
| Opus 4.8            |    4 |            7 |     8 | API/SDK/UI review, user-facing work, independent judgment                                          |
| Fable 5             |    2 |            9 |     9 | Architecture, ambiguous planning, product judgment, final synthesis, difficult review              |

How to apply:

- These are defaults, not limits. You have standing permission to escalate: if
  a cheaper model's output doesn't meet the bar, redo the work with a smarter
  model without asking. Judge the output, not the price tag; escalating costs
  less than shipping mediocre work.
- Use cheaper models to gather evidence and try bounded approaches before
  escalating.
- Cost is a tie-breaker only; when axes conflict for anything that ships, intelligence > taste > cost.
- Bulk or mechanical work with a clear spec (implementation, migrations, data
  analysis) goes to GPT-5.6 — it is very cost effective.
- Anything user-facing (UI, copy, API design) needs taste ≥ 7.
- Review plans and implementations with Fable 5 or Opus 4.8, optionally adding
  GPT-5.6 as an extra cross-family perspective. Never review with Haiku.
- Prefer different model families for independent review. If unavailable, disclose reduced independence.
- If computer use would help complete or verify work, shell out to GPT-5.6
  through Codex.

### Effort

Follow the routing policy's effort table and default Fable to `high` when
the work benefits from it. Reasoning effort controls thought per step, not how
long an agent can continue. Claude wrapper agents may use only `low`, `medium`,
or `high`; do not auto-select `xhigh` for a wrapper.

### Dispatch Mechanics

Use the first capable mechanism:

1. A host-native subagent or workflow with the required model, effort, tools,
   and isolation. Claude models (Sonnet 5, Opus 4.8, Fable 5) run directly via
   the `model` parameter.
2. A non-interactive CLI such as `codex exec` or `claude -p`.
3. Local execution, with any lost specialization or independence disclosed.

Limits: at most three automatic delegates, at most one per role unless scopes
differ, and no duplicate work without a specific reason. Parallelize
independent read-only work; sequence dependent phases. Describe a review as
independent only when another model actually performed it.

#### GPT-5.6 runs only through the Codex CLI

- Entry points are `codex exec` and `codex exec review`
  with `-m gpt-5.6-sol`. In an interactive session, a direct shell call is the
  default path; the wrapper pattern below applies only inside workflows and
  subagents where shell is not first-class.
  For work they don't cover (investigation, data analysis), run
  `codex exec -m gpt-5.6-sol -s read-only` with a self-contained prompt.
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

### Delegation Packet

Send only the context required for the assignment — no whole-codebase dumps or
raw transcripts:

```text
Objective: <specific outcome>
Success criteria: <observable result>
Role: <planner | builder | reviewer/judge | cheap worker>
Context: <compressed facts, relevant files, commands, or links>
Constraints: <repository rules, user requirements, safety, scope, budget>
Workspace/mode: <read-only or isolated writable worktree>
Do not: <explicit exclusions>
Verify with: <tests, checks, or evidence>
Return: outcome, evidence, changed files, checks, confidence, blockers
```

### Calling Codex

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

### Handle Results

Require delegates to return: outcome and key evidence; changed files, if any;
verification and results; confidence and unresolved uncertainty; blockers or
degraded fallbacks.

Verify important claims against repository tools, tests, or primary sources.
Summarize results instead of forwarding raw transcripts. Between staged
phases, preserve the objective, constraints, accepted plan, diff or result
report, and unresolved risks. If delegation or verification fails after one
corrected retry, stop integration and re-plan.

Treat duration and change size as risk signals, not proof of quality: a fix
that takes unexpectedly long or touches broad architecture deserves more
scrutiny, and a quick fix still requires verification. Ask the user when a
product or safety decision cannot be inferred safely.

### Long-Running Work

For a long-running goal, keep a plan checklist with observable completion
criteria and update it as work lands. A persistence request does not authorize
new external effects: rebasing, closing or merging PRs, changing branches, and
deploying require the user's explicit authority. Preserve human control of
production even when staging and merges are automated.
