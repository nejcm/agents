# Weekly agent analytics

- **Trigger**: weekly, Monday 07:00.
- **Requires**: this repo's transcripts on the runner's machine; `agent-analytics` installed (it
  ships in this preset and is found only after `ulis install`; see
  [loading other skills](../../../setup-factory/SKILL.md#loading-other-skills)); `python3`. `gh` optional (sessions per merged PR).
- **Runners**: local.
- **Input**: counter fields only; no model runs and no text is read.
- **Writes**: `.factory/reports/<date>-agents.md` only.
- **Write levels**: report.
- **Steps**: `skills=("<skill-path:agent-analytics>")`; fetch none; analyze is the parser. Every
  command's status reaches `set -e`, and the report comes from this run's view:

  ```bash
  analyze() {
    local since merged=()
    since=$(python3 -c 'import datetime as d; print(d.date.today() - d.timedelta(7))')
    if gh pr list --state merged --limit 200 --json url,headRefName,isCrossRepository \
      > "$view/prs.json"; then merged=(--merged "$view/prs.json"); fi
    python3 "$view/skills/agent-analytics/scripts/agent_analytics.py" \
      ${merged[@]+"${merged[@]}"} --since "$since" > "$view/report.md"
    test -s "$view/report.md"
    mv "$view/report.md" ".factory/reports/$day-agents.md"
  }
  ```

- **Choices**: none; it has no model, so no model picks.

## Prompt

None: the parser is the whole run. `.factory/automations/weekly-agent-analytics.md` is not written.
