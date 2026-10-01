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

## Model defaults

Use these workload preferences. They are routing policy, not benchmark claims.
The installed Claude CLI exposes `fable` and `opus` aliases. Verify availability
and resolve any requested exact version against the host before dispatch.

| Model | Identifier | Default work |
| ----- | ---------- | ------------ |
| Fable 5.1 | `claude-fable-5-1` in Claude CLI; discover the host-native ID | Complex implementation, architecture, ambiguous planning; first choice in this tier |
| Opus 5.5 | `claude-opus-5-5` in Claude CLI; discover the host-native ID | Complex implementation and planning when Fable is unavailable; independent review of GPT work |
| GPT-6.1 Sol | `gpt-6.1-sol` | Medium implementation, integration, migrations, debugging, computer use; independent review of Fable or Opus work |
| GPT-6 Luna | `gpt-6-luna` | Simple, bounded implementation, search, inventory, mechanical checks |
| Cursor Auto / Composer | Discover the actual model family | Explicitly requested or unavailable-provider fallback; verify capacity and family before use |
| Sonnet 5.5 | `claude-sonnet-5-5` | Thin CLI wrappers and bounded coordination |

How to apply:

- Route by uncertainty, scope, and correctness risk, not file count. Simple work
  has a clear spec and a cheap, decisive check. Medium work needs integration
  judgment. Complex work crosses architectural boundaries, has ambiguous
  requirements, or carries high blast radius.
- Escalate Luna to Sol, then Sol to Fable or Opus when the work exceeds its tier
  or one corrected retry still fails. Do not keep a complex task on Sol merely
  because the local host only exposes GPT models.
- Fable is preferred to Opus for complex work when both are available. Use Opus
  when Fable is unavailable or explicitly selected. Verify tools and isolation
  before choosing either. Computer use goes to Sol when its tools are required;
  complex design can go to Fable or Opus separately.
- Discover capacity before a fallback. Prefer another capable model in the
  required tier; if only a lower tier is available, disclose the limitation and
  leave work blocked when it cannot meet the requirements reliably.
- User choices override defaults. Never review a delegate's work in that same
  delegate session. Never use Luna or a thin wrapper as the substantive reviewer.

## Capability roles

| Role | Routing |
| ---- | ------- |
| Planner | Fable, then Opus for complex or ambiguous plans; Sol for medium plans; Luna for simple task breakdowns |
| Builder | Luna for simple work; Sol for medium work; Fable, then Opus for complex work |
| Reviewer/Judge | Select from the author's family using the review routing below |
| Cheap worker | Luna for search, inventory, log summaries, and mechanical checks; Sonnet for a CLI wrapper when needed |

## Builder routing

| Task profile | Model | Effort |
| ------------ | ----- | ------ |
| Simple, bounded, clearly specified and easily verified | GPT-6 Luna | `high` for mechanical work; `xhigh` for simple implementation |
| Medium implementation with integration or correctness judgment | GPT-6.1 Sol | `medium`; `high` for uncertainty or elevated risk within this tier |
| Complex implementation, cross-cutting design, deep debugging, high blast radius | Fable, then Opus | `high`, translated to the host's supported effort |

Increasing effort does not replace escalation to the appropriate difficulty tier.

## Review routing

Choose the reviewer's actual model family from the author of each artifact:

| Author | Reviewer |
| ------ | -------- |
| Fable or Opus | GPT-6.1 Sol at `high` |
| GPT Sol or Luna | Fable, then Opus at `high` |

Apply this to plans, implementations, and substantive fixes. Track the actual
model that authored the artifact, including after a fallback; a GPT wrapper
launching Fable makes Fable the author. A role name or CLI is not a model family.
Use a fresh reviewer session with the requirements, artifact, and evidence.

For mixed-family work, split review by authorship when the scopes are separable.
For coupled changes, use one reviewer from each family and give both the full
integration context. For unknown authorship or standalone reviews, prefer Fable,
then Opus; report when cross-family independence cannot be established.

