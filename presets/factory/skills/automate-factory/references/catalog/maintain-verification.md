# Maintain verification

- **Trigger**: weekly, Monday 06:00.
- **Requires**: a committed `verify-<app>` skill recorded in the profile's `Verification`
  section; pstack `maintain-verification-skill` installed for the follow-up.
- **Runners**: local.
- **Input**: the repo's tracked files and its commit graph since the verify skill last changed.
  Trusted.
- **Writes**: report to `.factory/reports/maintain-verification/<date>.md`.
- **Write levels**: report.
- **Steps**: fetch lists what changed since the skill's last commit, hashes and paths only (no
  commit messages):

  ```bash
  fetch() {
    local since
    since=$(git log -1 --format=%H "$ref" -- .cursor/skills/verify-<app>)
    git log --format=%H --name-only "$since..$ref" > "$view/input/changes.txt"
  }
  ```

  Analyze flags drift signals only. pstack's maintenance needs live verification, so it runs in
  the attended follow-up, never here.
- **Choices**: schedule.

## Prompt

```text
Read repo/.cursor/skills/verify-<app>/SKILL.md and its feature map. From input/changes.txt (commits
and changed paths since the skill last changed) and the current code in repo/, list each mapped
feature whose code, routes, selectors or run commands changed, with the commit and path.
End with exactly one line: "Maintenance due" or "No drift signals".
```

## Follow-up (attended)

On "Maintenance due", the user runs pstack `maintain-verification-skill` for `verify-<app>` in
their harness, with the report as its starting list; it verifies live and decides whether to ship.
