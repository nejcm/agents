#!/usr/bin/env bash
# Factory automation; step rules in automate-factory references/safety.md.
set -euo pipefail
cd "$(dirname "$0")/../.."
[ ! -e .factory/pause ] || { echo paused; exit 0; }
entry=$(basename "$0" .sh)
day=$(date +%F)
out=.factory/reports/$entry
mkdir -p "$out" .factory/tmp
[ -e .factory/tmp/.gitignore ] || echo '*' > .factory/tmp/.gitignore
view=$(mktemp -d "$PWD/.factory/tmp/$entry.XXXXXX")
# Against mistakes only: the edit step runs as this user and can change any Git config.
n=${GIT_CONFIG_COUNT:-0}
[[ $n =~ ^[0-9]+$ ]] || { echo "GIT_CONFIG_COUNT is not a number" >&2; exit 1; }
n=$((10#$n))
export GIT_CONFIG_COUNT=$((n + 2)) "GIT_CONFIG_KEY_$n=core.hooksPath" "GIT_CONFIG_VALUE_$n=/dev/null" \
  "GIT_CONFIG_KEY_$((n + 1))=core.fsmonitor" "GIT_CONFIG_VALUE_$((n + 1))=false"
trap 'rm -rf "$view"; git worktree prune' EXIT
mkdir "$view/repo" "$view/input" "$view/skills"
ref="<base>" repo="<owner/repo>"
max_turns="<turns>" minutes="<minutes>"
level="<level>"
# Credentials, providers and endpoints that would override the subscription login.
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_OAUTH_TOKEN ANTHROPIC_PROFILE \
  ANTHROPIC_FEDERATION_RULE_ID ANTHROPIC_ORGANIZATION_ID ANTHROPIC_BASE_URL ANTHROPIC_CUSTOM_HEADERS \
  CLAUDE_CODE_USE_BEDROCK CLAUDE_CODE_USE_VERTEX CLAUDE_CODE_USE_FOUNDRY CLAUDE_CODE_USE_MANTLE \
  CLAUDE_CODE_USE_ANTHROPIC_AWS CLAUDE_CODE_USE_ANTHROPIC_GOOGLE_CLOUD
caps=(--max-turns "$max_turns")
git archive "$ref" | tar -x -C "$view/repo"

# Project skills are repo-relative, read from the tracked snapshot and must resolve inside it;
# only regular, non-hidden .md and .py files are copied. Their paths, link and target, join deny.
skills=() consumed=()
snap=$(cd -P "$view/repo" && pwd)
for s in ${skills[@]+"${skills[@]}"}; do
  case "$s" in /*) src=$s ;; *) src=$view/repo/$s ;; esac
  real=$(cd -P "$src" && pwd)
  case "$s" in
    /*) ;;
    *) case "$real/" in "$snap"/*) ;; *) echo "skill $s resolves outside the snapshot" >&2; exit 1 ;; esac
      consumed+=("$s" "$s/*" "${real#"$snap"/}" "${real#"$snap"/}/*") ;;
  esac
  d="$view/skills/$(basename "$s")"
  mkdir "$d"
  (cd "$real" && find . -type f ! -path '*/.*' \( -name '*.md' -o -name '*.py' \) -print0 |
    tar --null -T - -cf -) | tar -x -C "$d"
done

fetch() { :; }

analyze() {
  prompt="$(cat ".factory/automations/$entry.md")
Date: $day
Snapshot: $ref at $(git rev-parse --short "$ref")"
  (cd "$view" && claude -p --restricted --safe-mode --tools "Read,Grep,Glob" --strict-mcp-config \
    --no-session-persistence --permission-mode dontAsk "${caps[@]}" --output-format text \
    "$prompt" < /dev/null) \
    > "$view/report.md"
  test -s "$view/report.md"
  mv "$view/report.md" "$out/$day.md"
}

post_check() { :; }

post() { :; }

# draft-pr and pr only. Destination, gates and test command are fixed here at setup.
remote="<remote url>" branch="factory/$entry"
title="chore: $entry automation $day"
test_cmd="<test command>" max_lines=400 summary_cap=65536
# Patterns stay literal; expanded against the checkout they would miss new files.
set -f
allow=("<path glob>")
deny=(.github/* .gitlab-ci.yml .circleci/* .buildkite/* Jenkinsfile .factory/* .husky/* .githooks/*
  .pre-commit-config.yaml .gitattributes CODEOWNERS */CODEOWNERS .cursor/skills/verify-*
  *.claude/settings* *.claude/hooks/* .cursor/*.json .cursor/hooks/* .codex/* .gemini/* .mcp.json
  .vscode/* .devcontainer/*)
set +f
deny+=(${consumed[@]+"${consumed[@]}"})
tests_re='(^|/)(tests?|__tests__|spec)/|[._-](test|spec)\.[A-Za-z]+$|(^|/)test_[^/]*\.py$'
pr="" start="" commit="" gated="" changed=()

clip() {
  local l n=0
  while IFS= read -r l; do
    if [ "$n" -lt "$1" ]; then printf '%s\n' "${l:0:200}"; fi
    n=$((n + 1))
  done
  if [ "$n" -gt "$1" ]; then echo "[$((n - $1)) more lines]"; fi
}

block() { echo "gate: $*" >&2; exit 1; }

no_creds() { ! grep -qE 'sk-ant-[A-Za-z0-9_-]{16}'; }

# Final body of every external write; returns 1 in dry run so the caller writes nothing.
sendable() {
  [ "$(wc -c < "$1")" -le 65536 ] || block "body over GitHub's 65536 characters"
  no_creds < "$1" || block "credential-shaped text"
  [ "${FACTORY_DRY_RUN:-0}" != 1 ]
}

edit() {
  local prs head prompt tools=Bash,Read,Grep,Glob,Edit,Write
  check=$view/check work=$view/work
  start=$(git rev-parse "$ref")
  prs=$(gh pr list --repo "$repo" --head "$branch" --state open --json number,headRefOid,isCrossRepository \
    --jq '.[] | select(.isCrossRepository | not) | "\(.number) \(.headRefOid)"')
  read -r pr head <<< "$prs"
  if [ -n "$pr" ]; then
    git fetch -q "$remote" "refs/heads/$branch"
    [ "$(git rev-parse FETCH_HEAD)" = "$head" ] || block "$branch moved during the run"
    start=$head
  elif [ "$branch" != "factory/$entry" ]; then
    block "no open PR on $branch"
  elif git ls-remote --exit-code -q "$remote" "refs/heads/$branch" > /dev/null; then
    block "$branch exists without an open PR"
  fi
  mkdir "$check"
  git worktree add -q --detach "$work" "$start"
  cp "$out/$day.md" "$check/report.md"
  cp .factory/profile.md "$check/"
  cp -R "$view/skills" "$check/"
  prompt="$(cat ".factory/automations/$entry.edit.md")
Inputs, read-only: $check (report.md, profile.md, skills/). Edit only the working directory; never
commit, push or run gh.
End your reply with a summary of what changed and why, last line edit: outcome=changed or
edit: outcome=stopped. Before that, one line per existing test file you changed:
test-change: <path from the repo root>: <one-line reason>. Never delete or rename a test file."
  # No setting sources: tracked project settings in the checkout could switch auth or permissions.
  (cd "$work" && timeout "${minutes}m" claude -p --safe-mode --setting-sources '' --strict-mcp-config \
    --no-session-persistence --tools "$tools" --allowedTools "$tools" "${caps[@]}" \
    --permission-mode dontAsk "$prompt" < /dev/null) | head -c $((summary_cap + 1)) > "$view/summary.md" ||
    [ "$(wc -c < "$view/summary.md")" -gt "$summary_cap" ]
  [ "$(wc -c < "$view/summary.md")" -le "$summary_cap" ] || block "summary over $summary_cap bytes"
  if [ "$(tail -n1 "$view/summary.md")" != "edit: outcome=changed" ]; then
    echo "edit: no change"
    exit 0
  fi
  git -C "$work" add -A
  git -C "$work" commit -q -m "$title"
  commit=$(git -C "$work" rev-parse HEAD)
}

gates() {
  local st p g ok a d r m rc lines=0 tests=() seen=$'\n'
  changed=()
  ! git diff --quiet "$start" "$commit" || block "empty diff"
  while IFS=$'\t' read -r st p; do
    for g in "${deny[@]}"; do [[ $p != $g ]] || block "CI, hook or policy path $p"; done
    ok=0
    for g in "${allow[@]}"; do [[ $p != $g ]] || ok=1; done
    [ "$ok" = 1 ] || block "$p outside the allowlist"
    [[ $p =~ $tests_re ]] || continue
    [ "$st" != D ] || block "test $p deleted or renamed"
    tests+=("$p")
    [ "$st" = A ] || changed+=("$p")
  done < <(git diff --name-status --no-renames "$start" "$commit")
  while read -r a d p; do
    [ "$a" != - ] || block "binary change $p"
    lines=$((lines + a + d))
  done < <(git diff --numstat --no-renames "$start" "$commit")
  [ "$lines" -le "$max_lines" ] || block "$lines changed lines, cap $max_lines"
  if [ ${#tests[@]} -gt 0 ]; then
    git diff -U0 --output-indicator-new='>' --output-indicator-old='<' "$start" "$commit" -- \
      "${tests[@]}" > "$view/tests.diff"
    ! grep -qE '^>.*(\.skip\(|\.only\(|\bx(it|describe|test)\(|@pytest\.mark\.(skip|xfail)|@unittest\.skip|\bt\.Skip|#\[ignore\]|@Disabled|@Ignore)' \
      "$view/tests.diff" || block "test skipped"
  fi
  sed -n 's/^test-change: /- /p' "$view/summary.md" > "$view/reasons.md"
  while IFS= read -r r; do
    m=""
    for p in ${changed[@]+"${changed[@]}"}; do
      [[ $r != "- $p: "* || ${#p} -le ${#m} ]] || m=$p
    done
    [ -n "$m" ] || block "test-change line names no changed existing test: $r"
    [[ ${r#"- $m: "} = *[![:space:]]* ]] || block "blank test-change reason for $m"
    [[ $seen != *$'\n'"$m"$'\n'* ]] || block "duplicate test-change for $m"
    seen+="$m"$'\n'
  done < "$view/reasons.md"
  for p in ${changed[@]+"${changed[@]}"}; do
    [[ $seen == *$'\n'"$p"$'\n'* ]] || block "no test-change reason for $p"
  done
  (cd "$work" && timeout "${minutes}m" sh -c "$test_cmd") > "$out/$day-tests.log" 2>&1 ||
    block "tests failed, exit $?"
  if [ ${#changed[@]} -gt 0 ]; then
    git worktree add -q --detach "$view/old" "$commit"
    git -C "$view/old" checkout -q "$start" -- "${changed[@]}"
    rc=0
    (cd "$view/old" && timeout "${minutes}m" sh -c "$test_cmd") > "$view/old.log" 2>&1 || rc=$?
    { printf '## Modifies existing tests\n\nNeeds human approval; the factory never merges.\n\n'
      clip 50 < "$view/reasons.md"
      if [ "$rc" = 124 ]; then
        printf '\nOld tests timed out after %s minutes: no evidence.\n' "$minutes"
      elif [ "$rc" = 0 ]; then
        printf '\nOld tests still pass on the new code: test edit not needed for this fix, review closely.\n'
      else
        printf '\nOld tests fail on the new code (exit %s): change needed.\n\n' "$rc"
        tail -n 20 "$view/old.log" | clip 20 | sed 's/^/    /'
      fi
      printf '\nChanged test lines:\n\n'
      git diff "$start" "$commit" -- "${changed[@]}" | clip 80 | sed 's/^/    /'
      echo; } > "$view/section.md"
  fi
  { git diff "$start" "$commit"; cat "$view/summary.md"; [ ! -e "$view/section.md" ] || cat "$view/section.md"; } |
    no_creds || block "credential-shaped text"
  [ ! -e "$view/section.md" ] || cp "$view/section.md" "$out/$day-test-change.md"
  gated=$start:$commit
}

publish() {
  local draft=() url label=factory:test-change
  if [ -z "$commit" ] || [ "$gated" != "$start:$commit" ]; then gates; fi
  [ "$level" != draft-pr ] && [ ${#changed[@]} = 0 ] || draft=(--draft)
  { [ ${#changed[@]} = 0 ] || cat "$view/section.md"
    printf 'Automation `%s`, %s. Base %s, start %s, commit %s. Gates passed.\n\n' \
    "$entry" "$day" "$(git rev-parse "$ref")" "$start" "$commit"
    cat "$view/summary.md"; } > "$view/body.md"
  sendable "$view/body.md" || return 0
  if [ -n "$pr" ] && [ ${#changed[@]} -gt 0 ]; then
    gh pr ready "$pr" --repo "$repo" --undo || block "could not return PR $pr to draft"
  fi
  git push -q "$remote" "$commit:refs/heads/$branch"
  if [ -n "$pr" ]; then
    gh pr comment "$pr" --repo "$repo" --body-file "$view/body.md"
    url=$pr
  else
    url=$(gh pr create --repo "$repo" ${draft[@]+"${draft[@]}"} --base "$ref" --head "$branch" --title "$title" \
      --body-file "$view/body.md")
    echo "$url"
  fi
  if [ ${#changed[@]} -gt 0 ]; then
    gh label create "$label" --repo "$repo" --description "Factory edit changes existing tests" > /dev/null 2>&1 || true
    gh pr edit "$url" --repo "$repo" --add-label "$label" > /dev/null || echo "publish: label $label not added" >&2
  fi
}

fetch
analyze
post_check
case "$level" in
  comment) if sendable "$out/$day.md"; then post; fi ;;
  draft-pr | pr)
    if declare -F pipeline > /dev/null; then
      pipeline
    else
      edit
      publish
    fi
    ;;
esac