If the opposite family is unavailable, disclose it. Use a fresh, capable
same-family reviewer only as a fallback and label the reduced independence.
Do not describe that result as cross-family review. Explicit user model choices
may override this routing; report the actual model and any lost independence.

## Effort

Choose effort from risk and ambiguity, independently of role. Reasoning effort
controls thought per step, not how long an agent may continue. Skill names are
advisory signals, not automatic model switches.

| Effort   | Use                                                                                                   |
| -------- | ----------------------------------------------------------------------------------------------------- |
| `low`    | Mechanical, bounded, easily verified work: exploration, status, documentation, formatting, validation |
| `medium` | Routine implementation, refactoring, and analysis                                                     |
| `high`   | Architecture, planning, ambiguity, security, adversarial review, code review, difficult debugging     |
| `xhigh`  | One narrow, high-stakes decision where extra reasoning has clear value  |
| `max`    | Extra-depth execution for a bounded Builder task routed to Luna when latency and token cost are acceptable |

Default Planner and Reviewer/Judge roles to `high` when the work benefits from
it. Use at most one automatic `xhigh` delegate. Use `max` only for an explicitly
requested, bounded Luna task; never select an unbounded host mode such as
`ultracode`, or an effort that delegates on its own such as Codex `ultra`.
Verify effort support for the actual model and host. Sol 6.1 supports `low`,
`medium`, `high`, `xhigh`, and `max`; never send it `none` or `minimal`.

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
Launch and quota failures use the separate bounded retry policy in
`model-dispatch`; they are not model-quality failures or unlimited retries.

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
4. **Verify & Fix:** resume the Builder with actionable findings. The Builder
   validates each against the code, confirms, corrects, or rejects it with
   evidence, and fixes only confirmed findings. The Reviewer/Judge inspects the
   fix diff and affected behavior and adjudicates rejected findings. Repeat a
   full review only when scope or affected boundaries changed. Carry confirmed,
   rejected, and unresolved findings forward with their evidence and resulting
   changes in the existing review report.

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
Target: <repo, exact base/head revisions or working-tree diff>
Context: <relevant entry points, governing docs, facts, links>
Checked: <commands already run, results, and revision checked>
Constraints: <scope, user requirements, repository rules, safety, budget>
Style: <code-style rules, quoted, for any file this agent writes>
Workspace: <read-only or isolated writable worktree>
Do not: <explicit exclusions>
Delegation: <terminal worker by default; explicit child scope if needed>
Verify with: <exact allowed checks, required writable paths and network access>
Return: <outcome, evidence, changed files, checks, confidence, blockers>
```

### Instruction inheritance

A delegate does not reliably inherit your instruction files. An in-process
subagent can start without the global `AGENTS.md`; another provider's CLI reads
its own config, not yours. Any rule that shapes written output — comment budget,
naming, dependency policy, test conventions — travels in the packet or it does
not apply.

Quote the rule; never cite it by filename. A delegate that cannot see
`AGENTS.md` cannot open it either, and "follow AGENTS.md" reads as satisfied
without changing anything.

For any assignment that writes code, carry the comment budget verbatim: **one
line, two if the reason needs it, never a paragraph; default zero; no JSDoc on
unexported functions.** It is the rule most often lost in delegation and the
easiest to check in the returned diff — reject output that ignores it rather
than reformatting it yourself.

Pass the accepted plan, result/diff report, and unresolved risks between phases.
For reviews, include prior findings and dispositions. Require only documents
governing the affected behavior; expand reading when evidence warrants it.
Label observed output, supplied claims, and inference. Give evidence artifacts'
generating command and revision, or mark provenance unknown. Verify reproductions
match the production path. Enforce `Return`; summarize rather than relay transcripts.

## Results

Require cited test, repository-tool, or primary-source evidence. Treat broad or
slow fixes as higher-risk and give them additional Reviewer/Judge scrutiny.
Call a result independent only if another model actually produced it.

For persistent goals, track observable completion criteria; persistence never
authorizes rebases, branch changes, closing or merging PRs, deployments, or
other external effects without the user's explicit approval.

Watching background runs, collecting artifacts, and diagnosing a stalled
delegate are `model-dispatch` mechanics.
