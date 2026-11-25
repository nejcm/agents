# Phase 2: Interview

One batched round of questions, only for the `Open gaps` in the profile's `Repo` section and
topics below that phase 1 could not establish. Then follow-ups only on
the items the user selected. Skip the phase when there are no gaps.

## Shape

- Number every question. Offer multiple choice built from what phase 1 found, plus "other" and
  "skip", so the user can answer with `1b 2a 3 skip`.
- Pre-fill what was detected and ask for confirmation rather than an open answer
  ("Sentry SDK found in `src/sentry.ts`. How should an agent reach it? a) MCP b) `sentry-cli`
  logged in c) API env var d) not reachable").
- Never ask for a secret value. Ask how access works, never what the credential is.

## Topics (gaps only)

1. **Issue sources**: GitHub Issues, Linear, Jira, Slack channels, error trackers; which one is
   the source of truth. For each one an agent should read, its fetch: the tool (MCP server name,
   CLI or API), the read-only operations (MCP tool names, or the exact CLI or API command), the
   query and filters (project, labels, states, lookback), the field holding the item's immutable
   ID, and a short prefix (`err-<source>` for an error tracker). Pre-fill from the server's tool list or
   the CLI's help; the user confirms.
   For each one, its trust for unattended fixes: `trusted` (any item may get a draft PR),
   `label <name>` (only open issues carrying that maintainer-applied label; `gh` only, since
   agent-fetched labels are model output over issue text), or `none` (default). For an error
   tracker marked `trusted`, warn once that its events carry strings any app user can set.
   For each one runs should write back to (other than GitHub), its writes: which of `ticket`,
   `comment`, `status`, `post`; for each, a CLI or API command (preferred) or one MCP write tool
   with its body and item (or title) arguments; the fixed destination (team, channel, status
   state); never a closing status.
2. **Error and analytics tools**: for each detected or named tool, how an agent reaches it
   (MCP server, logged-in CLI, API env var, none).
3. **Results and escalations**: where reports, questions and failures go (PR comment, issue,
   Slack channel, email, a file in `.factory/reports/`).
4. **Deploy targets**: environments and how they deploy (CI on merge, manual, platform name),
   and which ones an agent may touch (default: none).
5. **Budgets**: per run in minutes and turns (default 30 and 200); per scheduled `issue-pipeline`
   run that opens PRs, in minutes (default 240) and items (default 3); per week in USD of the
   CLI's cost estimate (default none; a run at or over it stops before any model call). Models,
   schedules, extra skills and stage skills are per entry, asked by `automate-factory` when it
   places each entry.
   Runs use the subscription login of each CLI the user picks (`claude`, `codex`, `agy`), never an API
   key; a run on a non-Claude CLI reports no cost, so the weekly budget counts only reported cost.
6. **Review**: who reviews agent PRs, and whether agents may open PRs at all (drafts only, or
   ready ones too). Scheduled runs open PRs only where `automate-factory` sets that write level.
   For `issue-pipeline`, `merge_level` stays `draft` unless the user picks more. Offer `ready` or
   `merge` only together with that entry's `Review:` line from the latest `agent-analytics`
   report (approve rate, agreement with human outcomes, misses, merge rates by scope); with no
   line or no resolved PR, say there is no evidence yet and recommend `draft`. `merge` needs two
   reviewers. A PR that changes agent instructions always stays a draft, at any setting.
7. **Environment**: recommend running unattended and issue-driven work in an isolated VM,
   container or devcontainer, set up as the user likes, holding only the credentials runs need:
   the model's login, a fine-grained `gh` token scoped to this one repo, and tracker tokens the
   recorded writes need, each scoped as narrowly as the tracker allows; no SSH keys or other
   personal logins. Model steps run as the user, so this is what bounds injected issue text. Ask
   whether this environment is isolated. If not, warn once that injected issue text can reach
   whatever this machine can, including every repo its `gh` login reaches, and that a
   fine-grained single-repo token limits that; then go on. The answer also decides whether a
   non-Claude CLI on an exec or write stage needs a recorded confirmation
   (`automate-factory` asks it per stage).
8. **Risk paths**: phase 1's proposed globs, for the user to edit and confirm; they decide when
   `security-review` runs only on risky changes.
9. **Contradictions**: each conflict from phase 1, with both sources named.

## Output

Fill the profile's `Integrations` (reach method per tool, `Fetch` and `Write` lines) and
`Interview` sections with the answers, each marked "user, interview, <date>". Record each resolved gap under `Resolved
gaps and contradictions` and leave the `Repo` section untouched; on later runs, skip gaps already
resolved there. For an integration that is not reachable yet, print the setup steps (install the
MCP server, `<cli> login`, export the env var) and record it as unavailable.
