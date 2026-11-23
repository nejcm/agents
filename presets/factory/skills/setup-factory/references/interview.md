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
2. **Error and analytics tools**: for each detected or named tool, how an agent reaches it
   (MCP server, logged-in CLI, API env var, none).
3. **Results and escalations**: where reports, questions and failures go (PR comment, issue,
   Slack channel, email, a file in `.factory/reports/`).
4. **Deploy targets**: environments and how they deploy (CI on merge, manual, platform name),
   and which ones an agent may touch (default: none).
5. **Budgets**: model auth (subscription, the default, or API key); per run in minutes and turns
   (default 30 and 50), plus money on API key; per week; which models are allowed.
6. **Review**: who reviews agent PRs, and whether agents may open PRs at all.
7. **Contradictions**: each conflict from phase 1, with both sources named.

## Output

Fill the profile's `Integrations` (reach method per tool, `Fetch` lines) and `Interview` sections
with the answers, each marked "user, interview, <date>". Record each resolved gap under `Resolved
gaps and contradictions` and leave the `Repo` section untouched; on later runs, skip gaps already
resolved there. For an integration that is not reachable yet, print the setup steps (install the
MCP server, `<cli> login`, export the env var) and record it as unavailable.
