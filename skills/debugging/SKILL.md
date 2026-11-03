---
name: debugging
description: Use when investigating a bug, failing test, build or integration failure, crash, flaky behavior, or anything that "doesn't work" or behaves unexpectedly, before proposing or making a fix. For slowness, memory, or throughput use performance.
category: workflow
---

# Debugging

Establish the root cause with concrete evidence before proposing or implementing
a fix. If the request is diagnosis-only, do not modify files. Preserve unrelated
user changes; never reset or overwrite them.

```text
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

Completing a phase means satisfying its gate, not performing its checklist.
Symptom fixes, speculative edits, and bundled experiments violate this rule.

## Investigation Record

Keep a compact record, separating:

- **Facts**: observed output, reproduction results, code, config, history
- **Hypotheses**: explanations that predict an observable result
- **Tests**: the single variable changed and the result
- **Decisions**: why the next step follows

Never print secrets, tokens, credentials, or sensitive payloads in diagnostics.
Log safe shapes, identifiers, versions, timestamps, and boundary outcomes.

## Phase 0: Frame the Problem

1. Expected versus actual behavior, with the exact error or symptom.
2. Scope and impact: command, input, users, environment, versions, frequency.
3. First known occurrence, recent changes, constraints (compatibility, rollback).
4. The smallest reliable reproduction, or why one is not available yet.

Establish a baseline before changing anything. If the report is ambiguous, name
the missing fact and gather it instead of guessing.

## Phase 1: Root-Cause Investigation (Mandatory)

1. **Read the failure completely**: every error, warning, stack frame, path,
   code, and surrounding log line, not just the first message.
2. **Reproduce and reduce** yourself, on the surface where it fails; ask the
   user only with a specific reason you cannot reach it. Vary one dimension at a
   time: input, state, timing, dependency version, config, concurrency. If it
   will not fire, synthesize the trigger or instrument until it does; never guess.
3. **Inspect changes and environment**: `git status`, the relevant diff, recent
   commits, lockfile and dependency changes, config, env propagation, platform
   and runtime differences. If it survives a restart, suspect persisted state
   (caches, stores, files, build output) before code.
4. **Locate the failing boundary.** In multi-component flows, add temporary safe
   diagnostics at each boundary (input, output, config/version propagation,
   state transitions), run once, and find the first divergence. Remove them after.
5. **Trace backward** from the symptom through callers and transformations to the
   first invalid transition or wrong assumption. Fix the source, not the place
   the bad value is noticed.

**Gate:** state what failed, where it first became invalid, why, and which
observations support it. Any unknown means stay here, research, or ask.

## Phase 2: Pattern and Difference Analysis

1. Find a similar working path, test, commit, config, or environment.
2. List every meaningful difference between working and broken; test small ones
   rather than dismissing them.
3. Read reference implementations and docs well enough to know their assumptions.
4. Check dependencies, lifecycle, ordering, defaults, config, data shape, ownership.

Output: a narrowed set of evidence-backed candidate causes, not a list of fixes.

## Phase 3: Hypothesis and Minimal Test

One hypothesis at a time:

```text
I think <specific cause> is responsible because <evidence>.
If true, <minimal test> should produce <predicted result>.
```

Make the smallest diagnostic change, one variable only, and check the
prediction. If it fails, revert what it motivated, revise with the new evidence,
and return to the relevant step; never stack another speculative change. If you
do not understand something, say so and investigate or ask.

## Phase 4: Fix and Verify

Only after the root cause is supported by evidence:

1. Write the smallest failing regression test or reproduction; confirm it fails
   for the diagnosed reason. Without a test framework, use a focused script and
   record the command and expected failure.
2. Make one minimal fix at the root cause. No unrelated cleanup, refactors, API
   changes, or "while I am here" edits. A guard (null check, catch, retry,
   clamp) is a fix only if the state it handles is legitimate; otherwise it
   hides the bug.
3. Run the regression test, focused checks, and the broader relevant suite when
   practical. Re-run the original reproduction on the same surface and check
   user-visible behavior, not just a changed assertion; an inconclusive or
   wrong-surface result is not a pass. If verification fails, first suspect how
   you observed it (stale build, wrong process or env, cached output, wrong log).
4. Check for regressions, changed logs/metrics, boundary behavior, operational
   side effects. Remove temporary instrumentation; inspect the final diff.
   Propose a cheap always-on signal (assertion, log line, metric) that would have
   caught this earlier.
5. Report what was proven, changed, and still uncertain, with the verification
   command and result. Never claim success without it.

## When Fixes Keep Failing

Count behavior-changing fix attempts; after each failure, stop and re-analyze
with its evidence. When two failed fixes share a premise, write the premise down
and test it directly before another fix. If a third fix fails, do not attempt
another without explicit human agreement: look for shared state, hidden coupling,
wrong ownership, lifecycle problems, or an unsound pattern, and present the
evidence with an architectural alternative.

## Red Flags: Return to Investigation

- "Quick fix for now" or "just try changing X"
- A fix proposed before reading the full failure or tracing data flow
- Multiple changes before testing
- Skipping the failing test and relying on manual confirmation
- Treating non-reproducibility as permission to guess
- Assuming a familiar pattern applies without comparing working and broken cases
- "I see the problem" when only the symptom is known
- A third fix before testing the shared premise of the first two
- Debug logging, secrets, or unrelated refactoring left in the final diff

## Environmental or Timing-Dependent Failures

If evidence points to an external, environmental, or timing cause:

1. Document attempted reproduction, observations, environment, and uncertainty.
2. Only if requested and justified, add the smallest handling or observability
   change: bounded retry, condition-based wait, timeout, validation, or an
   actionable error.
3. Add monitoring or a regression harness that detects recurrence.

An inconclusive first pass is not "no root cause".

## Completion Report

```text
Status: diagnosed | fixed | blocked

Observed behavior:
Reproduction:
Evidence:
Root cause and confidence:
Hypotheses rejected:
Changes made:
Verification (commands and results):
Remaining uncertainty / follow-up:
```

Speed comes from narrowing the search space with evidence, not guessing quickly.
