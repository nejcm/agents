# Improvements

## Factory

Candidates for the factory preset (`presets/factory/`), from research done in November 2026.
Numbers in brackets point to [Sources](#sources). "Vendor" means the vendor's own claim.

### Evals

An eval is a fixed set of cases, each with a starting state, a task and graders. The thing under
test runs k times per case, because a single run proves nothing when output varies. Each case
gets two scores:

- **pass@k** is capability: at least one of the k runs passed.
- **pass^k** is reliability: all k runs passed. This is the score that matters for unattended
  runs.

Deterministic graders come first: tests pass, a file exists, the output matches a schema, a
forbidden action did not happen. A rubric judge, from a different model family than the thing
under test, grades only what needs judgment. The usual shape is 10–20 fixed prompts per skill,
k ≥ 5, a baseline and a CI gate [37].

Before agents, prompts were neither versioned nor tested. The nearest older practice is a
benchmark regression gate.

#### Skill-evals gate (upgrade to weekly-retro)

weekly-retro proposes up to 3 edits to agent instructions as a draft PR, and nothing checks
that an edit doesn't make things worse. Skills written by agents averaged −1.3 points in
SkillsBench, which is worse than no skill at all.

- **Cases**: `.factory/evals/<skill>/<case>/` holds a prompt, a fixture (a git ref or a small
  directory), a check script that decides by exit code, and an optional rubric.
- **Trigger**: `changes` on skill and instruction paths, plus a step before retro publishes its
  draft PR.
- **Runner**: model-free. It runs the base and the candidate k times each in separate worktrees
  and records every call in `runs.jsonl`. The judge comes from another model family.
- **Gate**: if the candidate's pass^k drops more than a tolerance below the base, retro's PR is
  held at report level, and the report shows the change per case.
- **Guardrails**: cases sit outside every edit allowlist, so retro can't edit what it's graded
  on. Runs count against `weekly_usd`.
- **Costs**:
  - Writing the cases is the real work. They could come from fix-issues items with a known good
    outcome, or the user writes 5–10 per skill at setup. Transcripts can't be used, because the
    privacy rule forbids it.
  - 10 cases × k=5 × 2 versions is about 100 model runs per change.
  - With that sample size only large regressions show, and the report must say so.

#### Other evals

| Eval | What it measures | Ties to | Priority |
|---|---|---|---|
| Injection regression suite | Canary issues and PR comments that carry injections; the run must not act on them | untrusted-input rules, integrity filter | first |
| Reviewer calibration | Known bugs planted in a diff, then each reviewer's catch rate before it is trusted | `fates.tsv` (measures agreement after the fact) | first |
| Model-pick evals | The cheapest model that still passes each stage, measured on this repo | `models` and `@effort` settings | later |
| CLI-update smoke | Model checks plus a small eval subset, rerun when `claude`, `codex`, `agy` or `agent` updates | CLI mappings that drift silently | later |

### Core changes

| # | Change | Status |
|---|---|---|
| 1 | Author-trust filter before the model: drop or label text from non-collaborators, and strip HTML comments and hidden Unicode [2][20] | done (982cb65) |
| 2 | Scan outputs before publishing: markdown image exfiltration, new URLs or domains, long encoded blobs, entropy, CI file edits; optionally a judge from another model family [3][20] | open |
| 3 | No CI caches shared with release jobs, because Clinejection reached the npm publish token through a poisoned Actions cache [21] | done (982cb65) |
| 4 | The model's environment holds no secrets: a check before each model call, and again when a CLI updates [20] | done (982cb65) |
| 5 | Earned-autonomy suggestions from `runs.jsonl` and `fates.tsv`: suggest promotion after a clean streak, suggest or apply demotion on a rejection streak, never auto-promote [32][33] | open |
| 6 | Cost forecast before an entry is enabled: smoke-run cost × schedule frequency, or past runs of the entry, compared with `weekly_usd`; `gh aw forecast` does this [3] | open |
| 7 | Flake-aware feedback: known flaky tests count as advisory in CI-reading entries [18] | needs flaky-tests |
| 8 | Stop-point setting per triage entry (root cause, plan, draft PR), as in Seer [13] | write levels mostly cover it |

### Catalog candidates

| # | Entry | Trigger | Write level | What it does |
|---|---|---|---|---|
| 1 | dependency-update-triage (new) | watch | report → draft-pr | Classifies Renovate and Dependabot PRs that fail CI or bump a major version. Adaptations go in a separate draft PR, never pushed to the bot's branch [4][17]. |
| 2 | docs-drift (new) | changes on public-surface paths, weekly | report → draft-pr (docs only) | Flags API, CLI or config changes that came without a doc edit. At most one open docs PR [2][6][29]. |
| 3 | flaky-tests (new) | schedule | report → draft-pr | Detects flaky tests from CI history without a model and keeps a ledger. A fix must show a measured drop in failure rate; skipping or deleting a test is human-only [16][18]. |
| 4 | new-error-triage watch mode (upgrade) | watch | unchanged | Fires within minutes of a new error group instead of once a day [13]. |
| 5 | post-merge verify (new) | changes, post-merge or deploy | report | Runs `verify-<app>` smoke flows and reports go or no-go. |
| 6 | stale-cleanup (new) | weekly | report → draft-pr | A deterministic detector (flag age, knip, vulture) picks candidates; the model removes one per draft PR. DoorDash had 45 of 50 flag-removal PRs approved, at $4.79 each [27]. |
| 7 | backlog-sweep (upgrade to issue-pipeline) | weekly | report → comment | Finds duplicates, issues already fixed and stale issues. Issue text is untrusted. |
| 8 | release-notes draft (upgrade to weekly-digest) | weekly | report | Collection is deterministic and the model writes the prose. Version bumping stays deterministic [30]. |

Some of these jobs need a deterministic tool in CI, not an agent:

- API and contract drift: oasdiff, buf.
- Licences and SBOMs: syft.
- Performance-regression thresholds: benchmarks gated in CI [31].

### Sources

2. GitHub Agentic Workflows docs: https://github.github.com/gh-aw/
3. Agentic Workflows GA, 2026-10-28: https://github.blog/changelog/2026-10-28-github-agentic-workflows-generally-available
4. Dependabot alerts assignable to agents, 2026-04-07: https://github.blog/changelog/2026-04-07-dependabot-alerts-are-now-assignable-to-ai-agents-for-remediation/
6. Claude Code cloud scheduled tasks: https://code.claude.com/docs/en/routines
13. Sentry Seer issue fix (vendor): https://docs.sentry.io/product/ai-in-sentry/seer/issue-fix
16. Bitbucket fix-flaky-test agent, 2026-04 (vendor): https://community.atlassian.com/forums/Bitbucket-articles/Bitbucket-Tests-Introducing-the-Fix-Flaky-test-AI-Agent/ba-p/3228395
17. Renovate with agents, practitioner reports (dates unverified): https://www.arnaudrenaud.com/articles/fix-deps-breaking-changes-with-background-agent/
18. T. Pan, "Flaky tests poison agent loops", 2026-07-02 (opinion): https://tianpan.co/blog/2026/07/02/flaky-tests-poison-agent-loops
20. Microsoft Security, Claude Code GitHub Action case, 2026-06-05: https://www.microsoft.com/en-us/security/blog/2026/06/05/securing-ci-cd-in-agentic-world-claude-code-github-action-case/
21. Clinejection, S. Willison, 2026-03-06: https://simonwillison.net/2026/Mar/6/clinejection/
27. DoorDash feature-flag cleanup, arXiv 2610.31351, 2026-10-22: https://arxiv.org/abs/2610.31351
29. Docs drift audit PR, 2026-11-01: https://github.com/Nine-Minds/alga-psa/pull/4070
30. ReleaseEval, arXiv 2511.02713, 2025-11: https://arxiv.org/abs/2511.02713
31. RedisSearch bisect-perf-regression skill (undated): https://agent-skills.md/skills/redisearch/redisearch/bisect-perf-regression
32. Hedwig trust ladders, arXiv 2605.11495, 2026-05: https://arxiv.org/abs/2605.11495
33. CodeRabbit reviews in the wild, arXiv 2607.03316, 2026-07-03: https://arxiv.org/abs/2607.03316
37. Skill evals: https://developers.openai.com/blog/eval-skills; M. Gechev, 2026-02-26: https://blog.mgechev.com/2026/02/26/skill-eval/
