# Cursor Agent CLI

Calling a model through the Cursor Agent CLI. Cursor is a harness, not a model:
it fronts several families, and which are available depends on the account and
the CLI version, so list them rather than assuming.

Shell out to the **Cursor Agent CLI** binary `agent` (often also installed as
`cursor-agent`). Do **not** use the IDE `cursor` binary for orchestration, and
do not use this path from inside Cursor itself — dispatch natively there.

## Preconditions

Before the first dispatch in a session:

1. Confirm the binary: `command -v agent` (or `cursor-agent`).
2. Confirm auth: `agent status` / `agent about`. If not logged in, stop and tell
   the user to run `agent login` or set `CURSOR_API_KEY`.
3. Discover model IDs: `agent models` or `agent --list-models`. Never invent
   IDs — take the caller's requested model from that list. `auto` selects
   Cursor's own routing; every other id (Cursor's own models and the
   third-party families it fronts) must come from the listing verbatim.
4. Skim `agent --help` if flags may have changed.

Cursor usage is invisible to the host's own token budget; track it separately
when a budget matters.

## Implementation dispatch

Use print/headless mode so the orchestrator can drive it non-interactively:

```bash
mkdir -p "$ARTIFACT_DIR"
CHAT_ID=$(agent create-chat)

agent -p --trust --force \
  --model <id-from-agent-models> \
  --workspace "$PWD" \
  --resume "$CHAT_ID" \
  --output-format json \
  --sandbox disabled \
  "$(cat <<'EOF'
<delegation packet>
EOF
)" < /dev/null | tee "$ARTIFACT_DIR/build.json"
```

Required headless flags:

| Flag | Why |
| ---- | --- |
| `-p` / `--print` | Non-interactive; needed when the orchestrator shells out |
| `--trust` | Skip workspace trust prompts in headless mode |
| `--force` / `--yolo` | Auto-approve tool/shell commands |
| `--model` | The requested id, verbatim from `agent models` |
| `--output-format json` | Parseable artifact for the orchestrator |

Optional:

| Flag | When |
| ---- | ---- |
| `--worktree [name]` | Isolate writes; required for parallel writers |
| `--worktree-base <ref>` | Base the worktree on a branch other than HEAD |
| `--sandbox enabled` | Tighter command isolation when policy requires it |
| `--approve-mcps` | Only if the packet needs MCP and prompts would block |

Default mode is full Agent (edits allowed). Use `--mode ask` or `--plan` only
for read-only survey or planning dispatches.

For dispatches that edit, state permitted files, required behavior,
exclusions, branch/worktree authority, and verification. Prefer an isolated
worktree when parallel writers exist; a single shared branch is fine for
sequential staged phases.

Prompt as the final argument and redirect empty stdin so the CLI cannot stall
waiting for input. Store `CHAT_ID`, the JSON artifact, and any prompt text in a
temporary or gitignored artifact directory; remove or disclose leftovers.

## Resume for fixes

Reuse the same chat so the delegate keeps context:

```bash
agent -p --trust --force \
  --model <same-model-as-build> \
  --workspace "$PWD" \
  --resume "$CHAT_ID" \
  --output-format json \
  "$(cat <<'EOF'
Fix the actionable review findings below. Do not expand scope.
Verify with: <checks>
Findings:
<bulleted actionable items from the review>
Return: changed files, checks, remaining blockers
EOF
)" < /dev/null | tee "$ARTIFACT_DIR/fix.json"
```

`agent --continue` resumes the latest session when you did not keep a chat id;
prefer an explicit `--resume "$CHAT_ID"`.

## Survey-only Agent CLI use

For a read-only survey, use `--mode ask` with a model id from `agent models`
and confirm the session cannot write before trusting the result.

## Long Agent CLI runs

Launch lengthy `agent -p` runs in the background. Watch the captured PID and
`$ARTIFACT_DIR/build.json` (or redirected log). Poll about once a minute; emit a
heartbeat at least every ten minutes. Stop when the artifact is complete or the
PID exits without one, and report which condition occurred. Treat 15 minutes
without log growth as a diagnostic signal, not proof of a hang.
