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

Concrete model IDs are preferences, not guarantees. Discover available providers, models, and effort levels before dispatching.

| Role | Use | Preferred order |
| --- | --- | --- |
| **Planner** | Architecture, ambiguous requirements, implementation planning | Fable 5 → GPT-5.5 → Opus 4.8 |
| **Builder** | Implementation, refactoring, tests, repository commands | GPT-5.5 → Opus 4.8 → strongest discovered code-capable model |
| **Reviewer/Judge** | Code review, security review, plan or result evaluation | Fable 5 → Opus 4.8 → GPT-5.5 |
| **Cheap worker** | Search, inventory, log summarization, mechanical checks | Lowest-cost capable OpenCode model → GPT mini → Haiku |

Prefer a different model family for independent review. If unavailable, use the best same-family fallback and disclose the reduced independence.

## Effort

Choose effort from risk and ambiguity, independently of role. Skill names are advisory signals, not automatic model switches.

| Effort | Use |
| --- | --- |
| `low` | Mechanical, bounded, easily verified work: exploration, status, documentation, formatting, validation |
| `medium` | Routine implementation, refactoring, and analysis |
| `high` | Architecture, planning, ambiguity, security, adversarial review, code review, difficult debugging |
| `xhigh` | One narrow, high-stakes decision where extra reasoning has clear value |

Use at most one automatic `xhigh` delegate. Never select `max` or `ultracode` without an explicit user request. Request delegation only for a specialist, independent judgment, parallel work, or context compression. Follow platform-specific instructions for dispatch mechanics, orchestration patterns, limits, fallbacks, and reporting.
