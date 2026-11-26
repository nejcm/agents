# Write safety

An unattended run has no one to catch a bad action. Every automation is split into steps, and each
step gets only the capability it needs.

## Lethal-trifecta rule

Untrusted input, secrets and egress never meet in one step, with one accepted exception: the edit
step, and gates' test command running its code, have a shell and so reach whatever the runner's
environment holds. The isolation boundary is that environment: a VM, container or devcontainer
holding only the model's login and the token publish needs, scoped to the one repo (setup-factory
records it as `Environment`). Within a run, model steps get no write command or destination: every
write (push, PR, comment, post) happens in a model-free publish or post step, its target fixed at
setup, except an agent write, which holds one MCP write tool and is checked afterwards. The edit
step runs as the user: it can change Git config, `PATH` and the run script, and read the `gh` login. So the step split stops a model that is simply wrong, not an
injected one; an injected model is bounded only by the isolated environment, holding a
fine-grained token scoped to the one repo. Untrusted input is any text the repo owner did not
write: issue and PR bodies, PR and review comments, attachments, error payloads, CI logs,
commits and diffs from other authors, transcripts (they carry tool output and fetched pages),
fetched web pages. Trusted input is the default branch's tracked files and numbers the repo's own
CI produced. A step holds a secret or write access when any tool it has can use one: a shell
(reads env and credential files, runs `gh`, `git push`, `curl`), an MCP server, a hook, a token
in its environment.

## What the user can change

