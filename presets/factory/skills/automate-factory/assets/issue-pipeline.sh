# issue-pipeline at draft-pr: inserted into run.sh after publish; run.sh then calls pipeline.
trust=("<trust prefix>") label="<label>" run_minutes="<run minutes>" app="<app>" cap="<cap>"
flow="<flow>" verify_fixed="<verify-fixed>"
fx=$PWD/.factory/reports/fix-issues
items=$fx/items

try() { set +e; (set -e; "$@"); set -e; }
tag() { case $1 in *[!0-9]*) echo "$1" ;; *) echo "#$1" ;; esac; }
row() { [ ! -f "$1" ] || awk -v k="$2" '$1 == k {v = $2} END {print v}' "$1"; }
finish() { outcome=$1 reason=$2; exit 0; }
ran() { [ "$1" = 124 ] || { outcome=deferred reason=runner-error; exit 1; }; }

take() {
  [ -f "$1" ] && [ ! -L "$1" ] && [ "$(wc -c < "$1")" -le "$summary_cap" ] || exit 1
  cp "$1" "$2"
}

preflight() {
  local p
  for p in .factory .factory/reports "$fx"; do [ ! -L "$p" ] || block "$p is a symlink"; done
  [ -z "$(find "$fx" -path "$fx/tmp/fix-*/*" -prune -o -type l -print 2> /dev/null)" ] || block "symlink under $fx"
  [ -z "$(git ls-files -- "$fx")" ] || block "$fx is tracked: git rm -r --cached it"
  mkdir -p "$fx/tmp" "$items"
  [ -e "$fx/.gitignore" ] || (set -C; printf '*\n' > "$fx/.gitignore")
  [ "$(cat "$fx/.gitignore")" = '*' ] && git check-ignore -q "$fx/tmp/x/spec.md" || block "$fx is not ignored"
}

# $1 stage, $2 its directory, $3 reference, $4 tools, $5 commit of the verify skill, then inputs.
stage() {
  local check=$item/check/$1 evidence=$item/evidence/$1 prompt rc=0
  mkdir -p "$check" "$evidence"
  git archive "$5" ".cursor/skills/verify-$app" | tar -x -C "$check"
  cp -R "${@:6}" "$check/"
  prompt="$(cat "$runview/skills/fix-issues/references/$3" && overlay "$1" && cat "$item/bans.md")
Stage: $1."
  (cd "$2" && check=$check evidence=$evidence timeout "${minutes}m" claude -p --safe-mode --setting-sources '' \
    --strict-mcp-config --no-session-persistence --tools "$4" --allowedTools "$4" "${caps[@]}" \
    --permission-mode dontAsk --output-format json "$prompt" < /dev/null) > "$item/$1.json" 2> "$evidence/stdout.txt" ||
    rc=$?
  python3 -I -c "$record_py" json "$item/$1.json" "$calls" >> "$evidence/stdout.txt"
  [ "$rc" = 0 ] || ran "$rc"
}

spec_item() {
  local features=$runview/repo/.cursor/skills/verify-$app/features prompt rc=0
  prompt=$(cat ".factory/automations/$entry.spec.md" && overlay spec)
  { cat "$runview/input/items/$id.json"; echo
    awk -v h="## $id" '$0 == h {p = 1} p {print} p && /^fix-issues: / {exit}' "$report"; echo
    cat "$features/$feature.md"; } > "$item/spec-input.md"
  (cd "$runview" && timeout 5m claude -p --restricted --safe-mode --tools "" --strict-mcp-config \
    --no-session-persistence --permission-mode dontAsk --max-turns 3 --output-format json \
    "$prompt" < "$item/spec-input.md") > "$item/spec.json" || rc=$?
  python3 -I -c "$record_py" json "$item/spec.json" "$calls" > "$item/spec-draft.md"
  [ "$rc" = 0 ] || ran "$rc"
  python3 -I "$runview/skills/fix-issues/scripts/check_items.py" --spec "$features" "$feature" \
    < "$item/spec-draft.md" > "$item/spec.md"
}

red_green() {
  local p added=() rc=0
  while IFS= read -r p; do
    [[ $p =~ $tests_re ]] || continue
    added+=("$p")
  done < <(git diff --name-only --no-renames --diff-filter=A "$start" "$commit")
  if [ ${#added[@]} = 0 ]; then red="No test added; Root cause and fix says why."; return; fi
  git worktree add -q --detach "$item/red" "$start"
  git -C "$item/red" checkout -q "$commit" -- "${added[@]}"
  (cd "$item/red" && timeout "${minutes}m" sh -c "$test_cmd") > "$item/red.log" 2>&1 || rc=$?
  case $rc in
    0) red="New tests pass on base: they do not capture the bug, review closely." ;;
    124) red="New tests timed out on base after $minutes minutes: no evidence." ;;
    *) red="New tests fail on base (exit $rc) and pass on the fix." ;;
  esac
}

ticket_item() {
  local g=${id#err-} n c cs b
  n=$(row "$fx/tickets.tsv" "$g")
  if [ -z "$n" ]; then
    cs=$(gh issue list --repo "$repo" --state all --search "\"fix-issues-error: $g\" in:body" --json number --jq '.[].number')
    for c in $cs; do
      b=$(gh issue view "$c" --repo "$repo" --json body --jq .body)
      if grep -qxF "fix-issues-error: $g" <<< "${b//$'\r'/}"; then n=$c; break; fi
    done
    if [ -z "$n" ]; then
      { cat "$item/spec.md"; printf '\nfix-issues-error: %s\n' "$g"; } > "$item/ticket.md"
      sendable "$item/ticket.md" || finish deferred dry-run
      n=$(gh issue create --repo "$repo" --title "Error $g: $feature" --body-file "$item/ticket.md")
      n=${n##*/}
    fi
    [[ $n =~ ^[0-9]+$ ]] || exit 1
    printf '%s %s\n' "$g" "$n" >> "$fx/tickets.tsv"
  fi
  ticket=$n
}

