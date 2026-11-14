#!/usr/bin/env bash
# merge-gate v2, installed by the ship skill; upgrade from there, not by hand.
# Usage: merge-gate.sh <pr-number> [head-sha]. Prints blocking reasons, one per line; none means auto-merge eligible.
set -euo pipefail

pr=$1
policy=$(cat "$(dirname "$0")/../merge-policy.json")
meta=$(gh pr view "$pr" --json headRefOid,isDraft,labels,reviewDecision)
head=${2:-$(jq -r .headRefOid <<<"$meta")}
files=$(gh api --paginate "repos/{owner}/{repo}/pulls/$pr/files" | jq -s add)
review=$(gh api "repos/{owner}/{repo}/commits/$head/statuses" \
  --jq "[.[] | select(.context == \"agent-review\")][0].state // \"missing\"")

jq -nr --argjson p "$policy" --argjson m "$meta" --argjson f "$files" --arg review "$review" '
  def matches($res): . as $s | any($res[]; . as $r | $s | test($r));
  ([$f[] | select(.filename | matches($p.exclude_from_size) | not) | .additions + .deletions] | add // 0) as $lines
  | [$f[] | .filename, (.previous_filename // empty)] as $paths
  | (if $m.isDraft then "draft" else empty end),
    (if $m.reviewDecision == "CHANGES_REQUESTED" then "changes requested in review" else empty end),
    (if any($m.labels[]; .name == "ship") then empty else "missing opt-in label ship" end),
    (if $lines > $p.max_changed_lines then "\($lines) changed lines > \($p.max_changed_lines)" else empty end),
    (if ($f | length) > $p.max_files then "\($f | length) files > \($p.max_files)" else empty end),
    ($paths[] | select(matches($p.deny_paths)) | "protected path: \(.)"),
    ($f[] | select(.status != "added" and ([.filename, (.previous_filename // empty)] | any(matches($p.test_paths)))
        and (.deletions > 0 or .status == "renamed" or .status == "removed"))
      | "rewrites existing test: \(.previous_filename // .filename)"),
    (if $review == "success" then empty else "agent-review is \($review) on \($head[0:7])" end)
' --arg head "$head"