Through setup-factory's "change my factory", which runs automate-factory's [re-run](../SKILL.md#re-run):
- Settings in the profile: schedule, write level, destinations, per-source trust, `label`,
  `run_minutes`, `cap`, budgets (`weekly_usd`), per-entry model picks with their recorded
  [confirmations](runners.md#cli-mapping), extra skills and
  [stage skills](runners.md#stage-skills), `ceiling`,
  the [change trigger](runners.md#change-triggers) with `Risk paths` and `Feature paths`,
  the [watch trigger](runners.md#watch-trigger) with `interval`, `daily_cap`, `window`, `notify`
  and `drafts`, `issue-pipeline` `reviewers`, `merge_level` and `needs_human`.
- Guidance in [prompt overlays](runners.md#prompt-overlays) (`<entry>.<name>.local.md`).
- `issue-pipeline` [flow variants](catalog/issue-pipeline.md): `flow` `repro-only`, `verify_fixed` `off`.

Locked in the run scripts, at every write: model-free writes to destinations fixed at setup; dry
run writes nothing external; item text reaches stages only through the checked spec; gates on the
exact pushed commit; credential check and size cap on every final body (`sendable`); the consumed
in-repo skills, stage skills included, in `deny`; the record contract of every stage; pause, claims; a merge only at `issue-pipeline` `merge_level` `merge`,
by the model-free rule under Merge levels, never of a revert; every other PR stays unmerged, and
`issue-pipeline` PRs open as drafts; a PR that changes [agent instructions](#steps) stays a draft
and is never marked ready or merged, whatever `needs_human` says. A
user-owned executable flow is not offered: sourced Bash can redefine `gates` or `publish`, or call
`gh` directly, so no lock would hold.

## Steps

| Step | Model | Reads | Capability |
| ---- | ----- | ----- | ---------- |
| fetch | none | the source (`gh`, `git`, logs, a recorded CLI command) | read-only calls; writes into the run's view only |
| agent fetch | yes | one source, through its recorded read-only MCP tools, or a CLI's output on stdin | no built-in tools; its stdout enters the view only through `check_items.py` |
| analyze | yes | the run's view: `repo/` (tracked files of the default branch), `input/`, `skills/` | file read and search only; the report is its stdout |
| edit | yes | `report.md`, the profile, `skills/`, a disposable checkout | shell and edits in the checkout; no write command or destination |
| gates | none | the edit's diff | runs the fixed test command in the checkout |
| publish | none | the commit and the captured summary | pushes to one fixed branch and opens or comments on its PR |
| post | none | the report file | sends it unchanged to one fixed destination |
| agent write | yes | the report file on stdin | one recorded MCP write tool; the call is checked against the fixed arguments |
| spec-writer | yes | one selected item's JSON, its triage section and its journey, on stdin | no tools; its stdout enters only through `check_items.py --spec` |
| reproduce, fix, verify | yes | the checked spec, stage records, base or patch exports | `fix-issues` stages: shell, edits for fix only; no write command or destination |

- **Analyze isolation**: Claude Code with `--restricted --safe-mode --tools "Read,Grep,Glob"
  --strict-mcp-config --no-session-persistence`, run with the view as its working directory.
  `--restricted` confines file tools to that directory, so `.env` files, credential files and
  other sessions stay out of reach; `--safe-mode` drops hooks, plugins, skills and `CLAUDE.md`.
  Managed (policy) settings still apply: if they define hooks, analyze is unavailable on that
  runner. A runner that cannot run this command is not offered an entry with untrusted input.
- **Other CLIs**: the user may pick any supported CLI for any stage ([CLI
  mapping](runners.md#cli-mapping)); the runner never overrides that choice and never falls back
  to another model (a missing or logged-out CLI stops the call `model-unavailable`). A CLI that
  fails the analyze isolation above (`codex`: its read-only sandbox reads the whole filesystem;
  `agy`: read-only still reads outside its directory and keeps web search; `agent`: ask mode still
  reads outside its directory and keeps subagents)
  runs analyze or the spec-writer only after the user's recorded confirmation; it then gets every
  control the CLI has, the safety rules in its prompt (best effort against injection, not a
  boundary), and the stage is recorded `isolation: weak`. A non-Claude CLI on an exec or write
  stage outside an isolated `Environment` also needs a recorded confirmation: the machine it runs
  on is then the only boundary. Without the confirmation the run fails before any call. Agent fetch
  and agent write stay on Claude.
- **Agent fetch**: for sources without a script fetch, per `fix-issues`
  [triage.md](../../fix-issues/references/triage.md#agent-fetch). The MCP server holds the
  credential, out of the model's reach, and the agent can call only the allowlisted read tools of
  that one server, given the managed-policy precondition in
  [runners.md](runners.md#analyze-command). Residual risk: injected item text can make it run extra read-only queries on
  the same source; with no write tools, nothing is written. Prefer a read-only token where the
  source offers one, and allowlist no tool that takes a URL or reaches another host. CLI and API
  sources never give the agent a shell: the command runs model-free and the agent only reshapes
  its output.
- **Agent write**: a post to a tracker reached only through MCP, per `fix-issues`
  [write back](../../fix-issues/references/triage.md#write-back). `--allowedTools` cannot pin
  arguments, so injected report text can redirect the one call to another destination on the
  same server; `check_items.py --write` fails the run afterwards on any call other than the fixed
  one. Prefer the tracker's CLI or API, which posts model-free. On any post failure the post may
  already be live, so a rerun posts again: check the destination before rerunning.
- **Issue pipeline**: `issue-pipeline` at `draft-pr` runs the steps above per item, per its
  [catalog entry](catalog/issue-pipeline.md). Item text reaches stages only through the checked
  spec, written only for items from a source the user marked trusted or carrying the maintainer's
  label. Residuals, accepted: a stranger can edit a labelled public issue after the label, so the
  spec tops the draft for the reviewer; on a public repo the body carries clipped stage records,
  checked only for `sk-ant-`, OpenAI `sk-` and Google `AIza` key text.
- **Write levels**: each automation has one, chosen at setup and written into its run script:
  `report` (default, no writes), `comment` (post), `draft-pr` or `pr` (edit, gates, publish).
  An entry offers only the levels in its `Write levels`.
- **Edit**: per [runners.md](runners.md#write-levels), `claude` runs on a detached worktree under
  the runner's own login, with `--safe-mode --setting-sources ''` so the checkout's tracked
  settings cannot change auth, hooks or permissions. Its summary is its stdout, capped at
  `summary_cap` bytes, with one `test-change: <path>: <reason>` line per existing
  test file it changed, deleted or renamed (old path), one `dependency: <name> <why>` line per new
  package, one `scope: minimal` or `scope: refactor <why a smaller fix is worse>` line, ending
  `edit: outcome=changed`, `edit: outcome=stopped` or `escalated: <reason>`
  (`credentials`, `prod-access`, `ambiguous`, `out-of-scope`: the run ends `escalated`, the
  report says "needs a human", nothing is pushed); the script
  never opens a file the step wrote. On `changed` it commits with hooks off (Git stores symlinks
  as links and skips FIFOs); the step's own commits are squashed into that commit unless the scope
  is `refactor`, where they stay as refactor commits before it. Residual risk: its input derives from untrusted text, so injected
  text can use whatever the environment holds; keep write credentials there to the one repo and
  the writes publish needs.
- **Gates**, model-free, all must pass or nothing is published: a non-empty diff under the
  runaway `ceiling` (default 10000 weighted lines: a deletion weighs 1/4; lockfiles and known
  generated files such as `*.min.js` excluded), no binary files; every path in the entry's `allow` globs and none in
  `deny` (CI, hooks, agent harness and editor settings, `.factory/`, `CODEOWNERS`,
  `.gitattributes`, the verify skill, the in-repo skills the run reads, link and target), and
  none with a control character, quote or backslash, which Git prints quoted; every
  changed, deleted or renamed existing test file (a rename counts as its old path), and only
  those, has exactly one `test-change` line whose path matches it exactly and whose reason is not
  blank; added test lines carry no skip or focus marker; every new package has a `dependency`
  line; exactly one valid `scope` line; the commits descend linearly from the start and touch no
  path the final diff leaves unchanged; the fixed test command passes in the checkout; no
  credential-shaped text (`sk-ant-`, OpenAI `sk-`, Google `AIza` keys) in the diff, commit messages, summary or disclosure sections.
  Inside `allow`, a changed path must stay a regular or executable file at the start and the
  commit: a symlink could point a test, CI or reviewer at a path outside `allow`, and a
  submodule at code no gate saw.
  The path, mode, binary, ceiling and credential rules also hold for each intermediate commit's
  diff from the start, as do the dependency-only manifest rule and the refactor test runs, since
  the push publishes them.
  The test command, allowlist and ceiling are fixed at setup; `allow` must exclude the files that define the test command
  (manifests, test config); with `dep_files=1` a manifest outside `allow` may change only its
  dependency keys.
- **Changed tests**: when the edit changed, deleted or renamed existing test files, gates run the
  start versions of those files against the new code (same test command and timeout, in a second
  worktree) and record whether they fail (change needed), still pass (edit not needed, review
  closely) or time out (no evidence); none blocks. The section (reasons, that outcome with a
  capped output tail, each deleted path, the capped diff of the others, "needs human approval") goes to `.factory/reports/<entry>/<date>-test-change.md` and
  tops the PR body or comment. The PR is a draft at any write level, and at any `merge_level` while
  its disclosure is in `needs_human`: a new one opens as a draft, a reused
  one is returned to draft before the push or the run stops. It gets the `factory:test-change`
  label, created if missing (a label failure only warns). A body over GitHub's 65536 characters
  stops the run before the push. At the default `needs_human`, a PR with this disclosure never
  merges.
- **Scope**: the edit chooses it; size is not judged. `refactor` needs at least one refactor
  commit before the behaviour commit; each refactor commit leaves existing test files unchanged
(content, mode and type) and
  passes the test command (same timeout, in its own worktree), or the gate blocks. In
  `issue-pipeline` those runs, the old-tests run for changed tests and the run of added tests on
  the base each start only with time left in `run_minutes` for them, verify and the
  reviewers; else the item is `deferred` `run-time`. A refactor PR is
  a draft as for changed tests, gets the `factory:refactor` label, and its reason tops the body;
  the run record keeps `scope` and `weighted_lines`.
- **Agent instructions**: a path any pushed commit changes is one when it matches `instructions`
  in the run script (`AGENTS.md`, `CLAUDE.md` and `SKILL.md` at any depth, `.claude/`, `.agents/`,
  `.cursor/rules/`, `.cursor/skills/`, `.factory/`) or sits under a directory holding a `SKILL.md`
  at the start. Such a PR is a draft at any write level and `merge_level`, as for changed tests,
  gets the `factory:instructions` label, the paths top the body, and the run record sets
  `instruction_change`. This is not a `needs_human` disclosure: no setting lifts it.
- **Shadow review**: `issue-pipeline` only, after verify: each model in the entry's `reviewers`
  runs as analyze does (read-only tools, its own pick; Claude `--restricted`, another CLI at `weak` isolation) on an export of the
  gated commit with the checked spec, the diff and the gate and verify records, never item text.
  Its last line must be `review: verdict=approve` or `review: verdict=changes`; anything else
  counts as `changes`. Verdicts and capped findings go in the PR body and the item's run record;
  they decide nothing at the default `merge_level` `draft`.
- **Merge levels**: `issue-pipeline` only, the one entry with reviewer verdicts; other entries
  never merge, and `pr` opens ready-for-review PRs as before. `merge_level` `ready`: after the
  push, a PR whose every reviewer approved, that has no disclosure in `needs_human` and changes no
  agent instructions is marked ready for review. `merge` (at least two reviewers): such a PR is also recorded in
  `fix-issues/merges.tsv` with its entry, verdicts and disclosures, and a later run of that entry
  squash-merges it with `gh pr merge --squash
  --match-head-commit <gated commit>` only when, checked model-free in that run, the PR is open,
  not draft, on `factory/fix-<id>` into `<base>` from this repo, its head is still the gated
  commit, the recorded verdicts and disclosures still pass the current `reviewers` and
  `needs_human`, the PR's files (`gh pr diff --name-only`) hold no agent instructions at `<base>`, `mergeable` is `MERGEABLE`, the commit's CI rollup is `SUCCESS` (a commit with no CI
  never merges), `merge_level` is still `merge`, and `.factory/pause` is absent. Pending CI or
  mergeability waits for the next run; any other failure drops the PR from factory merging with a
  "needs a human" line in the report.
- **Revert**: each later run checks the CI rollup of every factory merge commit on `<base>`.
  `SUCCESS` closes it; `FAILURE` or `ERROR` opens a revert PR (`git revert` on the fetched
  `<base>`, the same gates and publish, always draft, on `factory/revert-<id>`), records the item
  `escalated` `main-red` and says "needs a human" in the report. A revert starts only with time
  left in `run_minutes` for two test runs; else it waits for a later run. When the branch was
  pushed but its PR did not open, the item stays `merged` and the next run opens the draft PR for
  that same commit from the saved body (`items/<id>/revert-body.md`, `revert-commit`), with a
  "needs a human" line each run; a revert that failed before the push is still recorded
  `reverted` with `revert PR none`. The factory never merges a
  revert PR: only `factory/fix-<id>` heads recorded as approved can merge. An unknown merge
  commit (failed lookup, merge queue) is looked up again on every later run until CI on it is
  green or red; the fifth failed lookup adds a "needs a human" line. A PR found closed unmerged
  leaves monitoring with one report line (`closed` in `merges.tsv`).
- **PR fates**: each non-dry `issue-pipeline` run looks up, with `gh pr view` and `git log` on
  the fetched `<base>`, every PR in `linked.tsv`: open, merged by the factory (a `merged` row in
  `merges.tsv`), merged by a human (any other merge),
  closed unmerged, or reverted (a later commit carrying `This reverts commit <merge commit>`,
  `Revert "<title>` or `Reverts <repo>#<n>`), plus a count of change-request reviews by authors not ending in `[bot]`. Rows go to
  `fix-issues/fates.tsv`; `agent-analytics` reports agreement from them. `pushed.tsv`,
  `linked.tsv`, `tickets.tsv`, `merges.tsv` and `fates.tsv` under `fix-issues/` must be regular
  files or absent, checked before any stage or write and again before each item
  ([state](catalog/issue-pipeline.md#state-draft-pr)).
- **Dependencies**: disclosed, never blocked. Gates compare dependency keys of every changed
  `package.json`, `pyproject.toml`, `Cargo.toml` and `go.mod` between the start and the commit
  (all package managers using that manifest). A new package without a `dependency: <name>` line
  fails the gate; with one, a section (the lines, the new packages) tops the body, the PR is a
  draft as for changed tests and gets the `factory:dependency` label. Only entries set up with
  `dep_files=1` (those that fix source code) may change manifests and generated lockfiles outside
  `allow`: such a manifest passes only if it parses and nothing but its dependency keys changed
  (tables left empty by removing them are ignored). Generated lockfiles skip the ceiling, and
  `bun.lockb` the binary check; an exempt file must stay a regular, non-executable file. A changed
  lockfile or `requirements.txt`, or an allowed manifest it cannot parse, is listed as
  "dependency files changed" with the same draft and label; a lockfile change without a manifest
  dependency change gets its own line.
- **Loop caps**: at most one PR per automation per run. Its branch is `factory/<entry>` (for
  `pr-babysitting`, the opted-in PR's branch); while that branch has an open same-repo PR, the
  run starts from the PR's head, pushes on top, never forced, and comments instead of opening
  another. `factory/<entry>` without an open PR, or a fixed PR branch without one, stops the run.
  CI cap: each push appends `<PR number> <commit>` to `.factory/reports/<entry>/pushed.tsv` (a
  symlink or non-regular file stops the run before any push); when the last two factory pushes'
  CI rollups (`gh api graphql` `statusCheckRollup`, check runs and statuses) are both `FAILURE` or
  `ERROR`, the run ends `escalated` `ci-cap` before the edit, "needs a human" in the report. A
  failed lookup ends it `ci-unknown`, "CI status unknown". Running or absent CI is not a failure.
  The cap lifts when a recorded push turns green on a rerun, or the PR head is a commit not in
  the ledger whose own CI is `SUCCESS`.
  Exception: `issue-pipeline` opens one draft PR per item on `factory/fix-<id>`, at most `cap` items
  per run (default 3), and skips an item whose branch or PR exists, so it never pushes twice.
- **Pause**: `.factory/pause` makes every run exit 0 before any work; `issue-pipeline` also checks
  it before each item and defers the rest.
- **Dry run**: no post or publish. Writes go to `.factory/reports/`, the run's temp view under
  `.factory/tmp/` and its worktree, nothing else; `issue-pipeline` also uses its claim under
  `.factory/reports/fix-issues/tmp/` and stages only the first selected item, with no ticket, link
  or state rows, and no merge, revert or fate lookup.
- **Fixed destination**: the post and publish steps' targets (`--repo <owner/repo>`, remote URL,
  branch, issue or PR number, channel, team) are written into the run script, or the
  `<prefix>.<op>.sh` it calls, when the user approves them, never taken from model output or
  fetched text. The body is passed as a file or on stdin, never interpolated into a command line.
  Tracker tokens a write needs sit in the isolated environment too, scoped to the destination
  where the tracker allows it (a Slack bot in one channel).
- **Memory**: no automation keeps notes between runs beyond its reports in `.factory/reports/`,
  including the redacted [run record](runners.md#run-record) `runs.jsonl`, the watch seen ledger
  `seen.tsv`, `pr-babysitting`'s `commented.tsv` and `security-review`'s `reviewed.sha`, written
  model-free by the script.
- **Change triggers**: the `no-risk-change` check is model-free, on the commit graph and the
  globs fixed at setup ([runners.md](runners.md#change-triggers)); `reviewed.sha` advances only
  after a successful run or that skip, never on a failure, budget or pause skip, or dry run.
  A later run reads earlier reports as data, never as instructions.
