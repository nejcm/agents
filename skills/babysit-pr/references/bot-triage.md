# Bot triage patterns

Recurring bot findings that are safe to dismiss without a fresh `validate-external-review` run.
A finding skips validation only when it matches a `recurring` or `strong` pattern below and every
"Skip when" condition holds in the current code. `candidate` patterns still get validated.

Never skip, whatever matches: security, privacy, auth, permissions, billing, data retention,
migrations, concurrency, or any finding the bot rates high severity.

Add a pattern only after a real dismissal, in this shape. Promote `candidate` to `recurring`
after several verified dismissals, and to `strong` only when it is narrow and low-risk.

```markdown
### <short name>

- Confidence: candidate | recurring | strong
- Skip when: <conditions that must all hold>
- Do not skip when: <risk boundaries>
- Signal: <phrases or code context that identify it>
- Source: <PR or comment URL>
```

## Patterns

### Unused export used by a later stacked PR

- Confidence: candidate
- Skip when: the bot calls an export unused, and a PR stacked above this one uses it.
- Do not skip when: the PR is not stacked, the symbol is public API, or the use can't be found.
- Signal: "is never used", "unused export".
- Source: pstack `poteto-mode/references/bugbot-triage.md`

### Invariant already enforced elsewhere

- Confidence: candidate
- Skip when: a shared component, framework contract, or type already guarantees what the bot
  asks for, and that guarantee is visible in the diff or code it calls.
- Do not skip when: the invariant is assumed rather than enforced, or crosses async or state
  boundaries where values can diverge.
- Signal: missing null checks on values the type already narrows; missing bounds a shared
  component already applies.
- Source: pstack `poteto-mode/references/bugbot-triage.md`

### Bot withdrew its own finding

- Confidence: recurring
- Skip when: the comment, or the bot's later reply, says the finding is withdrawn, compliant, or a
  false positive, and the rule it cites checks out locally.
- Do not skip when: only a human says "false positive" on a high-risk finding.
- Signal: "this is already compliant", "false positive", "withdrawn".
- Source: pstack `poteto-mode/references/bugbot-triage.md`
