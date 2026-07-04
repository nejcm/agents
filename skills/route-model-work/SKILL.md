---
name: route-model-work
description: Execute cross-model delegation — the decision tree, delegation packet, reporting shape, and three-phase plan→code→judge procedure for routing work between Fable, Codex/GPT-5.5, and cheaper analysis models. Use when asked to actually orchestrate a delegation, run a plan→code→judge round-trip, build a delegation prompt, classify a task for routing, or encode the delegation procedure in agent configs. For always-on routing defaults see the model-routing rule.
---

# Route Model Work

Procedural companion to the `model-routing` rule. The rule holds defaults; this skill holds how to execute.

## Decision Tree

Classify the request before selecting a model:

- **Implementation or repo edits**: delegate to Codex / GPT-5.5. Give exact goal, constraints, files, tests, and expected output. Ask for a concise result report.
- **Architecture, strategy, or ambiguous planning**: keep with Fable on `high`; delegate concrete implementation slices to Codex when ready.
- **Broad codebase survey**: use a cheaper model or subagent to map files, symbols, risks, and candidate touchpoints. Feed back only the compressed map and confidence gaps.
- **Computer use or browser-heavy work**: use another capable tool/model first. Return screenshots, URLs, form state, extracted facts, and unresolved blockers.
- **Review or verification**: Codex for local tests and diffs; a separate Fable judge pass only when independent judgment is useful.
- **High-stakes or uncertain current facts**: browse or use authoritative docs first, then route implementation separately.

## Three-Phase Procedure (non-trivial work)

Run when the task needs quality and a single pass won't suffice. Per the `model-routing` rule, this is the default for non-trivial work.

1. **Plan (Fable `high`)** — produce the objective, constraints, touchpoints, success criteria, and a concrete implementation slice list. No code edits here.
2. **Code (GPT 5.5 `high`)** — hand each slice to Codex with a delegation packet (below). Codex works locally: edits, runs tests, verifies. Returns changed files, test result, blockers only.
3. **Judge (Fable `high`)** — review diffs and verification against the plan. Approve, request changes, or re-plan. Do not redo implementation; re-delegate if needed.

Cost target: plan + judge in the ~few-dollar range. If a phase is burning tokens without progress, stop and re-plan rather than push through.

## Context Management

The three-phase procedure has natural compact points between phases:

- After **Plan** produces its slice list, compact before handing to **Code** while keeping the plan.
- After **Code** returns, the judge needs only the plan plus the diff/report — compact if the plan phase accumulated exploration context.
- Never compact mid-phase.

Compact only when context pressure is real (~125k tokens or ~60% of the window).

## Delegation Packet

Send only the minimum context needed:

- Objective and success criteria.
- Relevant files, commands, or links.
- Constraints from AGENTS.md, CLAUDE.md, user preferences, and repo rules.
- What not to spend tokens on.
- Required verification.
- Expected response shape.

Prompt shape:

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




## Orchestration

- **Effort levels:** Fable on `high` by default. `xhigh` only for the narrow planner/judge roles in three-phase work (below). Avoid `max`/`extra` — token-hungry with worse outputs.
- **Model priority:**
  - Fable — orchestrate, plan, judge, ambiguous architecture.
  - Codex / GPT-5.5 — default coder for implementation, repo edits, tests, local commands. Steerable, cheap, and fast even at `high`.
  - Cheaper / specialized models — token-hungry discovery: broad codebase survey, computer use, browser work, log summarization, first-pass inventory.
- **Report distilled findings back to Fable, never raw transcripts.**
- **Non-trivial work → three-phase:** Fable `high` plan → GPT 5.5 `high` code → Fable `high` judge. Economics: plan + judge cost ~few $ vs. $50+ for full round trips on Fable alone.
- **Don't choreograph multi-agent dances for tasks one local coding agent can finish directly.**
- See the `route-model-work` skill for the delegation packet, decision tree, and execution procedure.
