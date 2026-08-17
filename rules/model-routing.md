# Model Routing

Apply this policy every turn. It selects how work should be executed; it does not assume the current session can switch its own model.

## Local or Delegated

Work locally when the current agent can complete the task reliably without unnecessary coordination.

Delegate when doing so materially improves at least one of:

- Specialization or tool access.
- Independent verification.
- Parallel progress on independent work.
- Context reduction through a compressed survey.

Do not orchestrate solely because a task is non-trivial. Higher-priority host policies and user instructions may restrict delegation.

## Capability Roles

Concrete model IDs are preferences, not guarantees. Discover available providers, models, and effort levels before dispatching. If a selected model, variant, or effort is unavailable, use the next capable fallback and disclose it.

| Role               | Use                                                           | Preferred order                                                |
| ------------------ | ------------------------------------------------------------- | -------------------------------------------------------------- |
| **Planner**        | Architecture, ambiguous requirements, implementation planning | Opus 5 → GPT-5.6-sol                                           |
| **Builder**        | Implementation, refactoring, tests, repository commands       | GPT-5.6-luna or GPT-5.6-sol by difficulty → Cursor Auto / Composer via `agent` → Opus 5 → strongest capable model |
| **Reviewer/Judge** | Code review, security review, plan or result evaluation       | Opus 5 → GPT-5.6-sol                                           |
| **Cheap worker**   | Search, inventory, log summarization, mechanical checks       | GPT-5.6-luna → Haiku                                           |

Prefer a different model family for independent review. If unavailable, use the best same-family fallback and disclose the reduced independence.

For Builder, advance down the preferred order only when the current option is unavailable or the user explicitly selects a later one. CLI dispatch lives in the `model-orchestration` skill.

## Builder Routing

On the GPT-5.6 Builder path, pick variant and effort from difficulty:

| Task profile | Model | Effort |
| ------------ | ----- | ------ |
| Bounded, simple-to-medium work | GPT-5.6-luna | `xhigh` by default; `max` when extra depth is worth the latency |
| Medium work with integration or uncertainty through very complex work | GPT-5.6-sol | `medium` for routine work; `high` for complexity, ambiguity, or higher risk |

The medium band overlaps intentionally: choose Luna only when the task is
bounded and easily verified; choose Sol when integration, uncertainty, or
correctness risk matters more than cost.

## Effort

Choose effort from risk and ambiguity, independently of role. Skill names are advisory signals, not automatic model switches.

| Effort   | Use                                                                                                   |
| -------- | ----------------------------------------------------------------------------------------------------- |
| `low`    | Mechanical, bounded, easily verified work: exploration, status, documentation, formatting, validation |
| `medium` | Routine implementation, refactoring, and analysis                                                     |
| `high`   | Architecture, planning, ambiguity, security, adversarial review, code review, difficult debugging     |
| `xhigh`  | One narrow, high-stakes decision or bounded Luna Builder task where extra reasoning has clear value  |
| `max`    | Extra-depth execution for a bounded Builder task routed to Luna when latency and token cost are acceptable |

Use at most one automatic `xhigh` delegate. `max` is allowed only for the
Luna Builder path above; never select `ultracode`. Avoid Luna when latency is
more important than cost.
