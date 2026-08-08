# Cursor Auto / Composer via Agent CLI

Builder fallback path. Use when `model-routing` falls through to Cursor
Auto/Composer (Codex unavailable, or the user explicitly requests Cursor
Auto/Composer).

Shell out to the **Cursor Agent CLI** binary `agent` (often also installed as
`cursor-agent`). Do **not** use the IDE `cursor` binary for orchestration.

## Preconditions

Before the first dispatch in a session:

1. Confirm the binary: `command -v agent` (or `cursor-agent`).
2. Confirm auth: `agent status` / `agent about`. If not logged in, stop and tell
   the user to run `agent login` or set `CURSOR_API_KEY`.
3. Discover model IDs: `agent models` or `agent --list-models`. Never invent
   IDs. Prefer `auto` when the user asked for Auto mode; otherwise pick the
   current Composer id (e.g. `composer-2` / `composer-2.5`) from the list.
4. Skim `agent --help` if flags may have changed.

Cursor usage is invisible to Claude workflow token budgets; track it separately
when a budget matters.

## Builder (implementation)

Use print/headless mode so Claude can drive it non-interactively:

```bash
mkdir -p "$ARTIFACT_DIR"
CHAT_ID=$(agent create-chat)

agent -p --trust --force \
  --model <auto|composer-id-from-agent-models> \
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
| `-p` / `--print` | Non-interactive; needed when Claude shells out |
| `--trust` | Skip workspace trust prompts in headless mode |
| `--force` / `--yolo` | Auto-approve tool/shell commands |
| `--model` | Auto or Composer id from `agent models` |
| `--output-format json` | Parseable artifact for the orchestrator |

Optional:

| Flag | When |
| ---- | ---- |
| `--worktree [name]` | Isolate writes; required for parallel writers |
| `--worktree-base <ref>` | Base the worktree on a branch other than HEAD |
| `--sandbox enabled` | Tighter command isolation when policy requires it |
| `--approve-mcps` | Only if the packet needs MCP and prompts would block |

Default mode is full Agent (edits allowed). Use `--mode ask` or `--plan` only
for read-only survey/planning dispatches — not for Builder implementation.

For implementation packets, state permitted files, required behavior,
exclusions, branch/worktree authority, and verification. Prefer an isolated
worktree when parallel writers exist; a single shared branch is fine for
sequential staged phases.

Prompt as the final argument and redirect empty stdin so the CLI cannot stall
waiting for input. Store `CHAT_ID`, the JSON artifact, and any prompt text in a
temporary or gitignored artifact directory; remove or disclose leftovers.

## Resume Builder for fixes

Reuse the same chat so the Builder keeps context:

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
<bulleted actionable items from Reviewer/Judge>
Return: changed files, checks, remaining blockers
EOF
)" < /dev/null | tee "$ARTIFACT_DIR/fix.json"
```

`agent --continue` resumes the latest session when you did not keep a chat id;
prefer an explicit `--resume "$CHAT_ID"`.

## Survey-only Agent CLI use

If you must use the Agent CLI for a read-only survey, use `--mode ask` and a
non-Builder model id from `agent models`, and disclose reduced independence if
it is the same family as the Builder. Independent review still uses the
Reviewer/Judge from routing, not the Builder that produced the diff.

## Long Agent CLI runs

Launch lengthy `agent -p` runs in the background. Watch the captured PID and
`$ARTIFACT_DIR/build.json` (or redirected log). Poll about once a minute; emit a
heartbeat at least every ten minutes. Stop when the artifact is complete or the
PID exits without one, and report which condition occurred. Treat 15 minutes
without log growth as a diagnostic signal, not proof of a hang.
