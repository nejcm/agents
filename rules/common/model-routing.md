# Model Routing

Defaults apply every turn. Override only with an explicit reason.

- **Effort levels:** Fable on `high` by default. `xhigh` only for the narrow planner/judge roles in three-phase work (below). Avoid `max`/`extra` — token-hungry with worse outputs.
- **Model priority:**
  - Fable — orchestrate, plan, judge, ambiguous architecture.
  - Codex / GPT-5.5 — default coder for implementation, repo edits, tests, local commands. Steerable, cheap, and fast even at `high`.
  - Cheaper / specialized models — token-hungry discovery: broad codebase survey, computer use, browser work, log summarization, first-pass inventory.
- **Report distilled findings back to Fable, never raw transcripts.**
- **Non-trivial work → three-phase:** Fable `high` plan → GPT 5.5 `high` code → Fable `high` judge. Economics: plan + judge cost ~few $ vs. $50+ for full round trips on Fable alone.
- **Don't choreograph multi-agent dances for tasks one local coding agent can finish directly.**
- See the `route-model-work` skill for the delegation packet, decision tree, and execution procedure.
