# Merge rules

The final reviewer applies these after approving the diff. `merge-gate.sh` already blocks size,
protected paths, rewritten tests and skip markers; these cover what a regex can't see.

The verdict is `needs-human` when the diff:

- Is a one-way door: loses or rewrites stored data or schema, breaks a public API, CLI, config
  or file-format contract, or makes a security or auth decision anywhere in the code.
- Changes behavior without a test that would fail if the change were reverted.
- Adds a runtime dependency, a service or background process, or network calls where the code
  made none.
- Goes beyond the task's stated scope or success criteria.

Otherwise it is `eligible`. When unsure, it is `needs-human`.

End the approval with one `Merge:` line as the last line of the reply, after any door call.
Either `Merge: eligible`, or `Merge: needs-human — <reason>; <reason>`. A one-way door is
always `needs-human`.

A missing or malformed line counts as `needs-human`.