body() {
  case $id in
    err-*) echo "Fixes #$ticket" ;;
    *[!0-9]*) echo "Source item: $id" ;;
    *) echo "Fixes #$id" ;;
  esac
  printf '\n## Spec\n\n'; cat "$item/spec.md"
  printf '\n## Reproduction\n\n'; clip 60 < "$item/repro.md"
  printf '\n## Root cause and fix\n\n'; clip 60 < "$item/fix.md"
  printf '\n## Tests\n\nGates passed on the fix: allowlist, deny list, line cap and the test command.\n%s\n' "$red"
  printf '\n## Verification\n\n'; clip 60 < "$item/verify.md"
  printf '\nEvidence: `.factory/reports/fix-issues/items/%s/evidence/` on the runner.\n' "$id"
}

# $1 item, $2 PR URL, $3 commit, $4 base.
link_item() {
  local f=$runview/link-$1.md
  printf 'Draft PR %s: reproduced on %s, and the fix %s passed the same check. Nothing merges without review.\n' \
    "$2" "$4" "$3" > "$f"
  send "$1" "$f" "$2"
}

# $1 item, $2 comment file, $3 linked.tsv value. Sets linked to the report reason.
send() {
  local n="" p=${1%%-*} st
  sendable "$2" || return 0
  linked=linked
  case $1 in
    err-*) n=$(row "$fx/tickets.tsv" "${1#err-}"); [ -n "$n" ] || linked=no-ticket ;;
    *[!0-9]*)
      if [ -f ".factory/automations/$p.comment.sh" ]; then
        bash ".factory/automations/$p.comment.sh" "${1#"$p"-}" < "$2"
      else
        linked=no-comment-write
      fi ;;
    *) n=$1 ;;
  esac
  if [ -n "$n" ]; then
    st=$(gh issue view "$n" --repo "$repo" --json state --jq .state)
    if [ "$st" = OPEN ]; then gh issue comment "$n" --repo "$repo" --body-file "$2" > /dev/null; else linked=closed; fi
  fi
  printf '%s %s\n' "$1" "$3" >> "$fx/linked.tsv"
}

# Skips an item already commented on, or with nowhere to comment.
commentable() {
  [ -z "$(row "$fx/linked.tsv" "$id")" ] || finish skipped linked
  case $id in
    err-*) [ -n "$(row "$fx/tickets.tsv" "${id#err-}")" ] || finish skipped no-ticket ;;
    *[!0-9]*) [ -f ".factory/automations/${id%%-*}.comment.sh" ] || finish skipped no-comment-write ;;
  esac
}

# repro-only: one comment with the spec and repro record, then stop.
repro_item() {
  step=link
  { printf 'Reproduced on %s by a scheduled run. No fix was attempted.\n' "$start"
    printf '\n## Spec\n\n'; cat "$item/spec.md"
    printf '\n## Reproduction\n\n'; clip 60 < "$item/repro.md"
    printf '\nEvidence: `.factory/reports/fix-issues/items/%s/evidence/` on the runner.\n' "$id"; } > "$item/body.md"
  sendable "$item/body.md" || finish deferred dry-run
  send "$id" "$item/body.md" "$start"
  finish reproduced "$linked"
}

