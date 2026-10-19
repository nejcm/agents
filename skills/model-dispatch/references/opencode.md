# OpenCode CLI

A harness, not a model. OpenCode is provider-agnostic — it reaches a model
through `provider/model` ids, so it is the path to a family whose own CLI is
absent or unauthenticated, and the natural one when the user works in OpenCode.
Do not use it from inside OpenCode itself; dispatch natively there.

## Preconditions

Before the first dispatch in a session:

1. Confirm the binary: `command -v opencode`.
2. Confirm the flags: `opencode run --help`. The set below matches v2.0.32;
   verify before relying on it.
3. Discover the provider/model ids available to this install rather than
   guessing them. `--model` takes the form `provider/model#variant`.

OpenCode usage is invisible to another host's token budget; track it separately
when a budget matters.

## Dispatch

```bash
test -s "$PROMPT_FILE" || { printf 'Missing prompt: %s\n' "$PROMPT_FILE" >&2; exit 1; }
opencode run \
  --model '<provider/model>#<variant>' \
  --agent <agent> \
  --format json \
  --session "$SESSION_ID" \
  "$(cat "$PROMPT_FILE")" < /dev/null \
  > "$ARTIFACT_DIR/run.json" 2> "$ARTIFACT_DIR/run.stderr.log"
```

| Flag | Why |
| ---- | --- |
| `--model` / `-m` | `provider/model#variant`; the requested model and effort |
| `--format json` | Parseable artifact for the orchestrator (`default` is formatted prose) |
| `--agent` | Named agent definition |
| `--auto` | Auto-approve permissions not explicitly denied |
| `--file` / `-f` | Attach files to the message |

The `#variant` suffix is the only effort control, and it is provider-specific.
When the selected provider exposes no equivalent to the requested level, say so
rather than silently dispatching at the default.

## Permissions

`opencode run` cannot prompt: any permission the config sets to `ask` is
auto-rejected (`permission requested: edit (...); auto-rejecting`), including
`external_directory` access outside the cwd such as the host's scratchpad. Keep
every path the delegate must read or write under its cwd or worktree, in a
gitignored directory. The run still exits and reports, so grep its output for
`auto-rejecting` before trusting the result; a hit means partial work.

Without `--auto`, a read-only survey or review fails closed on writes. A
writing dispatch needs `--auto` or a config that allows the edits; Claude Code
auto mode may deny `--auto` as an unsafe agent, so ask the user rather than
working around it.

## Resume for fixes

`--session` / `-s` continues a specific session id; `--continue` / `-c`
continues the last one. Prefer an explicit id so a concurrent run cannot be
resumed by accident. `--fork` branches from a session instead of continuing it
— use it when comparing two directions from the same context.

## Long OpenCode runs

Follow [Watching Long Runs](../SKILL.md#watching-long-runs). Capture the child
PID and per-run JSON output. Add `--print-logs` on stderr and `--log-level` when
needed for diagnosis.
