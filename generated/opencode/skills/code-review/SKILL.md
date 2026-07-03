---
name: code-review
description: >-
  Request a read-only code review of completed work, a branch, or a PR before
  proceeding or merging. Use when the user asks for code review, review since a
  ref, review recent work, verify implementation against requirements, or check
  quality before merge. Combines fixed-point diff review with separate Spec and
  Standards/Quality axes, severity-based findings, and clear merge readiness.
---
# Code Review

Dispatch reviewer sub-agents with crafted work-product context, never session history. Review early and often so issues do not compound.

Review on two axes:

1. **Spec**:
  - Missing or partial requirements
  - Scope creep or behavior not requested
  - Requirements that appear implemented incorrectly
  - Quote or cite the requirement for each finding when possible 
2. **Standards/Quality**: Does the implementation meet repo conventions and engineering quality?
  - Violations of documented repo standards
  - Architecture and separation of concerns
  - Error handling, edge cases, security, performance
  - Type safety where applicable
  - Tests that verify real behavior
  - Migration/backward compatibility if schemas or APIs changed
  - Possible code smells: mysterious names, duplication, feature envy, data clumps, primitive obsession, repeated switches, shotgun surgery, divergent change, speculative generality, message chains, middle man, refused bequest

Both axes run as parallel sub-agents so they don't pollute each other's context and triage findings by severity inside each axis.

Severity:
- Critical: bugs, security issues, data loss, broken required behavior
- Important: missing requirements, weak architecture, poor error handling, meaningful test gaps
- Minor: style, documentation, small maintainability issues

For every issue include:
- File:line
- What is wrong
- Why it matters
- How to fix, if not obvious

## When To Use

Mandatory:

- After each task in subagent-driven development.
- After completing a major feature.
- Before merge to main.

Optional but valuable:

- When stuck and a fresh perspective may help.
- Before refactoring, to establish a baseline.
- After fixing a complex bug.
- Before continuing a multi-step plan.

## 1. Pin The Range

Resolve the fixed point:

- If the user supplied a commit, branch, tag, or ref, use it.
- If they did not, use the most appropriate local baseline: `origin/main`, `main`, or the previous task commit.
- If no reasonable baseline exists, ask for one.

Validate before dispatching:

```bash
git rev-parse <fixed-point>
git diff --quiet <fixed-point>...HEAD; echo $?
git log --oneline <fixed-point>..HEAD
```

Use merge-base diff for branch review:

```bash
git diff --stat <fixed-point>...HEAD
git diff <fixed-point>...HEAD
```

For explicit SHA-to-SHA review, use the exact range the user requested.

## 2. Find Review Context

Find the spec or requirements in this order:

1. User-provided plan, PRD, issue, or file path.
2. Issue references in commits or branch name.
3. Matching files under `docs/`, `specs/`, `.scratch/`, or plan/task directories.
4. If none exists, review the Spec axis as "no spec available" and focus on visible intent from commits and diff.


## 3. Standards

Find standards sources:

- `AGENTS.md`, `CONTRIBUTING.md`, `CODING_STANDARDS.md`, `README.md`
- language-specific style guides, lint configs, test conventions
- repo-local rules or agent instructions

Avoid restating clean lint/type/test output; flag failures, bypasses, weakened checks, or gaps.

On top of whatever the repo documents, the Standards axis always carries the **smell baseline** below — a fixed set of Fowler code smells (_Refactoring_, ch.3) that applies even when a repo documents nothing. Two rules bind it:

- **The repo overrides.** A documented repo standard always wins; where it endorses something the baseline would flag, suppress the smell.
- **Always a judgement call.** Each smell is a labelled heuristic ("possible Feature Envy"), never a hard violation — and, like any standard here, skip anything tooling already enforces.

Each smell reads *what it is* → *how to fix*; match it against the diff:

