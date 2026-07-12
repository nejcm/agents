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

### Execution mechanics

Dispatch order, orchestration patterns, the Codex CLI (`codex exec` /
`codex exec review`), the wrapper pattern for running GPT-5.6, delegation
packets, result handling, and long-running work live in the
`model-orchestration` skill. Load it when implementing a plan or approved
design, when starting a medium-to-high complexity task, or when delegating,
parallelizing, or shelling out to Codex. The platform-agnostic routing policy
(roles, effort, model preferences) stays in `@rules/model-routing.md`.
