# Maintain verification

- **Trigger**: weekly, Monday 06:00. Per-entry `trigger`
  ([runners.md](../runners.md#change-triggers)): `schedule` analyzes on every run; `changes`
  (from the oncue job or the user's workflow) re-reports an unchanged state without a model call.
- **Requires**: a committed `verify-<app>` skill recorded in the profile's `Verification`
  section, with a `Feature paths` line per mapped feature; pstack `maintain-verification-skill`
  installed for the follow-up.
- **Runners**: local.
- **Input**: the repo's tracked files and its commit graph since the verify skill last changed.
  Trusted.
- **Writes**: report to `.factory/reports/maintain-verification/<date>.md`.
- **Write levels**: report.
- **Steps**: fetch lists what changed since the skill's last commit, hashes and paths only (no
  commit messages), and, model-free, each mapped feature whose `Feature paths` a commit since then
  touched. That base moves only when the skill changes, so a drifted feature stays flagged until
  then. `feature_paths` holds one `[<feature>]="<glob> ..."` per `Feature paths` line. With
  `changes`, when no commit since the last successful run's `end_commit` (from `runs.jsonl`)
  touched a mapped feature's paths or the skill, the run appends `still flagged: <features>` to
  the day's report with no model call and is recorded `skipped` `no-risk-change`; a dry run (the
  smoke run) always analyzes.

  ```bash
  trigger="<trigger>"
  set -f
  declare -A feature_paths=([<feature>]="<path glob>")
  set +f
  fetch() {
    local since last f globs flagged=()
    trigger_ok
    since=$(git log -1 --format=%H "$ref" -- .cursor/skills/verify-<app>)
    for f in "${!feature_paths[@]}"; do
      [[ $f =~ ^[A-Za-z0-9._-]+$ ]] || block "feature $f is not a feature name"
      read -ra globs <<< "${feature_paths[$f]}"
      globs_ok ${globs[@]+"${globs[@]}"}
      paths log -z --format= --name-only --no-renames "$since..$ref"
      ! touches "${globs[@]}" < "$view/paths" || flagged+=("$f")
    done
    { [ ${#flagged[@]} = 0 ] || printf '%s\n' "${flagged[@]}"; } | sort > "$view/input/flagged.txt"
    git log --format=%H --name-only "$since..$ref" > "$view/input/changes.txt"
    [ "$trigger" = changes ] && [ "${FACTORY_DRY_RUN:-0}" != 1 ] || return 0
    last_end
    [[ $last =~ ^[0-9a-f]{40}$ ]] && git cat-file -e "$last^{commit}" 2> /dev/null || return 0
    [ -z "$(git log -1 --format=%H "$last..$ref" -- .cursor/skills/verify-<app>)" ] || return 0
    for f in "${!feature_paths[@]}"; do
      read -ra globs <<< "${feature_paths[$f]}"
      paths log -z --format= --name-only --no-renames "$last..$ref"
      ! touches "${globs[@]}" < "$view/paths" || return 0
    done
    f=$(paste -sd, "$view/input/flagged.txt" | sed 's/,/, /g')
    { printf 'still flagged: %s\n' "${f:-none}"
      printf 'Nothing since %s touched a mapped feature or the verify skill; details in the last full report.\n' "${last:0:12}"
      [ -s "$view/input/flagged.txt" ] && echo "Maintenance due" || echo "No drift signals"; } >> "$out/$day.md"
    run_outcome=skipped run_reason=no-risk-change
    exit 0
  }
  ```

  Analyze describes the drift. pstack's maintenance needs live verification, so it runs in the
  attended follow-up, never here.
- **Choices**: none.

## Prompt

```text
Read repo/.cursor/skills/verify-<app>/SKILL.md and its feature map. input/flagged.txt lists the
mapped features whose paths changed since the skill last changed, one per line; input/changes.txt
the commits and changed paths since then. For each flagged feature, and no other, say which of its
code, routes, selectors or run commands changed, with the commit and path, using the current code
in repo/.
End with exactly one line: "Maintenance due" or "No drift signals".
```

## Follow-up (attended)

On "Maintenance due", the user runs pstack `maintain-verification-skill` for `verify-<app>` in
their harness, with the report as its starting list; it verifies live and decides whether to ship.