# $1 the triage ref, #<n> or a SHA: qualified model-free per fix-issues reproduce.md, verify mode.
verify_item() {
  local tip v s x b k before after
  commentable
  linked_pr merged
  step=qualify
  git fetch -q "$remote" "refs/heads/$ref"
  tip=$(git rev-parse FETCH_HEAD)
  if [[ $1 =~ ^#([0-9]{1,9})$ ]]; then
    v=$(gh pr view "${BASH_REMATCH[1]}" --repo "$repo" --json state,isCrossRepository,baseRefName,mergeCommit,commits \
      --jq '"\(.state) \(.isCrossRepository) \(.baseRefName) \(.mergeCommit.oid) \(.commits | length)"') ||
      finish skipped unknown-ref
    read -r s x b after k <<< "$v"
    [ "$s" = MERGED ] || finish skipped not-merged
    [ "$x" = false ] || finish skipped fork-pr
    [ "$b" = "$ref" ] || finish skipped other-base
    [[ $after =~ ^[0-9a-f]{40}$ ]] || finish skipped unknown-ref
  elif [[ $1 =~ ^[0-9a-f]{7,40}$ ]]; then
    after=$(git rev-parse -q --verify "$1^{commit}") || finish skipped unknown-ref
    k=1
  else
    finish skipped fixed-ref
  fi
  git merge-base --is-ancestor "$after" "$tip" || finish skipped not-ancestor
  [ "$k" = 1 ] || [ "$(git rev-list --parents -n 1 "$after" | wc -w)" = 3 ] || finish skipped ambiguous-baseline
  before=$(git rev-parse -q --verify "$after^1") || finish skipped root-commit
  commit=$after

  step=spec
  spec_item

  step=verify
  mkdir -p "$item/verify/base" "$item/verify/patch"
  git archive "$before" | tar -x -C "$item/verify/base"
  git archive "$after" | tar -x -C "$item/verify/patch"
  stage verify "$item/verify" reproduce.md Bash,Read,Grep,Glob "$before" "$item/spec.md" "$item/run.md"
  take "$item/evidence/verify/verify.md" "$item/verify.md"
  v=$(tail -n 1 "$item/verify.md")
  case $v in
    "verify: outcome=confirmed" | "verify: outcome=insufficient" | "verify: outcome=inconclusive") echo "$id $v" ;;
    *) exit 1 ;;
  esac
  { if [ "$v" = "verify: outcome=confirmed" ]; then
      printf 'Verified: the merged fix %s (%s) resolves this; its parent %s showed the broken state.\n' \
        "$1" "$after" "$before"
    else
      printf 'Not confirmed: the merged fix %s (%s) against its parent %s ended `%s`. Not re-filed.\n' \
        "$1" "$after" "$before" "$v"
    fi
    printf '\n## Spec\n\n'; cat "$item/spec.md"
    printf '\n## Verification\n\n'; clip 60 < "$item/verify.md"
    printf '\nEvidence: `.factory/reports/fix-issues/items/%s/evidence/` on the runner.\n' "$id"; } > "$item/body.md"
  sendable "$item/body.md" || finish deferred dry-run

  step=link
  send "$id" "$item/body.md" "$after"
  [ "$v" != "verify: outcome=confirmed" ] || finish fixed "$linked"
  finish blocked not-confirmed
}

# $1 nonempty: a merged same-repo linked PR is the fix under verification; any other linked PR skips.
linked_pr() {
  local lp r n
  [[ $id != *[!0-9]* ]] || return 0
  lp=$(gh issue view "$id" --repo "$repo" --json closedByPullRequestsReferences \
    --jq '.closedByPullRequestsReferences[] | "\(.repository.owner.login)/\(.repository.name) \(.number)"')
  [ -n "$lp" ] || return 0
  [ -n "${1:-}" ] || finish skipped linked-pr
  while read -r r n; do
    [ "$r" = "$repo" ] && [[ $n =~ ^[0-9]+$ ]] &&
      [ "$(gh pr view "$n" --repo "$repo" --json state --jq .state)" = MERGED ] || finish skipped linked-pr
  done <<< "$lp"
}

recover_item() {
  local urls feature
  urls=$(gh pr list --repo "$repo" --head "factory/fix-$1" --state all --json url,isCrossRepository \
    --jq '.[] | select(.isCrossRepository | not) | .url')
  if [ -z "$urls" ]; then
    [ "$(git ls-remote "$remote" "refs/heads/factory/fix-$1" | cut -f1)" = "$2" ] ||
      { echo "recover: factory/fix-$1 is not at $2" >&2; exit 1; }
    sendable "$items/$1/body.md" || return 0
    feature=$(sed -n '1s/^feature: //p' "$items/$1/spec.md")
    urls=$(gh pr create --repo "$repo" --draft --base "$ref" --head "factory/fix-$1" \
      --title "fix: $(tag "$1") $feature" --body-file "$items/$1/body.md")
    echo "recover: $urls"
  fi
  link_item "$1" "${urls%%$'\n'*}" "$2" "$3"
}

