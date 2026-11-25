---
name: agent-analytics
description: Use when the user asks for agent usage numbers for a repo — sessions, tokens, cost, failed tool calls, retries, escalations, sessions per merged PR — from factory run records and local Claude Code, Codex, Cursor and Antigravity transcripts
category: workflow
disable-model-invocation: true
---

# Agent analytics

Totals for this repo's agent work, counted by
[`scripts/agent_analytics.py`](scripts/agent_analytics.py): factory run records first, local
transcripts second. The script reads only counter and structural fields and prints a Markdown
report. No transcript or record text enters the report or your context. Run from the repo root.

## Run

1. **Period**: all history by default; for a recurring report pass `--since <YYYY-MM-DD>` (the
   period's first day). It filters by transcript modification time.
2. **Generate**: fetch merged PRs only if `gh` succeeds, and replace the report only after the
   script succeeds, from per-run temp files, so a failure or an overlapping run never leaves an
   empty or partial report:

   ```bash
   mkdir -p .factory/reports .factory/tmp
   [ -e .factory/tmp/.gitignore ] || echo '*' > .factory/tmp/.gitignore
   prs=$(mktemp .factory/tmp/merged-prs.XXXXXX) report=$(mktemp .factory/tmp/agents.XXXXXX)
   merged=()
   gh pr list --state merged --limit 200 --json url,headRefName,isCrossRepository \
     >| "$prs" && merged=(--merged "$prs")
   rc=0
   python3 <skill-dir>/scripts/agent_analytics.py "${merged[@]}" [--since <date>] >| "$report" || rc=$?
   if [ "$rc" = 0 ] || [ "$rc" = 3 ]; then mv "$report" .factory/reports/<YYYY-MM-DD>-agents.md; fi
   rm -f "$prs" "$report"
   echo "agent_analytics exit $rc"
   ```

   Without `gh` or a GitHub remote the report marks sessions per merged PR unavailable.
   `<skill-dir>` is this skill's resolved directory. Needs `python3` (3.8+), standard library only.
3. **Ignore rule**: if `git check-ignore -q .factory/reports/x` fails, propose adding
   `.factory/reports/` to `.gitignore` and apply it only after the user confirms.
4. **Drift**: exit 3 means the report was written but has a "Format drift" section; follow
   [Repair on drift](#repair-on-drift) before replying.
5. **Reply** with the report path, the totals table, and the coverage lines. Never open
   transcripts to explain a number; this skill reports counts only. For why sessions went wrong,
   point to the `retro` skill.

## What is counted

**Factory runs** come from `.factory/reports/runs.jsonl`, one line per scheduled run, written by
the run script ([runners.md](../automate-factory/references/runners.md#run-record)). Per entry:
runs, dry runs, outcomes (`escalated` among them), item outcomes for `issue-pipeline`, escalation
reasons (`ci-cap` among them), runs and items that disclosed existing-test changes (and how many
files) or dependencies, turns,
tokens and cost (the CLI's own estimate), and for reviewed PRs, joined with
`.factory/reports/fix-issues/fates.tsv`: reviewer approve rate, agreement with the human outcome
(a human merge is agreement with approve; closed, reverted or a change request with changes; a
factory merge is not a human outcome), misses
(approved, then closed or reverted) and merge rates by scope; a run whose record has no usage or cost is counted as a run and listed under coverage. `--since` filters by the record's
start date. Factory runs keep no transcript, so they are not counted again below. Gate messages,
items and commits stay in the file, never in the report.

**Sessions**: scope is this repo: transcripts whose recorded cwd is the repo root or a path under it
(worktrees inside the repo included). Sessions a host such as T3 Code launches land in the same
harness dirs and count the same way. `$CLAUDE_CONFIG_DIR` and `$CODEX_HOME` are read in addition to
`~/.claude` and `~/.codex`.

| Harness | Source | Counted | Unavailable |
| ------- | ------ | ------- | ----------- |
| Claude Code | `~/.claude/projects/<path, non-alphanumerics as ->/*.jsonl`, subagents in `<session>/subagents/`; in the repo's exact dir any recorded cwd in the repo counts (a session moved in from a scratch dir), in prefix dirs the first | tokens per API message (deduped by message id), cost from the last `cost-state.totalCostUSD`, `tool_use` calls, `tool_result.is_error`, `system` `api_error` retries, `AskUserQuestion` calls, `pr-link` URLs, `gitBranch` | none |
| Codex | `~/.codex/{sessions,archived_sessions}/**/rollout-*.jsonl` whose `session_meta.cwd` is in the repo; `thread_source` `subagent`/`guardian_review` count as subagent transcripts (T3 Code marks the threads it delegates `subagent`) | last cumulative `token_count.total_token_usage`, tool calls, `request_user_input*` calls, `session_meta.git.branch` | cost, failed tool calls, retries (tool output carries no structured error) |
| Cursor | `~/.cursor/projects/<path, non-alphanumeric runs as ->/agent-transcripts/**/*.jsonl` | sessions, `tool_use` calls | tokens, cost, failed tool calls, retries, escalations, PR links (no usage or result fields) |
| Antigravity | SQLite `conversations/*.db` (read-only) under `~/.gemini/antigravity-cli/` and T3 Code's `~/.t3/userdata/providers/antigravity/*/antigravity-acp/`, whose workspace URI (`trajectory_metadata_blob`) is in the repo; column shown only when found | tokens per `gen_metadata` record (protobuf usage fields) | cost, tool calls, failed tool calls, retries, escalations, PR links, subagents (not decoded) |

- **Cost** is the harness's own estimate (Claude Code `cost-state`), never derived from a price
  table. The report says how many sessions reported it.
- **Escalations** are questions to the user through the harness's ask tool.
- **Sessions per merged PR** counts only sessions explicitly linked to a merged PR, divided by the
  merged PRs with at least one linked session. A recorded PR URL links on its own; a session with
  no URL links by branch only when exactly one merged PR has that head branch and it is not from a
  fork. Without a link it is unavailable, never inferred from timing.
- **Scope and dedup**: recorded cwds are normalized (symlinks, `..`) before the repo check, a
  session split across files counts once (by session id), and a subagent transcript with a cwd
  outside the repo is dropped. Unreadable files are skipped and counted, never named.
- A metric with no reading (no usage record, no cost snapshot) is unavailable, not zero.
- **Format drift**: a harness with 5+ sessions in which an expected record shape (usage records,
  tool calls, `is_error` flags, `token_count`, Antigravity `gen_metadata` usage) was recognised zero times gets a drift warning, its
  dependent metrics show "unverified" instead of 0, and the script exits 3.
- Every report lists coverage per harness and the metrics it could not count.

## Rules

- Never print, quote or summarize transcript text, prompts, tool inputs or outputs, and never
  write paths outside the repo into a report. If a number needs explaining, say it needs a
  `retro`, not a transcript read.
- Never patch numbers by hand; a wrong count is fixed in the parser.
- Tests: `python3 -B -m unittest discover -s <skill-dir>/tests`.

## Repair on drift

1. Pick ONE recent in-repo transcript of the drifted harness and print its structure only:
   `python3 <skill-dir>/scripts/agent_analytics.py --shape <file>`. It opens only the containers
   the parser reads (top level, `message`, its `content` blocks, `usage`, `payload`, `info`,
   `total_token_usage`, `git`) and prints their keys and value types; every other object or list
   prints as its type, unknown `type` values and ID-like keys as `?`. Never read the file any
   other way. Antigravity databases are protobuf in SQLite; `--shape` does not read them, so an
   Antigravity drift stays "unverified" until the parser is updated from a synthetic fixture.
2. Find the new name or nesting for the missing shape. Extend the parser to accept it and keep the
   old shape supported.
3. Add a synthetic fixture for the new shape (made-up values) and a test in [`tests/`](tests/);
   run the tests.
4. Rerun the report, show the user the diff, and do not commit unasked.
5. If the new shape cannot be identified confidently, change nothing: leave the metric
   "unverified" and say so.
