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
  typecheck, migrate and seed commands as written in the manifest, Makefile or task runner. With
  several manifests (monorepo), name the app or package behind the primary surface and record
  its commands so they run from the repo root (`npm --prefix`, `pnpm --filter`, `make -C`, or
  `(cd <dir> && <cmd>)`).
- **Services**: databases, queues, caches and other processes the app needs (compose files,
  env examples, connection-string env var names, ORM config).
- **CI**: workflow files, the jobs and named steps they run, triggers, required checks if visible
  (`gh api repos/{owner}/{repo}/branches/<default>/protection` when permitted).
- **Dependent repos**: other repos this one needs at runtime or build time (git submodules,
  workspace refs, API base URLs pointing at sibling services, docs naming them).
- **Agent config**: `AGENTS.md`, `CLAUDE.md`, `.cursor/rules`, project skills (`.agents/skills`,
  `.claude/skills`, `.cursor/skills`), MCP config (`.mcp.json`, `.cursor/mcp.json`,
  `.codex/config.toml`), existing verify skills.
- **Agent setup audit**: check whether that agent config asks for a plan step before code,
  splitting large work into phases, an independent review of the change, a cap on CI fix rounds
  (the factory stops at two), and a dependency rule (prefer existing code and the stdlib, justify
  each new package). Also list the user-level skills under the roots in
  [loading other skills](../SKILL.md#loading-other-skills), reading only each `SKILL.md`'s name and
  description (the one read outside the repo). Record each practice as present (with its file),
  unknown (only an installed skill's name or description suggests it; add it to `Open gaps`), or
  missing (neither project config nor any installed skill covers it).
- **Error and analytics SDKs**: detected from dependencies, init code, config files and env var
  names, e.g. Sentry, PostHog, Datadog, Bugsnag, Rollbar, New Relic, Amplitude, Segment,
  LogRocket. Record what was detected and where; do not check whether the agent can reach it yet.
- **Issue sources hinted by the repo**: issue templates, `.github/ISSUE_TEMPLATE`, Linear or Jira
  keys in branch names or commit messages (`git log --oneline -200`).

## Rules

- The audit installs and changes nothing; missing items become suggestions in the hand-off.
- Read env example files for variable names only. Never open `.env` or other files that may hold
  real values.
- MCP and harness config can hold inline tokens: list server and key names only, outside the
  model's context (`jq -r '.mcpServers | keys[]' .mcp.json`, `grep -o '^\[[^]]*\]'
  .codex/config.toml`), or use the connected tool inventory. Never print `env`, `headers`, `args`
  or URL values.
- Contradictions between sources (README says `npm`, lockfile is `pnpm-lock.yaml`) go to the
  interview's contradiction list, not silently resolved.

## Output

Fill the profile's `Repo` section, including `Open gaps`: each unknown and contradiction with its
sources, minus any already resolved in the `Interview` section. Phase 2 reads them from there.
