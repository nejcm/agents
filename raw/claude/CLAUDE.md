@AGENTS.md

# Personal Preferences

## Commands

- Do not start a development server; assume it is already running.
- Do not run build commands unless specifically requested.
- Prefer focused checks such as type checking, linting, and relevant tests.

## Code Style

- Prefer concise, simple solutions.
- If a problem has a materially simpler solution, propose it.

## General

- If a request is too broad to execute reliably at once, stop and state that
  clearly.
- If computer use would help complete or verify work, shell out to GPT-5.5
  through Codex.

# Model Orchestration

Use these instructions when choosing models, subagents, workflows, or external
CLIs. They override generic model-routing defaults for Claude Code.

## Terms

- **Intelligence**: how difficult a problem a model can solve unsupervised.
- **Taste**: judgment in code quality, architecture, API design, UI/UX, and copy.
- **Cost**: total constrained usage, latency, and token consumption. Treat it as
  a constraint and tiebreaker, not a reason to accept weak output.

Use cheaper models to gather evidence and try bounded approaches before
escalating.

## Model Defaults

Model names are preferences, not guarantees. Before dispatching, discover the
installed CLI, available models, supported effort levels, and tool access. Never
invent a model ID, provider, effort, permission mode, or capability.

Rankings are relative preferences from 1–10; higher is better. Cost means
effective cost efficiency for this environment, not list price.

| Model                 | Cost | Intelligence | Taste | Default work                                                                                         |
| --------------------- | ---: | -----------: | ----: | ---------------------------------------------------------------------------------------------------- |
| GPT-5.5 through Codex |    9 |            8 |     5 | Implementation, mechanical changes, migrations, data analysis, logs, large documents, computer use  |
| Sonnet 5              |    5 |            5 |     7 | Thin Claude wrappers and bounded coordination                                                        |
| Opus 4.8              |    4 |            7 |     8 | API/SDK/UI review, user-facing work, and independent judgment                                        |
| Fable 5               |    2 |            9 |     9 | Architecture, ambiguous planning, product judgment, final synthesis, and difficult review            |

How to apply:
- These are defaults, not limits. You have standing permission to override them: if a cheaper model's output doesn't meet the bar, rerun or redo the work with a smarter model without asking. Judge the output, not the price tag. Escalating costs less than shipping mediocre work.
- Cost is a tie-breaker only; when axes conflict for anything that ships, intelligence > taste > cost.
- Bulk/mechanical work (clear-spec implementation, data analysis, migrations): gpt-5.5 - it's effectively free.
- Anything user-facing (UI, copy, API design) needs taste ≥ 7.
- Reviews of plans/implementations: fable-5 or opus-4.8, optionally gpt-5.5 as an extra independent perspective. Never use Haiku.
- Prefer different model families for independent review. If unavailable, disclose reduced independence.
- Mechanics: gpt-5.5 is only reachable through the Codex CLI- `codex exec`/`codex review` (my ~/.codex/config.toml defaults to gpt-5.5). Use the codex-implementation, codex-review, and codex-computer-use skills for work they don't cover (investigation, data analysis), run `codex exec -s read-only` directly with a self-contained prompt.
- Claude models (sonnet-5, opus-4.8, fable-5) run via the Agent/Workflow model parameter. Using gpt-5.5 inside workflows and subagents (the model parameter only takes Claude models, so use a wrapper):
- Spawn a thin Claude wrapper agent with `model: 'sonnet', effort: 'low'` whose prompt instructs it to write self-contained codex prompt, run `codex exec` via Bash, and return the report (use `schema` on the wrapper to get structured output back).
- Always label these agents with a `gpt-5.5:` prefix, e.g. `{label: 'gpt-5.5: review-auth'}` the workflow UI shows the wrapper's Claude model, so the label is the only indication the real worker is gpt-5.5.
- Codex runs can exceed Bash's 10-minute timeout: pass an explicit timeout, or run in the background and poll for the report file.
- Parallel gpt-5.5 implementation agents must use `isolation: 'worktree'` so codex edits don't collide in the shared checkout.
- Workflow token budgets only count Claude tokens; codex work is free and invisible to `budget.spent()`.

## Effort

Use `low`, `medium`, or `high`. Default to `high` for Fable when the work
benefits from it. Reasoning effort controls thought per step, not how long the
agent can continue. Do not automatically use `xhigh`, `max`, or `ultracode`. Use one only
when the user explicitly requests it.


---

## Decide Whether to Delegate

Work locally when the current agent can complete the task reliably. Delegate
only when it materially adds:

- specialized expertise or tool access;
- independent verification;
- parallel progress on independent work; or
- context reduction through a compressed survey.

Use the first capable mechanism:

1. A host-native subagent with the required model, effort, tools, and isolation.
2. A non-interactive CLI such as `codex exec` or `claude -p`.
3. Local execution, with any lost specialization or independence disclosed.

Do not orchestrate merely because a task is large. Use at most three automatic
delegates, at most one delegate per role unless scopes differ, and no duplicate
work without a specific reason. User instructions and host limits take
precedence.

## Choose the Smallest Pattern

- **Specialist**: one bounded task needing different expertise or tools.
- **Parallel fan-out**: independent read-only surveys or reviews, then synthesis.
- **Plan → build → judge**: sequential phases for ambiguous or high-risk work,
  with different agents for building and judging.
