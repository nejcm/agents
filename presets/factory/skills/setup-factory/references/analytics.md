# Phase 5: Agent analytics

A baseline of how agents have worked in this repo so far, from the `agent-analytics` skill.
Needs no earlier phase.

## Steps

1. Load `agent-analytics` by path (see SKILL.md, loading other skills) and follow it with no
   `--since`, so the baseline covers all local history.
2. Its report lands at `.factory/reports/<YYYY-MM-DD>-agents.md`. Its `.gitignore` proposal
   follows this skill's write rule.
3. Do not open transcripts to explain the numbers. Struggles behind them are `retro`'s job.

## Output

The profile's `Agent analytics` section: the period, the report path, and from the report's
totals: sessions per harness, total tokens (uncached input, cache write, cache read, output), cost
and how many sessions reported it, failed tool calls against the tool calls of the same harness
(never against the all-harness total), retries, escalations, sessions per merged PR, and each
harness's unavailable metrics. Copy numbers as reported; never fill an
unavailable one.
