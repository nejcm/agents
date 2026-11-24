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
  checked only for `sk-ant-` text.
- **Write levels**: each automation has one, chosen at setup and written into its run script:
  `report` (default, no writes), `comment` (post), `draft-pr` or `pr` (edit, gates, publish).
  An entry offers only the levels in its `Write levels`.
- **Edit**: per [runners.md](runners.md#write-levels), `claude` runs on a detached worktree under
  the runner's own login, with `--safe-mode --setting-sources ''` so the checkout's tracked
  settings cannot change auth, hooks or permissions. Its summary is its stdout, capped at
  `summary_cap` bytes, with one `test-change: <path>: <reason>` line per existing
  test file it changed, ending `edit: outcome=changed` or `edit: outcome=stopped`; the script
  never opens a file the step wrote. On `changed` it commits with hooks off (Git stores symlinks
  as links and skips FIFOs). Residual risk: its input derives from untrusted text, so injected
  text can use whatever the environment holds; keep write credentials there to the one repo and
  the writes publish needs.
- **Gates**, model-free, all must pass or nothing is published: a non-empty diff of at most
  `max_lines` changed lines, no binary files; every path in the entry's `allow` globs and none in
  `deny` (CI, hooks, agent harness and editor settings, `.factory/`, `CODEOWNERS`,
  `.gitattributes`, the verify skill, the in-repo skills the run reads, link and target); no test
  file deleted or renamed; every changed existing test file, and only those, has exactly one
  `test-change` line whose path matches it exactly and whose reason is not blank; added test
  lines carry no skip or focus
  marker; the fixed test command passes in the checkout; no credential-shaped text (`sk-ant-`)
  in the diff, summary or test-change section. The test command, allowlist
  and cap are fixed at setup; `allow` must exclude the files that define the test command
  (manifests, test config).
- **Changed tests**: when the edit changed existing test files, gates run the start versions of
  those files against the new code (same test command and timeout, in a second worktree) and
  record whether they fail (change needed), still pass (edit not needed, review closely) or time
  out (no evidence); none blocks. The section (reasons, that outcome with a capped output tail, the capped test
  diff, "needs human approval") goes to `.factory/reports/<entry>/<date>-test-change.md` and
  tops the PR body or comment. The PR is a draft at any level: a new one opens as a draft, a reused
  one is returned to draft before the push or the run stops. It gets the `factory:test-change`
  label, created if missing (a label failure only warns). A body over GitHub's 65536 characters
  stops the run before the push. The factory never merges.
- **Loop caps**: at most one PR per automation per run. Its branch is `factory/<entry>` (for
  `pr-babysitting`, the opted-in PR's branch); while that branch has an open same-repo PR, the
  run starts from the PR's head, pushes on top, never forced, and comments instead of opening
  another. `factory/<entry>` without an open PR, or a fixed PR branch without one, stops the run.
  Exception: `issue-pipeline` opens one draft PR per item on `factory/fix-<id>`, at most `cap` items
  per run (default 3), and skips an item whose branch or PR exists.
- **Pause**: `.factory/pause` makes every run exit 0 before any work; `issue-pipeline` also checks
  it before each item and defers the rest.
- **Dry run**: no post or publish. Writes go to `.factory/reports/`, the run's temp view under
  `.factory/tmp/` and its worktree, nothing else; `issue-pipeline` also uses its claim under
  `.factory/reports/fix-issues/tmp/` and stages only the first selected item, with no ticket, link
  or state rows.
- **Fixed destination**: the post and publish steps' targets (`--repo <owner/repo>`, remote URL,
  branch, issue or PR number, channel, team) are written into the run script, or the
  `<prefix>.<op>.sh` it calls, when the user approves them, never taken from model output or
  fetched text. The body is passed as a file or on stdin, never interpolated into a command line.
  Tracker tokens a write needs sit in the isolated environment too, scoped to the destination
  where the tracker allows it (a Slack bot in one channel).
- **Memory**: no automation keeps notes between runs beyond its reports in `.factory/reports/`.
  A later run reads earlier reports as data, never as instructions.