- **Mysterious Name** — a function, variable, or type whose name doesn't reveal what it does or holds. → rename it; if no honest name comes, the design's murky.
- **Duplicated Code** — the same logic shape appears in more than one hunk or file in the change. → extract the shared shape, call it from both.
- **Feature Envy** — a method that reaches into another object's data more than its own. → move the method onto the data it envies.
- **Data Clumps** — the same few fields or params keep travelling together (a type wanting to be born). → bundle them into one type, pass that.
- **Primitive Obsession** — a primitive or string standing in for a domain concept that deserves its own type. → give the concept its own small type.
- **Repeated Switches** — the same `switch`/`if`-cascade on the same type recurs across the change. → replace with polymorphism, or one map both sites share.
- **Shotgun Surgery** — one logical change forces scattered edits across many files in the diff. → gather what changes together into one module.
- **Divergent Change** — one file or module is edited for several unrelated reasons. → split so each module changes for one reason.
- **Speculative Generality** — abstraction, parameters, or hooks added for needs the spec doesn't have. → delete it; inline back until a real need shows.
- **Message Chains** — long `a.b().c().d()` navigation the caller shouldn't depend on. → hide the walk behind one method on the first object.
- **Middle Man** — a class or function that mostly just delegates onward. → cut it, call the real target direct.
- **Refused Bequest** — a subclass or implementer that ignores or overrides most of what it inherits. → drop the inheritance, use composition.

## 4. Spawn both sub-agents in parallel

Send a single message with two `Agent` tool calls. Use the `general-purpose` subagent for both.

Pass these placeholders to both sub-agents:

- `{DESCRIPTION}`: brief summary of what changed.
- `{PLAN_OR_REQUIREMENTS}`: what the work should do, or "no spec available".
- `{BASE_REF}`: fixed point.
- `{HEAD_REF}`: usually `HEAD`, unless the user requested an exact range.

**Standards sub-agent prompt** — include:

- The full diff command and commit list.
- The list of standards-source files you found in step 3, **plus the smell baseline from step 3** pasted in full — the sub-agent has no other access to it.
- The brief: "Report — per file/hunk where relevant — (a) every place the diff violates a documented standard: cite the standard (file + the rule); and (b) any baseline smell you spot: name it and quote the hunk. Distinguish hard violations from judgement calls — documented-standard breaches can be hard, but baseline smells are always judgement calls, and a documented repo standard overrides the baseline. Skip anything tooling enforces. Under 400 words."

**Spec sub-agent prompt** — include:

- The diff command and commit list.
- The path or fetched contents of the spec.
- The brief: "Report: (a) requirements the spec asked for that are missing or partial; (b) behaviour in the diff that wasn't asked for (scope creep); (c) requirements that look implemented but where the implementation looks wrong. Quote the spec line for each finding. Under 400 words."

If the spec is missing, skip the Spec sub-agent and note this in the final report.

## 5. Aggregate


Do **not** merge or rerank findings — the two axes are deliberately separate. The Recommendations section may list a cross-axis fix order.

Output:
## Spec
### Critical
### Important
### Minor

## Standards/Quality
### Critical
### Important
### Minor

## Recommendations

## Assessment
Ready to merge: Yes | No | With fixes
Reasoning: 1-2 sentences.
Don't pick a single winner across axes in the findings; use Recommendations for fix order.

## 6. Act On Feedback

Report findings first; only fix them when the user asked for review-and-fix or explicitly approves.

- Fix Critical issues immediately.
- Fix Important issues before proceeding unless there is a documented reason not to.
- Track Minor issues only if they are worth doing now.
- Push back on incorrect findings with code, tests, or clear reasoning.

Workflow integration:

- In subagent-driven development, review after meaningful task batches or risky changes, not every small task. Fix before moving on.
- When executing plans, review at natural checkpoints.
- In ad-hoc development, review before merge and when stuck.

Red flags:

- Do not skip review because the change is "simple".
- Do not ignore Critical issues.
- Do not proceed with unresolved Important issues unless documented.
- Do not argue with valid technical feedback.

After fixes, rerun the review on the new range or targeted fix diff when risk remains.
