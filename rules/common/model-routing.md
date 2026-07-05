# Model Routing

Apply this policy every turn. It selects how work should be executed; it does not assume the current session can switch its own model.

## Local or Delegated

Work locally when the current agent can complete the task reliably without unnecessary coordination.

Use `route-model-work` when delegation materially improves at least one of:

- Specialization or tool access.
- Independent verification.
- Parallel progress on independent work.
- Context reduction through a compressed survey.

Do not orchestrate solely because a task is non-trivial. Higher-priority host policies and user instructions may restrict delegation.

## Capability Roles

Concrete model IDs are preferences, not guarantees. Discover available providers, models, and effort levels before dispatching.

| Role | Use | Preferred order |
| --- | --- | --- |
| **Planner** | Architecture, ambiguous requirements, implementation planning | Fable 5 → Opus 4.8 → GPT-5.5 |
| **Builder** | Implementation, refactoring, tests, repository commands | GPT-5.5 → Opus 4.8 → strongest discovered code-capable model |
| **Reviewer/Judge** | Code review, security review, plan or result evaluation | Fable 5 → Opus 4.8 → GPT-5.5 |
| **Cheap worker** | Search, inventory, log summarization, mechanical checks | Lowest-cost capable OpenCode model → GPT mini → Haiku |

Prefer a different model family for independent review. If unavailable, use the best same-family fallback and disclose the reduced independence.

## Effort

Choose effort from risk and ambiguity, independently of role:

| Effort | Use |
| --- | --- |
| `low` | Mechanical, bounded, easily verified work |
| `medium` | Routine implementation and analysis |
| `high` | Architecture, ambiguity, security, difficult debugging, and review |
| `xhigh` | One narrow, high-stakes decision where extra reasoning has clear value |

Use at most one automatic `xhigh` delegate. Never select `max` or `ultracode` without an explicit user request.

## Skill Guidance

Skill names are advisory signals, not automatic model switches:

- Planning, architecture, adversarial review, security, and code review normally need Planner or Reviewer at `high`.
- Implementation and refactoring normally need Builder at `medium`; raise to `high` only for material complexity or risk.
- Exploration, status checks, documentation, formatting, and mechanical validation normally need Cheap worker at `low`.
- A skill should request delegation only when it needs a specialist, independent judgment, parallel work, or context compression.

Use `route-model-work` for dispatch mechanics, orchestration patterns, limits, fallbacks, and reporting.