recover() {
  local id c e b
  [ -f "$fx/pushed.tsv" ] || return 0
  while read -r id c e b; do
    [ "$e" = "$entry" ] && [ -z "$(row "$fx/linked.tsv" "$id")" ] || continue
    try recover_item "$id" "$c" "$b" < /dev/null
  done < <(awk '{r[$1] = $0} END {for (i in r) print r[i]}' "$fx/pushed.tsv")
}

release() {
  local f
  set +e
  [ -n "$outcome" ] || outcome=blocked reason=$step
  printf '%s %s %s\n%s %s\n%s\n' "$outcome" "$reason" "$url" "$start" "${commit:-$start}" "$stat" > "$runview/outcomes/$id"
  [ -n "$claimed" ] || return
  if [ "$step" = publish ] && [ -n "$commit" ] &&
    [ "$(git ls-remote "$remote" "refs/heads/$branch" | cut -f1)" = "$commit" ]; then
    printf '%s %s %s %s\n' "$id" "$commit" "$entry" "$start" >> "$fx/pushed.tsv"
  fi
  if [ -d "$item/evidence" ]; then
    mkdir -p "$out/evidence"
    (cd "$item/evidence" && find . -type f -size -10485760c -print0 | tar --null -T - -cf -) | tar -x -C "$out/evidence"
  fi
  for f in spec.md body.md; do [ ! -f "$item/$f" ] || cp "$item/$f" "$out/"; done
  [ "${FACTORY_DRY_RUN:-0}" = 1 ] || [ "$outcome" = deferred ] ||
    printf '%s issue-pipeline: outcome=%s reason=%s base=%s commit=%s pr=%s\n' \
      "$day" "$outcome" "$reason" "$start" "${commit:-none}" "$url" >> "$out/summary.md"
  rm -rf "$item"
  git worktree prune
}

run_item() {
  local r prs
  id=$1 feature=$2 item=$fx/tmp/fix-$1
  view=$item out=$items/$1 branch=factory/fix-$1 title="fix: $(tag "$1") $2"
  outcome="" reason="" url=none step=claim claimed="" ticket="" red="" stat=""
  trap release EXIT
  mkdir "$item" 2> /dev/null || finish skipped claimed
  claimed=1
  mkdir -p "$out"
  prs=$(gh pr list --repo "$repo" --head "$branch" --state all --json url,isCrossRepository \
    --jq '.[] | select(.isCrossRepository | not) | .url')
  [ -z "$prs" ] || finish skipped pr-exists
  ! git ls-remote --exit-code -q "$remote" "refs/heads/$branch" > /dev/null || finish skipped branch-exists
  printf '%s\n' 'No git commit or git push, no gh, no tracker or chat writes, no edits outside the working directory and $evidence.' \
    'Unattended run: never ask a question; nobody answers.' \
    'In fix.md, before its last line, one line per existing test file you changed: test-change: <path from the repo root>: <one-line reason>.' \
    'Never delete or rename a test file.' > "$item/bans.md"
  { awk '/^## /{p = $0 == "## Run"} p' .factory/profile.md; grep '^- Scripts: ' .factory/profile.md || true; } > "$item/run.md"
  [ -z "$3" ] || verify_item "$3"
  [ "$flow" = fix ] || commentable

  step=spec
  spec_item

  step=reproduce
  mkdir "$item/repro"
  git archive "$start" | tar -x -C "$item/repro"
  stage reproduce "$item/repro" reproduce.md Bash,Read,Grep,Glob "$start" "$item/spec.md" "$item/run.md"
  take "$item/evidence/reproduce/repro.md" "$item/repro.md"
  r=$(tail -n 1 "$item/repro.md")
  case $r in "repro: outcome=reproduced" | "repro: outcome=not-reproduced") echo "$id $r" ;; *) exit 1 ;; esac
  [ "$r" = "repro: outcome=reproduced" ] || finish not-reproduced reproduce
  [ "$flow" = fix ] || repro_item

  step=fix
  linked_pr
  git worktree add -q --detach "$item/patch" "$start"
  stage fix "$item/patch" fix.md Bash,Read,Grep,Glob,Edit,Write "$start" \
    "$item/spec.md" "$item/repro.md" "$item/run.md" "$runview/skills/debugging"
  take "$item/evidence/fix/fix.md" "$item/fix.md"
  [ "$(tail -n 1 "$item/fix.md")" = "fix: outcome=changed" ] || exit 1
  cp "$item/fix.md" "$item/summary.md"
  git -C "$item/patch" add -A
  git -C "$item/patch" commit -q -m "fix: $feature ($(tag "$id"))"
  commit=$(git -C "$item/patch" rev-parse HEAD) work=$item/patch
  stat=$(git diff --shortstat "$start" "$commit" | sed 's/^ //')

  step=gates
  gates
  red_green

  step=verify
  mkdir -p "$item/verify/base" "$item/verify/patch"
  git archive "$start" | tar -x -C "$item/verify/base"
  git archive "$commit" | tar -x -C "$item/verify/patch"
  stage verify "$item/verify" fix.md Bash,Read,Grep,Glob "$start" "$item/spec.md" "$item/repro.md" "$item/run.md"
  take "$item/evidence/verify/verify.md" "$item/verify.md"
  [ "$(tail -n 1 "$item/verify.md")" = "verify: outcome=confirmed" ] || exit 1
  echo "$id verify: outcome=confirmed"
  cat "$item/spec.md" "$item/repro.md" "$item/verify.md" | no_creds || block "credential-shaped text"
  [ "${FACTORY_DRY_RUN:-0}" != 1 ] || finish deferred dry-run

  step=ticket
  [[ $id != err-* ]] || ticket_item

  step=publish
  body > "$item/summary.md"
  publish > "$item/pr-url"
  url=$(tail -n 1 "$item/pr-url")
  printf '%s %s %s %s\n' "$id" "$commit" "$entry" "$start" >> "$fx/pushed.tsv"

  step=link
  link_item "$id" "$url" "$commit" "$start"
  finish fixed "$linked"
}

