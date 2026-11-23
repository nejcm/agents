# Issue pipeline

- **Status**: unavailable until the `fix-issues` skill exists. List it, never offer it. Becomes
  available when the skill lookup finds `fix-issues/SKILL.md`.
- **Trigger**: hourly.
- **Requires**: `fix-issues` installed; one issue tracker from the profile's `Integrations`,
  available; the verify skill; agent PRs allowed.
- **Runners**: local.
- **Input**: new issues from the profile's source-of-truth tracker. Untrusted.
- **Writes**: defined by `fix-issues` within [`../safety.md`](../safety.md).
- **Choices**: tracker; labels in scope.

## Prompt

Defined with `fix-issues`.
