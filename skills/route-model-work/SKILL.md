---
name: route-model-work
description: Route work across models and providers using capability roles, risk-based effort, live discovery, safe delegation patterns, and structured result handling. Use when dispatching a subagent, coordinating parallel work, running plan/build/judge, obtaining independent judgment, or encoding orchestration behavior.
---

# Route Model Work

This skill executes delegation. The always-on `model-routing` rule owns role, effort, and model preferences.

## Decide Whether to Delegate

Keep work local unless delegation materially improves specialization, independent verification, parallel progress, or context reduction.

When delegation helps:

1. Select the minimum sufficient orchestration pattern.
2. Assign each delegate one capability role and a risk-based effort.
3. Discover supported providers, models, efforts, and modes.
4. Dispatch with least privilege and a bounded packet.
5. Verify and integrate results; do not accept model output uncritically.

## Dispatch Order

Use the first available mechanism:

- **Host-native subagent tool** — use when it supports the required role, model, effort, and isolation.
- **Non-interactive CLI** — use an installed `codex exec` or `claude -p` only when the required settings can be represented safely.
- **Local execution** — continue locally when capable; disclose that delegation or model independence was unavailable.

Never guess a provider, model ID, effort option, or mode. Use the nearest supported fallback and report any degraded capability, effort, or independence.

## Permissions and Workspaces

- Planner, reviewer, judge, survey, and second-opinion delegates are read-only.
- Builders receive only the edit-capable mode required for their task.
- Bypass, full-access, or equivalent modes require explicit user authorization.
- Use one writer in the active workspace.
- Parallel delegates are read-only by default.
- Parallel builders require isolated worktrees and explicit integration.

## Orchestration Patterns

Choose the smallest pattern that provides the needed benefit:

- **Specialist delegate** — one bounded task requiring different expertise or tools.
- **Parallel fan-out** — independent read-only surveys or reviews, followed by synthesis.
- **Plan → build** — ambiguous work needs a plan before one builder implements it.
- **Plan → build → judge** — high-risk work needs independent evaluation after implementation.
- **Second opinion** — a read-only, cross-family challenge to a material decision or conclusion.

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

## Anti-Patterns

- Expensive effort for routine, easily verified work.
- Multiple agents when one local agent can finish reliably.
- Multiple writers in one workspace.
- Premium models performing broad mechanical discovery.
- Reviewer and builder sharing a model family when independent judgment is material and an alternative is available.
- Hidden failures, skipped checks, unsupported settings, or silent fallbacks.