pipeline() {
  local id feature why fref o r u p sel=() started="" halt=""
  runview=$view report=$out/$day.md start=$(git rev-parse "$ref")
  [[ $cap =~ ^[1-9][0-9]*$ ]] || block "cap $cap is not a positive whole number"
  [[ $flow =~ ^(fix|repro-only)$ ]] || block "flow $flow is not fix or repro-only"
  [[ $verify_fixed =~ ^(on|off)$ ]] || block "verify-fixed $verify_fixed is not on or off"
  preflight
  [ "${FACTORY_DRY_RUN:-0}" = 1 ] || recover
  for p in ${trust[@]+"${trust[@]}"}; do sel+=(--trust "$p"); done
  [ -z "$label" ] || sel+=(--label "$label")
  [ "$verify_fixed" = on ] || sel+=(--no-verify)
  python3 -I "$view/skills/fix-issues/scripts/check_items.py" --select "$report" "$view/input/items" "$cap" \
    ${sel[@]+"${sel[@]}"} > "$view/select.tsv"
  mkdir "$view/outcomes"
  printf '\n## Pipeline\n\n' >> "$report"
  grep -qE $'\t(fix$|verify\t)' "$view/select.tsv" || echo "pipeline: no candidates" | tee -a "$report"
  while IFS=$'\t' read -r id feature why fref; do
    u=none
    case $why in
      fix | verify)
        if [ -n "$halt" ]; then o=deferred r=$halt
        elif [ -e .factory/pause ]; then o=deferred r=paused
        # Three stages, the test command and the spec-writer, each at its timeout.
        elif [ $((run_minutes * 60 - SECONDS)) -lt $(((4 * minutes + 5) * 60)) ]; then o=deferred r=run-time
        elif [ -n "$started" ] && [ "${FACTORY_DRY_RUN:-0}" = 1 ]; then o=deferred r=dry-run
        else
          started=1 o=blocked r=error
          try run_item "$id" "$feature" "$fref" < /dev/null
          [ ! -f "$view/outcomes/$id" ] || read -r o r u < "$view/outcomes/$id"
          [ "$r" != runner-error ] || halt=runner-error
          [ "${FACTORY_DRY_RUN:-0}" != 1 ] || { echo "dry run: $id $o $r"; o=deferred r=dry-run u=none; }
        fi ;;
      same-feature | cap) o=deferred r=$why ;;
      *) o=skipped r=$why ;;
    esac
    echo "pipeline: id=$id outcome=$o reason=$r pr=$u" | tee -a "$report"
  done < "$view/select.tsv"
  [ -z "$halt" ] || { echo "pipeline: stopped on a runner error" >&2; exit 1; }
}
