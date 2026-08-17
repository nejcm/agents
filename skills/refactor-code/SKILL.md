---
name: refactor-code
description: Use when the user asks to clean up, simplify, deduplicate, or restructure existing code without changing its behavior or public API.
disable-model-invocation: true
---

# Refactor Code

Use this skill for behavior-preserving refactoring of an existing codebase. Keep the change narrow, make the reasoning visible before editing, and verify each meaningful step.

## Operating contract

- Preserve observable behavior: inputs, outputs, public APIs, return and error behavior, side-effect order, mutation, async/concurrency semantics, logging, and feature-flag/configuration behavior.
- Do not add features, change requirements, introduce dependencies, rewrite unrelated code, or silently change performance-sensitive behavior.
- Read repository instructions first (`AGENTS.md`, contribution guides, architecture notes, and package scripts). Preserve unrelated working-tree changes.
- Search before reading broadly. Start from the requested file/function, then inspect callers, exports, nearby tests, and the smallest relevant slices.
- Prefer a small, domain-specific helper over a generic utility. Do not extract code merely because it looks similar: confirm that its inputs, invariants, error handling, and lifecycle are actually shared.

## Workflow

### 1. Audit before editing

Do not write code until you have emitted an audit report. If the request is report-only, stop after the report. Otherwise, show the report and then implement the approved-safe scope in the same turn.

Establish the target boundary and inspect enough context to identify:

- Exact duplicate or near-duplicate blocks, with file and line references.
- Repeated semantic patterns that could share a helper or processing pipeline.
- Deep nesting, repeated branching, long conditional chains, or high-complexity functions.
- Dead or redundant code, needless conversions, duplicated validation, and unclear names.
- Cases that look similar but must remain separate because their behavior differs.

Use this report shape:

```text
Refactoring audit
Scope: <files, functions, and exclusions>
Behavior contract: <inputs, outputs, side effects, errors, ordering, and other constraints>
Baseline checks: <commands run and results, or why unavailable>

Findings:
1. <finding and exact location>
   Evidence: <duplicate pattern or structural issue>
   Risk: <why changing it could alter behavior>
   Minimal refactor: <helper, guard clause, or consolidation>
   Verification: <test or check that proves equivalence>

Out of scope: <similar-looking code intentionally left unchanged and why>
```

Do not claim duplication without pointing to both occurrences or explaining the semantic equivalence. Do not label a style preference a defect.

### 2. Establish a verification baseline

Before changing code, run the narrowest relevant existing tests. Also run the repository’s prescribed formatter, linter, type checker, or equivalent checks when practical. Record the exact commands and results.

If coverage is weak, add a focused characterization test only when it is necessary to make existing behavior observable. Do not redesign production code to make testing convenient. If no reliable verification path exists, state the limitation and keep the refactor smaller or stop.

### 3. Refactor incrementally

Apply one cohesive change block at a time; do not rewrite a large file wholesale.

- Consolidate repeated logic only after identifying the shared contract. Preserve validation order, default values, error paths, side effects, and source locations where they are observable.
- Prefer guard clauses and early returns when they reduce nesting without changing evaluation order, short-circuit behavior, or cleanup. Keep a conditional chain when the branches are not truly equivalent.
- Extract a helper at the narrowest useful scope, with a name that describes domain intent. Avoid catch-all `utils` functions and abstractions used once unless they materially clarify the code.
- Preserve types, exports, schemas, serialization, dependency injection seams, and public names unless the request explicitly permits an API change.
- After each meaningful block, run the focused tests and relevant static checks. If a check fails, stop adding changes, diagnose the regression, and repair or remove only the last block without touching unrelated work.

### 4. Final verification and handoff

Review the diff as a behavior change, not just a style change:

- Confirm every audit item addressed is reflected in the diff and no unrelated file changed.
- Check for altered branch order, eager evaluation, mutation, error behavior, async timing, resource cleanup, and logging.
- Remove unused helpers/imports and confirm formatting, lint, types, and tests pass using repository-defined commands.
- If the project has a required full check, run it at the natural completion point. Do not start a development server or run a build unless repository instructions or the user require it.

Report:

```text
Refactoring result
Changed: <files and concise behavior-preserving changes>
Unchanged intentionally: <out-of-scope similar code, if any>
Verification: <exact commands and results>
Residual risk: <remaining uncertainty, missing coverage, or none>
```

If behavior cannot be demonstrated safely, do not present an unverified rewrite as complete; explain the blocker and leave the code unchanged or narrowly improved with explicit residual risk.