- **Second opinion**: a read-only cross-family challenge to a high-impact,
  disputed, security-sensitive, hard-to-reverse, or low-confidence decision.

Never claim independent review unless another model actually ran. Do not make
plan → build → judge the default for every non-trivial task.

## Subagents and Workflows

A subagent handles one bounded assignment. A workflow is a deterministic,
programmatic multi-stage pipeline whose later stages depend on earlier results.

- Invent agent roles for the task; do not force every problem into fixed
  reviewer, adversary, or explorer archetypes.
- Use workflows for fan-out, classification, and repeatable verification.
- Use the parent session to orchestrate checkpoint-driven programs. Do not put
  an umbrella project into one workflow when each stream needs CI, review,
  product decisions, rebases, or merges between stages.
- Run independent read-only work in parallel. Run dependent phases
  sequentially.
- Isolate concurrent edits in worktrees and combine them only after checking
  overlap, conflicts, tests, and ownership.
- Inside a Claude-only workflow, use a thin wrapper agent with
  `model: 'sonnet'` and `effort: 'low'`. Its prompt must create a self-contained
  Codex prompt, run `codex exec` through Bash, and return the report. Use the
  wrapper's `schema` option when structured output is useful.
- Prefix every Codex-backed wrapper label with `gpt-5.5:`, for example
  `{label: 'gpt-5.5:review-auth'}`. The workflow UI shows the wrapper's Claude
  model, so the label identifies the real worker.
- A Codex run may exceed Bash's 10-minute timeout. Set an explicit longer
  timeout, or run it in the background and poll for its report artifact.
- Parallel GPT-5.5 implementation wrappers must use `isolation: 'worktree'` so
  their edits cannot collide in the shared checkout.
- Workflow token budgets count Claude wrapper tokens, not Codex work. Codex
  usage is not represented by `budget.spent()`; track it separately when a
  budget matters.

For a long-running goal, keep a repository TODO with observable completion
criteria and update it as work lands. A persistence request does not authorize
new external effects. Rebasing, closing or merging PRs, changing branches, and
deploying require the user's explicit authority. Preserve human control of
production even when staging and merges are automated.

## Delegation Packet

Send only the context required for the assignment:

```text
Objective: <specific outcome>
Success criteria: <observable result>
Role: <planner | builder | reviewer/judge | cheap worker>
Effort: <supported low | medium | high>
Context: <compressed facts, relevant files, commands, or links>
Constraints: <repository rules, user requirements, safety, scope, budget>
Workspace/mode: <read-only or isolated writable worktree>
Do not: <explicit exclusions>
Verify with: <tests, checks, or evidence>
Return: outcome, evidence, changed files, checks, confidence, blockers
```

Do not send whole-codebase dumps or raw transcripts when focused context is
enough.

## Calling Codex

Verify syntax with the installed `codex --help`, `codex exec --help`, and
`codex exec review --help`. Use a self-contained, direct prompt; do not prompt
Codex as if it were Claude.

Use an artifact file so the result survives long runs and wrapper timeouts:

```bash
codex exec -m gpt-5.5 -C "$PWD" -s read-only \
  -o "$ARTIFACT_DIR/result.md" "<focused investigation prompt>"
```

For a bounded implementation, use an isolated worktree and `-s workspace-write`.
State the permitted files, required behavior, exclusions, and verification.
Never give parallel writers the same worktree.

For review, select exactly one target:

```bash
codex exec review -m gpt-5.5 --uncommitted \
  -o "$ARTIFACT_DIR/review.md" "<review focus>"
codex exec review -m gpt-5.5 --base <branch> \
  -o "$ARTIFACT_DIR/review.md" "<review focus>"
codex exec review -m gpt-5.5 --commit <sha> \
  -o "$ARTIFACT_DIR/review.md" "<review focus>"
```

For runtime or computer-use work, state the flow, environment, expected
evidence, screenshot or video requirements, and whether edits are allowed.
Confirm that the invoked Codex environment actually has the needed tools; CLI
availability alone does not prove computer-use availability.

Codex tasks can outlive a wrapper timeout. On timeout, inspect the process and
artifact before retrying. Retry once with a concrete correction, then re-plan.
If a review finds no issue, accept that result when the target was inspected;
do not rerun merely to force findings. Reports must name the inspected target
and say clearly when there are no findings.

## Handle Results

Require delegates to return:

- outcome and key evidence;
- changed files, if any;
- verification and results;
- confidence and unresolved uncertainty; and
- blockers or degraded fallbacks.

Verify important claims against repository tools, tests, or primary sources.
Summarize results instead of forwarding raw transcripts. Between staged phases,
preserve the objective, constraints, accepted plan, diff or result report, and
unresolved risks.

If a preferred model is unavailable, use the next capable model and disclose
the fallback. If cross-family review is unavailable, use a same-family reviewer
and disclose reduced independence. If delegation or verification fails after
one corrected retry, stop integration and re-plan.

Treat duration and change size as risk signals, not proof of quality. A fix that
takes unexpectedly long or touches broad architecture deserves more scrutiny;
a quick fix still requires verification. Ask the user when a product or safety
decision cannot be inferred safely.
