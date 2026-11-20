#!/usr/bin/env bash
# merge-gate v6, installed by the ship skill; upgrade from there, not by hand.
# Usage: merge-gate.sh <pr-number> [head-sha]. Prints blocking reasons, one per line; none means auto-merge eligible.
# MERGE_GATE_LOCAL=1: no installed gate; skip the ship opt-in and require green CI on the head instead.
# Exits non-zero when it can't evaluate; treat that as blocked, never as eligible.
set -euo pipefail

pr=$1
policy=$(cat "${MERGE_POLICY:-$(dirname "$0")/../merge-policy.json}")
local_mode=${MERGE_GATE_LOCAL:-0}
meta=$(gh pr view "$pr" --json baseRefName,headRefOid,isDraft,labels,reviewDecision)
trunk=$(gh api 'repos/{owner}/{repo}' --jq .default_branch)
head=${2:-$(jq -r .headRefOid <<<"$meta")}
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
gh api --paginate "repos/{owner}/{repo}/pulls/$pr/files" | jq -s add >"$tmp/files"
# Large diffs exceed the API's limit; the patch then can't match and the PR blocks.
gh pr diff "$pr" --color never >"$tmp/diff" 2>/dev/null || : >"$tmp/diff"
patch=$(git patch-id --verbatim <"$tmp/diff" | cut -c1-12)
review=$(gh api --paginate "repos/{owner}/{repo}/commits/$head/statuses" | jq -sc \
  '[add[] | select(.context == "agent-review")][0] // {state: "missing"} | {state, description: (.description // "")}')
checks='[]' behind=0
if [ "$local_mode" = 1 ]; then
  # Some CI reports on GitHub's test merge commit instead of the head; read both.
  merge_sha=$(gh api "repos/{owner}/{repo}/pulls/$pr" --jq '.merge_commit_sha // empty')
  for sha in $head $merge_sha; do
    gh api --paginate "repos/{owner}/{repo}/commits/$sha/check-runs" | jq -sc --arg sha "$sha" \
      '[.[].check_runs[] | {name, sha: $sha, done: (.status == "completed"),
        actions: (.app.slug == "github-actions" and .conclusion == "success"),
        ok: (.status == "completed" and (.conclusion | IN("success", "neutral", "skipped"))),
        state: (if .status == "completed" then .conclusion else .status end)}]'
    gh api --paginate "repos/{owner}/{repo}/commits/$sha/status?per_page=100" | jq -sc --arg sha "$sha" \
      '[.[].statuses[] | select(.context != "agent-review")
        | {name: .context, sha: $sha, done: (.state != "pending"), ok: (.state == "success"), state}]'
  done >"$tmp/checks"
  checks=$(jq -sc add "$tmp/checks")
  behind=$(gh api "repos/{owner}/{repo}/compare/$trunk...$head" --jq .behind_by)
fi

jq -nr --argjson p "$policy" --argjson m "$meta" --slurpfile fs "$tmp/files" --rawfile diff "$tmp/diff" \
  --argjson review "$review" --arg patch "$patch" --argjson checks "$checks" --arg local "$local_mode" --argjson behind "$behind" '
  def matches($res): . as $s | any($res[]; . as $r | $s | test($r));
  $fs[0] as $f
  | ([$f[] | select(.filename | matches($p.exclude_from_size) | not) | .additions + .deletions] | add // 0) as $lines
  | [$f[] | .filename, (.previous_filename // empty)] as $paths
  | (if $m.isDraft then "draft" else empty end),
    (if $m.baseRefName != $trunk then "stacked on \($m.baseRefName), not \($trunk)" else empty end),
    (if $m.reviewDecision == "CHANGES_REQUESTED" then "changes requested in review" else empty end),
    (if $local == "1" or any($m.labels[]; .name == "ship") then empty else "missing opt-in label ship" end),
    (if $local != "1" then empty
     elif any($checks[]; .done | not) then ($checks[] | select(.done | not) | "check \(.name) still running (\(.state)) on \(.sha[0:7])")
     elif any($checks[]; .actions) | not then "no passing GitHub Actions run on \($head[0:7]), nothing verifies the change"
     else ($checks[] | select(.ok | not) | "check \(.name) is \(.state) on \(.sha[0:7])") end),
    (if $behind > 0 then "\($behind) commits behind \($trunk), CI has not tested it against the current base" else empty end),
    (if $lines > $p.max_changed_lines then "\($lines) changed lines > \($p.max_changed_lines)" else empty end),
    (if ($f | length) > $p.max_files then "\($f | length) files > \($p.max_files)" else empty end),
    ($paths[] | select(matches($p.deny_paths)) | "protected path: \(.)"),
    ($f[] | select(.status != "added" and ([.filename, (.previous_filename // empty)] | any(matches($p.test_paths)))
        and (.deletions > 0 or .status == "renamed" or .status == "removed"))
      | "rewrites existing test: \(.previous_filename // .filename)"),
    ($diff | [splits("(?m)^diff --git ")][1:][]
      | (capture("(?m)^\\+\\+\\+ b/(?<f>.+)$").f // empty) as $file
      | select(($file | matches($p.test_paths)) and ($file | endswith(".snap") | not)
        and test("(?m)^\\+(?!\\+\\+ ).*(\\.(only|skip)\\(|\\bx(it|describe)\\(|@pytest\\.mark\\.(skip|xfail)|t\\.Skip\\(|#\\[ignore\\])"))
      | "adds skip/focus marker: \($file)"),
    (if $review.state != "success" then "agent-review is \($review.state) on \($head[0:7])"
     elif $patch == "" then "PR diff unavailable (too large?), cannot check agent-review patch"
     elif ($review.description | endswith("approved patch \($patch)")) then empty
     else "agent-review approved a different patch than the PR diff (\($patch))" end)
' --arg head "$head" --arg trunk "$trunk"
