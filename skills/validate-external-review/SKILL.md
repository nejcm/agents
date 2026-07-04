---
name: validate-external-review
description: >-
  Triage an external review (from another LLM, a teammate, or a tool) against
  the actual codebase. Use when the user pastes or points to a review report
  from another source and asks to verify findings, check which issues are
  real, validate a review, or cross-check another LLM's output.
---

# Validate External Review

Take a review report from another LLM or source, verify each finding against the codebase, and produce a structured triage.

## Core rule

**Do not edit, fix, or modify code** unless the user explicitly requests it.

## Workflow

### 1. Ingest the review

If the input (pasted, file path, or URL) is ambiguous or can't be parsed as a review with discrete findings, ask the user to paste findings one at a time or reformat.

### 2. Parse findings

Extract every discrete finding. For each, capture:
- **Claim**: what the reviewer says is wrong
- **Location**: file:line references, if provided
- **Severity**: whatever the reviewer assigned (Critical / Important / Minor)

If the review has no structured findings, summarise what it asserts and ask the user to confirm before proceeding.

### 3. Verify against codebase

For each finding:
- Read the referenced file:line and surrounding context
- Check whether the claim matches the actual code
- If the reviewer provides a suggested fix, evaluate whether it's correct
- If no location is given, search the codebase for the described pattern

### 4. Classify

Assign one verdict per finding:

| Verdict | Criteria |
|---------|----------|
| **Valid** | The issue exists as described. The code matches the reviewer's description and the concern is real. |
| **Invalid** | The issue does not exist. The code doesn't match the description, the reviewer misread it, or the concern is based on wrong assumptions. |
| **Partial** | The general concern is valid but the specifics (location, severity, suggested fix) are wrong. |
| **Already fixed** | The issue existed but has since been resolved in the current code. |
| **Needs info** | Can't verify without more context (e.g., runtime behaviour, external service state, user intent). |

For each verdict, include:
- Evidence: quote the relevant code or file paths
- Reasoning: 1-2 lines on why this verdict was reached

### 5. Report

Output a structured triage:

```
## Triage Report

Source: [file path or "pasted input"]
Findings reviewed: N
Verified against: [branch/HEAD]

### Valid (X)
- [Finding 1] — confirmed in file:line. [Evidence snippet].
- [Finding 2] — ...

### Invalid (Y)
- [Finding 3] — not present in code. [What the code actually does].
- ...

### Partial (Z)
- [Finding 4] — concern valid but [what's different]. [Correction].

### Already fixed (W)
- [Finding 5] — resolved in commit abc1234.

### Needs info (V)
- [Finding 6] — depends on [missing context].

```

### 6. Next steps

End with a clear prompt — don't act:

```
To fix the X valid findings, say "fix the valid ones".
To investigate the V uncertain ones further, say which.
To dismiss the Y invalid ones, no action needed.
```

## Guardrails

- If a finding references a file that doesn't exist, mark it Invalid (not Needs info).
- If the review contains both valid and invalid findings, triage each independently — don't dismiss the whole review.
- If the reviewer's suggested fix is wrong even though the finding is valid, mark as Valid but note the fix is incorrect.
- Do not re-review code the external reviewer didn't mention. Scope is the provided review only.
