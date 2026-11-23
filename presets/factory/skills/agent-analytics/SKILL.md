---
name: agent-analytics
description: Use when the user asks for agent usage numbers for a repo — sessions, tokens, cost, failed tool calls, retries, escalations, sessions per merged PR — from local Claude Code, Codex and Cursor transcripts
category: workflow
disable-model-invocation: true
---

# Agent analytics

Totals for this repo's agent sessions, counted from local transcripts by
[`scripts/agent_analytics.py`](scripts/agent_analytics.py). The script reads only counter and
structural fields and prints a Markdown report. No transcript text enters the report or your
context. Run from the repo root.

## Run

1. **Period**: all history by default; for a recurring report pass `--since <YYYY-MM-DD>` (the
   period's first day). It filters by transcript modification time.
2. **Generate**: fetch merged PRs only if `gh` succeeds, and replace the report only after the
   script succeeds, from per-run temp files, so a failure or an overlapping run never leaves an
   empty or partial report:

   ```bash
   mkdir -p .factory/reports .factory/tmp
   prs=$(mktemp .factory/tmp/merged-prs.XXXXXX) report=$(mktemp .factory/tmp/agents.XXXXXX)
   merged=()
   gh pr list --state merged --limit 200 --json url,headRefName,isCrossRepository \
     >| "$prs" && merged=(--merged "$prs")
   python3 <skill-dir>/scripts/agent_analytics.py "${merged[@]}" [--since <date>] \
     >| "$report" && mv "$report" .factory/reports/<YYYY-MM-DD>-agents.md
   rm -f "$prs" "$report"
   ```

   Without `gh` or a GitHub remote the report marks sessions per merged PR unavailable.
   `<skill-dir>` is this skill's resolved directory. Needs `python3` (3.8+), standard library only.
3. **Ignore rule**: if `git check-ignore -q .factory/reports/x` fails, propose adding
   `.factory/reports/` to `.gitignore` and apply it only after the user confirms.
4. **Reply** with the report path, the totals table, and the coverage lines. Never open
   transcripts to explain a number; this skill reports counts only. For why sessions went wrong,
   point to the `retro` skill.

## What is counted

Scope is this repo: transcripts whose recorded cwd is the repo root or a path under it
(worktrees inside the repo included).

| Harness | Source | Counted | Unavailable |
| ------- | ------ | ------- | ----------- |
| Claude Code | `~/.claude/projects/<path, non-alphanumerics as ->/*.jsonl`, subagents in `<session>/subagents/` | tokens per API message (deduped by message id), cost from the last `cost-state.totalCostUSD`, `tool_use` calls, `tool_result.is_error`, `system` `api_error` retries, `AskUserQuestion` calls, `pr-link` URLs, `gitBranch` | none |
| Codex | `~/.codex/sessions/**/rollout-*.jsonl` whose `session_meta.cwd` is in the repo; `thread_source` `subagent`/`guardian_review` count as subagent transcripts | last cumulative `token_count.total_token_usage`, tool calls, `request_user_input*` calls, `session_meta.git.branch` | cost, failed tool calls, retries (tool output carries no structured error) |
| Cursor | `~/.cursor/projects/<path, non-alphanumeric runs as ->/agent-transcripts/**/*.jsonl` | sessions, `tool_use` calls | tokens, cost, failed tool calls, retries, escalations, PR links (no usage or result fields) |

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
- Every report lists coverage per harness and the metrics it could not count.

## Rules

- Never print, quote or summarize transcript text, prompts, tool inputs or outputs, and never
  write paths outside the repo into a report. If a number needs explaining, say it needs a
  `retro`, not a transcript read.
- Field names changed upstream (a harness shows 0 tokens for sessions that clearly used tokens):
  report the harness as unreliable for that metric, do not patch numbers by hand. Fix the parser
  and its fixtures in [`tests/`](tests/) together.
- Tests: `python3 -B -m unittest discover -s <skill-dir>/tests`.
