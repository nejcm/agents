#!/usr/bin/env bash
# Factory automation; step rules in automate-factory references/safety.md.
set -euo pipefail
cd "$(dirname "$0")/../.."
entry=$(basename "$0" .sh)
day=$(date +%F)
out=.factory/reports/$entry
mkdir -p "$out" .factory/tmp
[ -e .factory/tmp/.gitignore ] || echo '*' > .factory/tmp/.gitignore
view=$(mktemp -d ".factory/tmp/$entry.XXXXXX")
trap 'rm -rf "$view"' EXIT
mkdir "$view/repo" "$view/input" "$view/skills"
ref="<base>"
auth="<auth>" max_turns="<turns>"
# Higher-precedence credentials would bill the run instead of the chosen auth.
unset ANTHROPIC_AUTH_TOKEN ANTHROPIC_PROFILE \
  CLAUDE_CODE_USE_BEDROCK CLAUDE_CODE_USE_VERTEX CLAUDE_CODE_USE_FOUNDRY
[ "$auth" = api-key ] || unset ANTHROPIC_API_KEY
git archive "$ref" | tar -x -C "$view/repo"

# Project skills are repo-relative, read from the tracked snapshot and must resolve inside it;
# only regular, non-hidden .md and .py files are copied.
skills=()
snap=$(cd -P "$view/repo" && pwd)
for s in ${skills[@]+"${skills[@]}"}; do
  case "$s" in /*) src=$s ;; *) src=$view/repo/$s ;; esac
  real=$(cd -P "$src" && pwd)
  case "$s" in
    /*) ;;
    *) case "$real/" in "$snap"/*) ;; *) echo "skill $s resolves outside the snapshot" >&2; exit 1 ;; esac ;;
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
    --no-session-persistence --permission-mode dontAsk --max-turns "$max_turns" --output-format text \
    "$prompt" < /dev/null) \
    > "$view/report.md"
  test -s "$view/report.md"
  mv "$view/report.md" "$out/$day.md"
}

post_check() { :; }

post() { :; }

fetch
analyze
post_check
[ "${FACTORY_DRY_RUN:-0}" = 1 ] || post
