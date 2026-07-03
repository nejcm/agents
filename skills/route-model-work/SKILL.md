---
name: route-model-work
description: Route work across Codex, Claude Code, subagents, and cheaper analysis models with a token-efficient delegation policy. Use when asked to design an agent workflow, choose which model should handle coding or codebase-analysis tasks, set fallback behavior between models, orchestrate subagents, reduce token burn, or encode model-priority rules in CLAUDE.md, AGENTS.md, skills, or agent configs.
---

# Route Model Work

## Routing Policy

Use a skill or lightweight routing section for recurring delegation policy. Use a full workflow only when there are durable handoffs, required artifacts, or deterministic validation gates.

Default to the cheapest reliable path:

1. Keep Fable on `high` effort by default.
2. Avoid `xhigh`, `max`, and `extra` unless the user explicitly asks or the task has a clear quality reason that justifies the token cost.
3. Use Codex as the fallback or implementation executor for coding tasks where precise steering, repo edits, tests, and local command execution matter.
4. Use cheaper or specialized models for token-hungry discovery such as broad codebase analysis, web or computer-use research, log summarization, and first-pass inventory.
5. Report distilled findings back to Fable or the primary orchestrator instead of forwarding raw transcripts.

## Decision Tree

Classify the request before selecting a model:

- **Implementation or repo edits**: delegate to Codex/GPT-5.5-style coding agent. Give exact goal, constraints, files, tests, and expected output. Ask for a concise result report.
- **Architecture, strategy, or ambiguous planning**: keep with Fable on `high`, then delegate concrete implementation slices to Codex when ready.
- **Broad codebase survey**: use a cheaper model or subagent to map files, symbols, risks, and candidate touchpoints. Feed back only the compressed map and confidence gaps.
- **Computer use or browser-heavy work**: use another capable tool/model first. Return screenshots, URLs, form state, extracted facts, and unresolved blockers.
- **Review or verification**: use Codex for local tests and diffs; use a separate reviewer only when independent judgment is useful.
- **High-stakes or uncertain current facts**: browse or use authoritative docs first, then route implementation separately.

## Delegation Packet

When delegating, send only the minimum context needed:

- Objective and success criteria.
- Relevant files, commands, or links.
- Constraints from AGENTS.md, CLAUDE.md, user preferences, and repo rules.
- What not to spend tokens on.
- Required verification.
- Expected response shape.

Prefer this prompt shape:

```text
Task: <specific outcome>
Context: <compressed facts only>
Constraints: <style, safety, routing, token budget>
Work locally with the available tools. Do not broaden scope.
Verify with: <tests/checks>
Return: changed files, verification result, blockers only.
```

## Reporting Back

Return summaries, not transcripts:

- Decision made and why.
- Delegated target and effort level.
- Findings, changed files, tests, and blockers.
- Residual uncertainty.

Do not hide failures, uncertainty, or skipped validation. If the requested model/tool is unavailable, say so and use the nearest available fallback.

## Anti-Patterns

- Do not use expensive effort levels for routine implementation.
- Do not send whole-codebase dumps to premium models.
- Do not ask Fable to perform exhaustive tool-heavy exploration when a cheaper worker can summarize it.
- Do not preserve model outputs uncritically; verify important claims with tools, tests, or primary sources.
- Do not create multi-agent choreography for tasks one local coding agent can finish directly.
