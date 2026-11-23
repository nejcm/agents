# Phase 1: Explore

Answer from the repo alone. Cite the file or command for every fact; leave unknowns for the
interview instead of asking now.

## What to find

- **Purpose**: what the repo is and who uses it (README, package metadata, top-level docs).
- **Surfaces**: what a user touches (web UI, API, CLI/TUI, mobile, desktop, library, worker).
  A repo can have several; name the primary one.
- **Stack**: languages, frameworks, key libraries, runtime versions (`.nvmrc`, `.tool-versions`,
  `engines`, `go.mod`, `pyproject.toml`, `Cargo.toml`, Dockerfiles).
- **Package manager and scripts**: from the lockfile, not a guess. List dev, build, test, lint,
  typecheck, migrate and seed commands as written in the manifest, Makefile or task runner.
- **Services**: databases, queues, caches and other processes the app needs (compose files,
  env examples, connection-string env var names, ORM config).
- **CI**: workflow files, the jobs and named steps they run, triggers, required checks if visible
  (`gh api repos/{owner}/{repo}/branches/<default>/protection` when permitted).
- **Dependent repos**: other repos this one needs at runtime or build time (git submodules,
  workspace refs, API base URLs pointing at sibling services, docs naming them).
- **Agent config**: `AGENTS.md`, `CLAUDE.md`, `.cursor/rules`, project skills (`.agents/skills`,
  `.claude/skills`, `.cursor/skills`), MCP config (`.mcp.json`, `.cursor/mcp.json`,
  `.codex/config.toml`), existing verify skills.
- **Error and analytics SDKs**: detected from dependencies, init code, config files and env var
  names, e.g. Sentry, PostHog, Datadog, Bugsnag, Rollbar, New Relic, Amplitude, Segment,
  LogRocket. Record what was detected and where; do not check whether the agent can reach it yet.
- **Issue sources hinted by the repo**: issue templates, `.github/ISSUE_TEMPLATE`, Linear or Jira
  keys in branch names or commit messages (`git log --oneline -200`).

## Rules

- Read env example files for variable names only. Never open `.env` or other files that may hold
  real values.
- Contradictions between sources (README says `npm`, lockfile is `pnpm-lock.yaml`) go to the
  interview's contradiction list, not silently resolved.

## Output

Fill the profile's `Repo` section, including `Open gaps`: each unknown and contradiction with its
sources, minus any already resolved in the `Interview` section. Phase 2 reads them from there.
