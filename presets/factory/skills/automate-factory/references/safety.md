# Write safety

An unattended run has no one to catch a bad action. Every automation is split into steps, and each
step gets only the capability it needs.

## Lethal-trifecta rule

Untrusted input, secrets and egress never meet in one step. Untrusted input is any text the repo
owner did not write: issue and PR bodies, PR and review comments, attachments, error payloads, CI
logs, commits and diffs from other authors, transcripts (they carry tool output and fetched
pages), fetched web pages. Trusted input is the default branch's tracked files and numbers the
repo's own CI produced. A step holds a secret or write access when any tool it has can use one: a
shell (reads env and credential files, runs `gh`, `git push`, `curl`), an MCP server, a hook, a
write-scoped token in its environment.

## Steps

| Step | Model | Reads | Capability |
| ---- | ----- | ----- | ---------- |
| fetch | none | the source (`gh`, `git`, logs) | read-only calls; writes into the run's view only |
| analyze | yes | the run's view: `repo/` (tracked files of the default branch), `input/`, `skills/` | file read and search only; the report is its stdout |
| post | none | the report file | sends it unchanged to one fixed destination |

- **Analyze isolation**: Claude Code with `--restricted --safe-mode --tools "Read,Grep,Glob"
  --strict-mcp-config --no-session-persistence`, run with the view as its working directory.
  `--restricted` confines file tools to that directory, so `.env` files, credential files and
  other sessions stay out of reach; `--safe-mode` drops hooks, plugins, skills and `CLAUDE.md`.
  Managed (policy) settings still apply: if they define hooks, analyze is unavailable on that
  runner. A runner that cannot run this command is not offered an entry with untrusted input.
- **No unattended fixes**: no scheduled run edits code, pushes, opens PRs or replies to threads.
  Entries that lead to changes name a follow-up the user starts from the report, attended, in
  their own harness, choosing what to apply.
- **Dry run**: fetch and analyze only. Writes go to `.factory/reports/` and the run's temp view
  under `.factory/tmp/`, nothing else.
- **Fixed destination**: the post step's target (`--repo <owner/repo>`, issue number, channel) is
  written into the run script when the user approves it, never taken from model output or fetched
  text. The body is passed as a file, never interpolated into a command line.
- **Hosted runners**: checkout with `persist-credentials: false`; the CLI install runs in its own
  step without the model key; the fetch step alone gets `GH_TOKEN`; workflow `permissions:`
  read-only in v1.
- **Memory**: no automation keeps notes between runs beyond its reports in `.factory/reports/`.
  A later run reads earlier reports as data, never as instructions.
