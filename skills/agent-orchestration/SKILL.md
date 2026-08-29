---
name: agent-orchestration
description: Decide whether to delegate work to another model and how to structure it — model defaults, capability roles, effort selection, delegation patterns, staged plan/build/review/fix phases, delegation packets, and independent review. Use whenever work may be handed to another model or split across several agents.
---

# Agent Orchestration

This skill decides **which** model, role, and effort a piece of work gets, and
how work is structured across agents. The `model-dispatch` skill explains
**how** to call each provider CLI once that decision is made — read it before
the first delegated call. User and repository instructions override both.

Model names here are preferences, not guarantees. Discover the available
providers, models, and effort levels before dispatching; if a selected model,
variant, or effort is unavailable, use the next capable fallback and disclose
it.

## Local or Delegated

Work locally when the current agent can complete the task reliably without
unnecessary coordination.

Delegate when doing so materially improves at least one of:

- Specialization or tool access.
- Independent verification.
- Parallel progress on independent work.
- Context reduction through a compressed survey.

Do not orchestrate solely because a task is non-trivial. Higher-priority host
policies and user instructions may restrict delegation.

## Model Defaults

Rankings are relative preferences from 1–10; higher is better.

- **Intelligence**: how difficult a problem the model can solve unsupervised.
- **Taste**: judgment in code quality, architecture, API design, UI/UX, and
  copy.
- **Cost**: effective cost efficiency in this environment (constrained usage,
  latency, tokens), not list price. A constraint and tiebreaker, never a
  reason to accept weak output.

| Model                  | Invoke via                            | Cost | Intelligence | Taste | Default work                                                                                   |
| ---------------------- | ------------------------------------- | ---: | -----------: | ----: | ---------------------------------------------------------------------------------------------- |
| GPT-5.6                | `codex exec`, or native inside Codex  |    9 |            8 |     5 | Preferred Builder; implementation, mechanical changes, migrations, data analysis, computer use |
| Cursor Auto / Composer | `agent -p`, or native inside Cursor   |    8 |            7 |     6 | Fallback Builder when Codex is unavailable or explicitly requested                             |
| Sonnet 5               | host-native subagent, or `claude -p`  |    5 |            5 |     6 | Thin Builder-CLI wrapper agents and bounded coordination                                       |
| Opus 5                 | host-native subagent, or `claude -p`  |    4 |            7 |     8 | API/SDK/UI review, user-facing work, independent judgment, architecture, ambiguous planning    |

How to apply:

- These are defaults, not limits. You have standing permission to escalate: if
  a cheaper model's output doesn't meet the bar, redo the work with a smarter
  model without asking. Judge the output, not the price tag; escalating costs
  less than shipping mediocre work.
- Use cheaper models to gather evidence and try bounded approaches before
  escalating.
- Cost is a tie-breaker only; when axes conflict for anything that ships,
  intelligence > taste > cost.
- Bulk or mechanical work with a clear spec (implementation, migrations, data
  analysis) goes to GPT-5.6 — it is very cost effective.
- Anything user-facing (UI, copy, API design) needs taste ≥ 7.
- Review plans and implementations with Opus 5, optionally adding GPT-5.6 as an
  extra cross-family perspective. Never review with Haiku.
- Do not use the Builder to review its own diff.
- If computer use would help complete or verify work, dispatch to GPT-5.6
  through Codex.

## Capability Roles

| Role               | Use                                                           | Preferred order                                                |
| ------------------ | ------------------------------------------------------------- | -------------------------------------------------------------- |
| **Planner**        | Architecture, ambiguous requirements, implementation planning | Opus 5 → GPT-5.6-sol                                           |
| **Builder**        | Implementation, refactoring, tests, repository commands       | GPT-5.6-luna or GPT-5.6-sol by difficulty → Cursor Auto / Composer via `agent` → Opus 5 → strongest capable model |
| **Reviewer/Judge** | Code review, security review, plan or result evaluation       | Opus 5 → GPT-5.6-sol                                           |
| **Cheap worker**   | Search, inventory, log summarization, mechanical checks       | GPT-5.6-luna → Haiku                                           |

Prefer a different model family for independent review. If unavailable, use the
best same-family fallback and disclose the reduced independence.

For Builder, advance down the preferred order only when the current option is
unavailable or the user explicitly selects a later one.

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

Choose effort from risk and ambiguity, independently of role. Reasoning effort
controls thought per step, not how long an agent may continue. Skill names are
advisory signals, not automatic model switches.

