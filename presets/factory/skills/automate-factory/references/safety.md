# Write safety

An unattended run has no one to catch a bad action. Every automation is split into steps, and each
step gets only the capability it needs.

## Lethal-trifecta rule

Untrusted input, secrets and egress never meet in one step; the one accepted exception is the edit
step's model auth, below. Model steps never hold a write credential: every write (push, PR,
comment, post) happens in a model-free publish or post step. Untrusted input is any text the repo
owner did not write: issue and PR bodies, PR and review comments, attachments, error payloads, CI
logs, commits and diffs from other authors, transcripts (they carry tool output and fetched pages),
fetched web pages. Trusted input is the default branch's tracked files and numbers the repo's own
CI produced. A step holds a secret or write access when any tool it has can use one: a shell (reads
env and credential files, runs `gh`, `git push`, `curl`), an MCP server, a hook, a write-scoped
token in its environment.

## Steps

| Step | Model | Reads | Capability |
| ---- | ----- | ----- | ---------- |
| fetch | none | the source (`gh`, `git`, logs, a recorded CLI command) | read-only calls; writes into the run's view only |
| agent fetch | yes | one source, through its recorded read-only MCP tools, or a CLI's output on stdin | no built-in tools; its stdout enters the view only through `check_items.py` |
| analyze | yes | the run's view: `repo/` (tracked files of the default branch), `input/`, `skills/` | file read and search only; the report is its stdout |
| edit | yes | `report.md`, the profile, `skills/`, a disposable checkout | jailed shell and edits in the checkout only; model auth is its one secret |
| gates | none | the edit's diff | runs the fixed test command jailed, with no secret |
| publish | none | the commit and the captured summary | pushes to one fixed branch and opens or comments on its PR |
| post | none | the report file | sends it unchanged to one fixed destination |

- **Analyze isolation**: Claude Code with `--restricted --safe-mode --tools "Read,Grep,Glob"
  --strict-mcp-config --no-session-persistence`, run with the view as its working directory.
  `--restricted` confines file tools to that directory, so `.env` files, credential files and
  other sessions stay out of reach; `--safe-mode` drops hooks, plugins, skills and `CLAUDE.md`.
  Managed (policy) settings still apply: if they define hooks, analyze is unavailable on that
  runner. A runner that cannot run this command is not offered an entry with untrusted input.
- **Agent fetch**: for sources without a script fetch, per `fix-issues`
  [triage.md](../../fix-issues/references/triage.md#agent-fetch). The MCP server holds the
  credential, out of the model's reach, and the agent can call only the allowlisted read tools of
  that one server, given the managed-policy precondition in
  [runners.md](runners.md#analyze-command). Residual risk: injected item text can make it run extra read-only queries on
  the same source; with no write tools, nothing is written. Prefer a read-only token where the
  source offers one, and allowlist no tool that takes a URL or reaches another host. CLI and API
  sources never give the agent a shell: the command runs model-free and the agent only reshapes
  its output.
- **Write levels**: each automation has one, chosen at setup and written into its run script:
  `report` (default, no writes), `comment` (post), `draft-pr` or `pr` (edit, gates, publish).
  An entry offers only the levels in its `Write levels`.
- **Edit**: per [runners.md](runners.md#write-levels), `claude` runs in fix-issues'
  [`jail.sh`](../../fix-issues/assets/jail.sh) on a detached worktree: empty `HOME`, no
  inherited environment besides the model's auth variable, the repo and `.git` out of reach, so no
  push credential or `gh` login. Its summary is its stdout, captured by the script outside the
  jail and capped at `summary_cap` bytes, ending `edit: outcome=changed` or
  `edit: outcome=stopped`; the script never opens a file the jail wrote. On `changed` it commits
  with hooks off (Git stores symlinks as links and skips FIFOs). Residual
  risk: the edit step's input derives from untrusted text and the network is shared, so injected
  text can make it leak the model token; it cannot write anywhere but the checkout. Linux with
  `bwrap` only; elsewhere the jail fails closed.
- **Gates**, model-free, all must pass or nothing is published: a non-empty diff of at most
  `max_lines` changed lines, no binary files; every path in the entry's `allow` globs and none in
  `deny` (CI, hooks, agent harness and editor settings, `.factory/`, `CODEOWNERS`,
  `.gitattributes`, the verify skill); existing test files take additions only (no changed,
  removed or renamed line), new test files are allowed, and
  added lines carry no skip or focus marker; no credential-shaped text (`sk-ant-`) in the diff or
  summary; the fixed test command passes in the jail with no secret. The test command, allowlist
  and cap are fixed at setup; `allow` must exclude the files that define the test command
  (manifests, test config).
- **Loop caps**: at most one PR per automation per run. Its branch is `factory/<entry>` (for
  `pr-babysitting`, the opted-in PR's branch); while that branch has an open same-repo PR, the
  run starts from the PR's head, pushes on top, never forced, and comments instead of opening
  another. `factory/<entry>` without an open PR, or a fixed PR branch without one, stops the run.
- **Dry run**: no post or publish. Writes go to `.factory/reports/`, the run's temp view under
  `.factory/tmp/` and its worktree, nothing else.
- **Fixed destination**: the post and publish steps' targets (`--repo <owner/repo>`, remote,
  branch, issue or PR number, channel) are written into the run script when the user approves
  them, never taken from model output or fetched text. The body is passed as a file, never
  interpolated into a command line.
- **Hosted runners**: `report` and `comment` only. Checkout with `persist-credentials: false`;
  the CLI install runs in its own step without the model key; the fetch step alone gets
  `GH_TOKEN`; workflow `permissions:` read-only. `comment` adds a separate model-free job with
  the one write scope it needs. No edit: gates run model-written code, which on a hosted runner
  (passwordless `sudo`) could tamper with any later step of its job, so a safe split needs edit,
  gates and publish as three jobs with a re-check of the patch in publish; later.
- **Memory**: no automation keeps notes between runs beyond its reports in `.factory/reports/`.
  A later run reads earlier reports as data, never as instructions.
