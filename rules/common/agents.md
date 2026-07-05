# Agent Orchestration

Agents in `~/.claude/agents/`: planner, architect, tdd-guide, code-reviewer, security-reviewer, build-error-resolver, e2e-runner, refactor-cleaner, doc-updater, rust-reviewer.

- Follow `model-routing.md` to decide whether delegation is justified and to select a capability role and effort.
- Use the `route-model-work` skill for dispatch, parallelism, workspace isolation, verification, and result handling.
- Do not assume every complex task needs multiple agents.
