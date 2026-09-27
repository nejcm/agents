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

Use a fresh `ARTIFACT_DIR` per run (`mktemp -d`) and write the packet to
`$ARTIFACT_DIR/build.prompt.md` first; a reused directory lets a stale packet
pass the check.

```bash
PROMPT_FILE="$ARTIFACT_DIR/build.prompt.md"
test -s "$PROMPT_FILE" || { printf 'Missing prompt: %s\n' "$PROMPT_FILE" >&2; exit 1; }

CHAT_ID="$(agent create-chat)" && test -n "$CHAT_ID" ||
  { printf 'Cursor did not return a chat id\n' >&2; exit 1; }
printf '%s\n' "$CHAT_ID" > "$ARTIFACT_DIR/chat-id"

agent -p --trust --force \
  --model <id-from-agent-models> \
  --workspace "$PWD" \
  --resume "$CHAT_ID" \
  --output-format json \
  --sandbox enabled \
  "$(cat "$PROMPT_FILE")" < /dev/null \
  > "$ARTIFACT_DIR/build.json" 2> "$ARTIFACT_DIR/build.stderr.log"
status=$?
printf '%s\n' "$status" > "$ARTIFACT_DIR/build.exit-status"
exit "$status"
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
| `--sandbox enabled` | Default for delegated work; host launcher access is handled separately |
| `--sandbox disabled` | Only with explicit authorization and host-policy approval; never to fix host access to Cursor's state files |
| `--approve-mcps` | Only if the packet needs MCP and prompts would block |

Default mode is full Agent (edits allowed). Use `--mode ask` or `--plan` only
for read-only survey or planning dispatches.

## Recovering from setup and launch errors

- `EAI_AGAIN` from `agent models` is a DNS/network lookup failure, not evidence
  that the requested model is unavailable. Check connectivity and retry once;
  if discovery still fails, report that blocker instead of guessing an id or
  switching to `auto`.
- `unable to open database file` can come from the host process being unable to
  access Cursor's own state database. Diagnose the path and use the host's
  approved access mechanism if needed, while keeping `--sandbox enabled` for
  the delegate. Do not turn the Cursor sandbox off to fix a host-level denial.
- If the expected prompt file is missing or empty, rebuild it from the current
  authorized task packet and verify it before launching; never send an empty prompt.
- If a background run appears stalled, inspect its task or process ID, stderr,
  and exit-status file before retrying. Verify the prompt file is present, passed as one quoted argument,
  and stdin is redirected; do not start a duplicate while the first process is
  still running. Resume fixes with the saved chat id and same model.

For dispatches that edit, state permitted files, required behavior,
exclusions, branch/worktree authority, and verification. Prefer an isolated
worktree when parallel writers exist; a single shared branch is fine for
sequential staged phases.

## Resume for fixes

Reuse the same chat so the delegate keeps context. Write each round's packet to
a new `fix-$ROUND.prompt.md`:

```bash
CHAT_ID="$(cat "$ARTIFACT_DIR/chat-id")"
FIX="$ARTIFACT_DIR/fix-$ROUND"
test -n "$CHAT_ID" && test -s "$FIX.prompt.md" ||
  { printf 'Missing chat id or fix prompt\n' >&2; exit 1; }

agent -p --trust --force \
  --model <same-model-as-build> \
  --workspace "$PWD" \
  --resume "$CHAT_ID" \
  --output-format json \
  --sandbox enabled \
  "$(cat "$FIX.prompt.md")" < /dev/null \
  > "$FIX.json" 2> "$FIX.stderr.log"
status=$?
printf '%s\n' "$status" > "$FIX.exit-status"
exit "$status"
```

`agent --continue` resumes the latest session when you did not keep a chat id;
prefer an explicit `--resume "$CHAT_ID"`.

## Survey-only Agent CLI use

For a read-only survey, use `--mode ask` with a model id from `agent models`
and confirm the session cannot write before trusting the result.

## Long Agent CLI runs

Follow [Watching Long Runs](../SKILL.md#watching-long-runs). Capture the child
PID and the per-run structured output, such as `$ARTIFACT_DIR/build.json`.