| Effort   | Use                                                                                                   |
| -------- | ----------------------------------------------------------------------------------------------------- |
| `low`    | Mechanical, bounded, easily verified work: exploration, status, documentation, formatting, validation |
| `medium` | Routine implementation, refactoring, and analysis                                                     |
| `high`   | Architecture, planning, ambiguity, security, adversarial review, code review, difficult debugging     |
| `xhigh`  | One narrow, high-stakes decision or bounded Luna Builder task where extra reasoning has clear value  |
| `max`    | Extra-depth execution for a bounded Builder task routed to Luna when latency and token cost are acceptable |

Default Planner and Reviewer/Judge roles to `high` when the work benefits from
it. Use at most one automatic `xhigh` delegate. `max` is allowed only for the
Luna Builder path above; never select an unbounded host mode such as
`ultracode`. Avoid Luna when latency is more important than cost.

A wrapper agent — one that only launches another CLI and returns its artifact —
gets the cheapest model that can drive a CLI reliably, at `low` or `medium`.
The reasoning belongs in the delegate, not in the process that shells out to
it; never auto-select `xhigh` for a wrapper. Hosts may cap effort further than
this table allows.

## Choosing a Pattern

At each dispatch, confirm through `model-dispatch` that the chosen mechanism
supports the model, effort, tools, and isolation needed. Prefer:

1. A capable host-native subagent/workflow.
2. A non-interactive CLI of a *different* host — see the reference table in
   `model-dispatch`.
3. Local work, disclosing any lost specialization or independent review.

Local fallback is unavailable during the staged workflow below, where phase
independence is part of the contract.

Use the smallest useful pattern:

- **Specialist** — one bounded task needing distinct expertise or tools.
- **Fan-out** — independent, read-only surveys or reviews; synthesize after.
- **Staged implementation** — plan → build → independent review → fix and
  re-verify.
- **Second opinion** — preferably a cross-family challenge for a consequential,
  disputed, low-confidence, or hard-to-reverse decision. Disclose when only a
  same-family fallback is available.

A single delegated call needs no pattern at all — dispatch it and stop.

## Running the Fleet

Parallelize only independent work. Keep dependent phases sequential. Use no
more than three distinct automatic delegates and at most one per role unless
scopes differ. Avoid duplicate assignments and resume the Builder for fixes
rather than creating a fourth worker. Resume an interrupted delegate by id/name
to preserve context.

Give genuinely wrong output one corrected retry, then stop and re-plan.
Invocation, sandbox, timeout, or infrastructure failures require fixing the
launch rather than spending that retry.

## Staged Implementation

Use the full staged pattern only when independent review materially reduces
risk. In that pattern, the current session coordinates only: it dispatches,
passes artifacts, resumes agents, tracks progress, requests decisions, and
reports. It does not inspect or edit implementation files, author or adjudicate
phase work, perform review, apply fixes, or run verification. Phase agents
perform all repository inspection, planning, edits, review, and checks.

1. **Plan:** forward an already accepted executable plan, otherwise assign a
   Planner to produce scope, success criteria, risks, and checks.
2. **Build:** assign a Builder to the accepted scope; require changed files and
   executed checks.
3. **Review:** assign an independent Reviewer/Judge with the plan and diff to
   review requirements, repository rules, and correctness.
4. **Verify and Fix:** resume the Builder for actionable findings. Have the Reviewer/Judge
   inspect every fix diff and relevant check; resume a full second review when
   fixes are material or touch logic.

Commit after each phase that changed the repository, once its checks pass, in
the orchestrator and scoped to that phase, so phases stay separately
reviewable and revertable. Never push or open a PR without explicit approval.

Do not have a Builder decide objections to its own review. The Reviewer/Judge
adjudicates disputed findings. Ask the user when a product or safety decision
cannot be inferred. Direct coordination the user explicitly authorizes (such as
committing or pushing) may run in the orchestrator.

## Delegation Packet

Send only the context needed to complete and verify the assignment:

```text
Objective: <specific outcome>
Success criteria: <observable result>
Role / effort: <selected above>
Context: <compressed relevant files, facts, commands, links>
Constraints: <scope, user requirements, repository rules, safety, budget>
Workspace: <read-only or isolated writable worktree>
Do not: <explicit exclusions>
Verify with: <tests, checks, evidence>
Return: <outcome, evidence, changed files, checks, confidence, blockers>
```

Pass the accepted plan, result/diff report, and unresolved risks between
phases. Enforce the `Return` contract and summarize results rather than relaying
transcripts.

## Results

Require cited test, repository-tool, or primary-source evidence. Treat broad or
slow fixes as higher-risk and give them additional Reviewer/Judge scrutiny.
Call a result independent only if another model actually produced it.

For persistent goals, track observable completion criteria; persistence never
authorizes rebases, branch changes, closing or merging PRs, deployments, or
other external effects without the user's explicit approval.

Watching background runs, collecting artifacts, and diagnosing a stalled
delegate are `model-dispatch` mechanics.
