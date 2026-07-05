---
name: route-model-work
description: Route work across models and providers using capability roles, risk-based effort, live discovery, safe delegation patterns, and structured result handling. Use when dispatching a subagent, coordinating parallel work, running plan/build/judge, obtaining independent judgment, or encoding orchestration behavior.
---

# Route Model Work

This skill executes delegation. The always-on `@rules/model-routing.md` rule owns role, effort, and model preferences.

## Dispatch Order

Use the first available mechanism:

- **Host-native subagent tool** — use when it supports the required role, model, effort, and isolation.
- **Non-interactive CLI** — use an installed `codex exec` or `claude -p` only when the required settings can be represented safely.
- **Local execution** — continue locally when capable; disclose that delegation or model independence was unavailable.

Never guess a provider, model ID, effort option, or mode.

## Orchestration Patterns

Choose the smallest pattern that provides the needed benefit:

- **Specialist delegate** — one bounded task requiring different expertise or tools.
- **Parallel fan-out** — independent read-only surveys or reviews, followed by synthesis.
- **Plan → build → judge** — high-risk or ambiguous work needs independent evaluation after implementation.
- **Second opinion** — a read-only, cross-family challenge to a material decision or conclusion.

For cross-family staged work, assign each family the role it is strongest at, keep phases sequential, and prevent self-review. If a requested family is unavailable, use the next capable model and disclose the reduced independence (Example: ask Fable to produce an implementation plan, ask GPT to implement the accepted plan, then ask Fable to review the diff against the plan and repo rules).

Do not use plan → build → judge as a default for all non-trivial work.

Use a second opinion when explicitly requested or when a decision is high-impact, disputed, difficult to reverse, security-sensitive, or supported with low confidence. Never claim a second opinion unless a separate model actually ran.

## Automatic Limits

Unless the user specifies another budget:

- Use at most three delegates.
- Use at most one `xhigh` delegate.
- Do not create duplicate roles without a distinct question or scope.
- Retry a failed delegation once with a concrete correction, then stop and re-plan.
- Run independent read-only delegates in parallel; run dependent phases sequentially.

## Delegation Packet

Send only the context needed for the assigned task:

```text
Objective: <specific outcome>
Success criteria: <observable result>
Role: <planner | builder | reviewer/judge | cheap worker>
Effort: <supported effort>
Context: <compressed facts, relevant files, commands, or links>
Constraints: <repo rules, user requirements, safety, scope, budget>
Workspace/mode: <read-only or isolated edit workspace>
Do not: <explicit exclusions>
Verify with: <tests, checks, or evidence>
Return: outcome, evidence, changed files, checks, confidence, blockers
```

Do not send whole-codebase dumps or raw transcripts when a focused packet is sufficient.

## Result Handling

Require each delegate to return:

- Outcome and key evidence.
- Changed files, if any.
- Verification performed and results.
- Confidence and unresolved uncertainty.
- Blockers or degraded fallbacks.

The orchestrator must check important claims against repository tools, tests, or primary sources. Summarize results instead of forwarding transcripts.

For staged patterns, compact context only between phases and only under real context pressure. Preserve the objective, constraints, accepted plan, diff or result report, and unresolved risks.

## Failure Handling

- If the preferred model is unavailable, discover and use the next capable mapping from `model-routing.md`.
- If cross-family review is unavailable, use a same-family reviewer and disclose reduced independence.
- If a delegate fails, correct the packet or choose a supported fallback for one retry.
- If verification fails or the retry fails, stop integration and re-plan.
