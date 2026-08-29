# OpenCode CLI

A harness, not a model. OpenCode is provider-agnostic — it reaches a model
through `provider/model` ids, so it is the path to a family whose own CLI is
absent or unauthenticated, and the natural one when the user works in OpenCode.
Do not use it from inside OpenCode itself; dispatch natively there.

## Preconditions

Before the first dispatch in a session:

1. Confirm the binary: `command -v opencode`.
2. Confirm the flags: `opencode run --help`. The set below is taken from the
   published CLI docs, not from a local install — verify before relying on it.
3. Discover the provider/model ids available to this install rather than
   guessing them. `--model` takes the form `provider/model`.

OpenCode usage is invisible to another host's token budget; track it separately
when a budget matters.

## Dispatch

```bash
mkdir -p "$ARTIFACT_DIR"
opencode run \
  --model <provider/model> \
  --variant <provider-specific effort> \
  --agent <agent> \
  --format json \
  --auto \
  --session "$SESSION_ID" \
  "$(cat <<'PROMPT'
<delegation packet>
PROMPT
)" < /dev/null | tee "$ARTIFACT_DIR/run.json"
```

| Flag | Why |
| ---- | --- |
| `--model` / `-m` | `provider/model`; the requested model |
| `--variant` | Provider-specific reasoning effort — map the requested level onto whatever the provider exposes, and say so when it has no equivalent |
| `--format json` | Parseable artifact for the orchestrator (`default` is formatted prose) |
| `--agent` | Named agent definition |
| `--mode` | `all`, `primary`, or `subagent` |
| `--auto` | Auto-approve permissions not explicitly denied |
| `--permissions` | Comma-separated allowlist; prefer this over `--auto` for a read-only survey |
| `--file` / `-f` | Attach files to the message |

`--variant` is the only effort control, and it is provider-specific. When the
selected provider exposes no equivalent to the requested level, say so rather
than silently dispatching at the default.

For a read-only survey or review, constrain with `--permissions` instead of
`--auto`, and confirm the resulting session cannot write before trusting the
result as independent.

## Resume for fixes

`--session` / `-s` continues a specific session id; `--continue` / `-c`
continues the last one. Prefer an explicit id so a concurrent run cannot be
resumed by accident. `--fork` branches from a session instead of continuing it
— use it when comparing two directions from the same context.

## Long OpenCode runs

Launch lengthy `opencode run` invocations in the background. Watch the captured
PID and the JSON artifact; add `--print-logs` (stderr) and `--log-level` when a
run needs diagnosis. Poll about once a minute, emit a heartbeat at least every
ten minutes, and stop when the artifact appears or the PID exits without one —
reporting which occurred. Treat 15 minutes without log growth as a diagnostic
signal, not proof of a hang.
