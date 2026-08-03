---
name: model-orchestration
description: Dispatch and coordinate multi-model work in Claude Code, including delegation patterns, GPT-5.6 through Codex CLI, compact task packets, long-running runs, and independent review. Use whenever implementing an approved plan or design, delegating or parallelizing work, shelling out to Codex, or starting medium- or high-complexity work where plan → build → review → fix materially reduces risk.
---

# Model Orchestration

`model-routing` decides roles, effort, preferred models, independence, and
fallbacks. This skill supplies the dispatch mechanics. User and repository
instructions override both.

## Dispatch

At each dispatch, apply `model-routing`, then confirm that the chosen mechanism
supports the model, effort, tools, and isolation needed. Prefer:

1. A capable host-native subagent/workflow.
2. A non-interactive CLI (`codex exec` or `claude -p`).
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

## GPT-5.6 via Codex

When routing selects GPT-5.6, use `codex exec` or `codex exec review` with
`-m <variant selected by model-routing>`. For Builder dispatches, apply the
Builder matrix: use `gpt-5.6-luna` at `xhigh` (or `max` when extra depth is
worth the latency) for bounded simple-to-medium work, and `gpt-5.6-sol` at
`medium` or `high` for medium-to-very-complex work. In the overlapping medium
band, select Luna only for bounded, easily verified work; otherwise select Sol.
Do not hard-code one GPT-5.6 variant for every role. If host workflows accept
only Claude models, use a thin host-native wrapper selected by the
Claude-specific model defaults (normally
Sonnet 5) that runs Codex and returns its artifact. Use its schema option when
structured output helps. Prefix its label with `gpt-5.6:` so the UI does not
misrepresent the actual worker; if a reused wrapper changes roles, rename it or
disclose the mismatch. Parallel writers need separate worktrees. Codex usage is
invisible to Claude workflow token budgets, so track it separately when a
budget matters.

Before relying on an invocation, check the installed CLI help. Give Codex a
self-contained prompt and pass the selected variant and effort separately:

```bash
mkdir -p "$ARTIFACT_DIR"
codex exec -m <selected-variant> -C "$PWD" -s read-only \
  -c "model_reasoning_effort=<selected-effort>" \
  -o "$ARTIFACT_DIR/result.md" \
  "<focused prompt>" < /dev/null
```

For implementation, state permitted files, required behavior, exclusions,
branch authority, and verification. Prefer an isolated branch or worktree;
working directly on one branch is valid for sequential phases because there
are no parallel writers to isolate. Prompt as the final positional argument and
redirect empty stdin: on Windows, piped or absent stdin can stall at `Reading
additional input from stdin...`. Distinguish that stall from a sandbox failure.
If the sandbox fails before commands start, repair that mode and retry once
with broader isolation only when host and user policy permit it. Keep the prompt
tightly scoped and disclose the reduced isolation.

For review, select exactly one target (`--uncommitted`, `--base`, or `--commit`)
_or_ use a focused prompt; the CLI does not allow both. A clean review is a
valid result. Reports must name the inspected target and clearly state when
there are no findings. `--uncommitted` includes untracked files, so discard
findings caused only by unrelated scratch or local-settings files. Do not rerun
an unchanged, already-triaged diff to force findings.

```bash
codex exec review -m <selected-variant> --uncommitted \
  -c "model_reasoning_effort=<selected-effort>" \
  -o "$ARTIFACT_DIR/review.md"
```

`codex exec resume <session-id>` preserves context but not necessarily the
recorded model: always supply `-m`. Check that any prompt file is non-empty
before resuming. Store prompts and reports in a temporary or gitignored
artifact directory and remove or disclose leftovers.

For computer use, state the flow, environment, whether edits are allowed, and
the screenshot, video, or other evidence required. Confirm that the invoked
Codex environment exposes the necessary tools; CLI availability alone does not
establish computer-use availability.

## Long Runs and Results

Launch lengthy Codex runs in the background and have the orchestrator watch the
captured PID, output artifact, and a per-run JSONL log created by redirecting
`--json` stdout. Poll about once a minute and emit a heartbeat at least every
ten minutes. Stop when the artifact appears or the captured PID exits without
one, and report which condition occurred. Treat 15 minutes without log growth
as a diagnostic signal, not proof of a hang or a reason to terminate a live
process. On Windows, poll the captured PID with `tasklist`, not `kill -0` or a
process-name check.

A wrapper's completion only confirms that it launched Codex. Resume it after
the artifact exists to collect the outcome. Before retrying or resuming after a
timeout, inspect the PID, artifact, and log.

Require cited test, repository-tool, or primary-source evidence. Treat broad or
slow fixes as higher-risk and give them additional Reviewer/Judge scrutiny.
For persistent goals, track observable completion criteria; persistence never
authorizes rebases, branch changes, closing or merging PRs, deployments, or
other external effects without the user's explicit approval.
