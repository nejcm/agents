---
name: model-orchestration
description: Multi-model dispatch for Claude Code — delegation patterns, Builder CLI selection (Codex, `agent`), task packets, long-running runs, and independent review.
disable-model-invocation: true
---

# Model Orchestration

`model-routing` decides roles, effort, preferred models, independence, and
fallbacks. This skill supplies the dispatch mechanics. User and repository
instructions override both.

## Dispatch

At each dispatch, apply `model-routing`, then confirm that the chosen mechanism
supports the model, effort, tools, and isolation needed. Prefer:

1. A capable host-native subagent/workflow.
2. A non-interactive CLI (`codex exec` for the default Builder, `agent` for the
   Cursor Auto/Composer fallback, or `claude -p`).
3. Local work, disclosing any lost specialization or independent review.

Never invent a capability or identifier. Local fallback is unavailable during
the staged workflow below, where phase independence is part of the contract.

Use the smallest useful pattern:

- **Specialist** — one bounded task needing distinct expertise or tools.
- **Fan-out** — independent, read-only surveys or reviews; synthesize after.
- **Staged implementation** — plan → build → independent review → fix and
  re-verify.
- **Second opinion** — preferably a cross-family challenge for a consequential,
  disputed, low-confidence, or hard-to-reverse decision. Disclose when only a
  same-family fallback is available.

Parallelize only independent work. Keep dependent phases sequential. Use no
more than three distinct automatic delegates and at most one per role unless
scopes differ. Avoid duplicate assignments and resume the Builder for fixes
rather than creating a fourth worker. Resume an interrupted delegate by id/name
to preserve context. Give genuinely wrong output one corrected retry, then stop
and re-plan. Invocation, sandbox, timeout, or infrastructure failures require
fixing the launch rather than spending that retry. Call a result independent
only if another model actually produced it.

## Builder CLIs

After `model-routing` selects a Builder path, read only the matching reference
before dispatching:

| Path                      | When                                                     | Read                      |
| ------------------------- | -------------------------------------------------------- | ------------------------- |
| Codex / GPT-5.6           | Default Builder                                          | `references/codex.md`     |
| Agent CLI (Auto/Composer) | Codex unavailable, or user requests Cursor Auto/Composer | `references/agent-cli.md` |

Do not load both unless switching paths mid-run or comparing mechanisms. Keep
CLI flags, auth, resume, and tool-specific long-run details in those files.

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

Do not have a Builder decide objections to its own review. The Reviewer/Judge
adjudicates disputed findings. Ask the user when a product or safety decision
cannot be inferred. Direct coordination the user explicitly authorizes (such as
committing or pushing) may run in the orchestrator.

## Delegation Packet

Send only the context needed to complete and verify the assignment:

```text
Objective: <specific outcome>
Success criteria: <observable result>
Role / effort: <from model-routing>
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

## Long Runs and Results

Launch lengthy Builder CLI runs in the background and have the orchestrator
watch the captured PID, output artifact, and the per-run log described in the
active Builder CLI reference. Poll about once a minute and emit a heartbeat at
least every ten minutes. Stop when the artifact appears or the captured PID
exits without one, and report which condition occurred. Treat 15 minutes
without log growth as a diagnostic signal, not proof of a hang or a reason to
terminate a live process. On Windows, poll the captured PID with `tasklist`,
not `kill -0` or a process-name check.

A wrapper's completion only confirms that it launched the delegate. Resume it
after the artifact exists to collect the outcome. Before retrying or resuming
after a timeout, inspect the PID, artifact, and log.

Require cited test, repository-tool, or primary-source evidence. Treat broad or
slow fixes as higher-risk and give them additional Reviewer/Judge scrutiny.
For persistent goals, track observable completion criteria; persistence never
authorizes rebases, branch changes, closing or merging PRs, deployments, or
other external effects without the user's explicit approval.
