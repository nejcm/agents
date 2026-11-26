# Antigravity CLI

Calling a model through Google's Antigravity CLI, the path to the Gemini
families (Neon, Argon, Hydrogen, Flash). It is a harness, not a model: it also
fronts some Claude and open-weight models, but use their own CLI for those when
it is available. Do not use this path from inside Antigravity itself — dispatch
natively there.

The binary is `antigravity`, also installed as `agy`.

## Preconditions

Before the first dispatch in a session:

1. Confirm the binary: `command -v antigravity agy`.
2. Confirm the flags: `antigravity --help`. The set below matches v1.5.15;
   verify before relying on it.
3. Confirm auth and discover model IDs in one step: `antigravity models`. A
   listing proves the CLI is signed in; on failure, stop and tell the user to
   sign in through an interactive `antigravity` session. Take the id from the
   listing verbatim.

Antigravity usage is invisible to the host's own token budget; track it
separately when a budget matters.

## Model and effort

The listing exposes most models as `<family>-<effort>` variants, such as
`gemini-4-neon-high`. Two equivalent ways to select a model and effort:

- Pass the variant id alone: `--model gemini-4-neon-high`.
- Pass the base id with `--effort`: `--model gemini-4-neon --effort high`.

Never combine a variant id with a different `--effort` — the CLI rejects it
(`--model ...-low conflicts with --effort=high`). A requested level with no
listed variant has no equivalent; the CLI rejects it (`has no "xhigh" effort`).
Say so instead of taking the default.

## Dispatch

Unlike `claude -p`, `-p` takes the prompt as its own value. Pass it last; a
bare `-p` before `--model` swallows the flag as the prompt and exits 2.

```bash
test -s "$PROMPT_FILE" || { printf 'Missing prompt: %s\n' "$PROMPT_FILE" >&2; exit 1; }
antigravity \
  --model <id-from-antigravity-models> \
  --output-format json \
  --mode plan \
  --add-dir "$ARTIFACT_DIR" \
  -p "$(cat "$PROMPT_FILE")" < /dev/null \
  > "$ARTIFACT_DIR/run.json" 2> "$ARTIFACT_DIR/run.stderr.log"
status=$?
printf '%s\n' "$status" > "$ARTIFACT_DIR/run.exit-status"
```

| Flag | Why |
| ---- | --- |
| `-p` / `--print` | Non-interactive; its value is the prompt |
| `--model` | The requested id, verbatim from `antigravity models` |
| `--effort` | `low`/`medium`/`high`/`xhigh`/`max`, only with a base id |
| `--output-format json` | One JSON object: `conversation_id`, `status`, `response`, `usage`; `denied_actions`, `structured_output`, or `error` when present |
| `--json-schema` | Enforce structured output, inline or as a file path; read `.structured_output`, not `.response` |
| `--mode` | `plan`, `accept-edits`, or `auto` (account-gated; falls back to default with only a stderr warning) |
| `--sandbox` | Terminal restrictions for the delegate |
| `--add-dir` | Widen the workspace beyond the cwd (repeatable); reads outside it are auto-denied |
| `--print-timeout` | Cap the turn as a Go duration (`30s`, `5m`); bare `30` exits 2. `0s` (default) waits |

## Permissions and isolation

Headless mode cannot prompt: a tool needing approval is auto-denied, the run
still reports `"status":"SUCCESS"`, and the denial shows only in
`denied_actions` (often with an empty `response`). Check `denied_actions`
before trusting a result; any entry means partial work. `--add-dir` every
directory outside the cwd the delegate must read, including `$ARTIFACT_DIR`.

- **Read-only survey or review:** `--mode plan`. Edits become a plan artifact
  instead; shell commands are planned or auto-denied, never run. Write the diff
  or command output to a file, pass its path, and tell the prompt not to run
  shell commands.
- **Default mode is not read-only:** omitting `--mode` lets the delegate edit
  files in a trusted workspace.
- **Writing:** `--mode accept-edits` approves file edits only. Shell commands,
  such as running checks, need allow-rules via `--settings`
  (`'{"permissions":{"allow":["command(<pattern>)"]}}'`, session-only) or
  `--dangerously-skip-permissions` with explicit authorization. Keep
  `--sandbox` on.

The CLI has no worktree flag. Create the worktree first and run the delegate
from inside it; parallel writers each need their own.

## Resume for fixes

Save `conversation_id` from the JSON output and pass it back with the same
model, mode, and flags; a dropped `--mode` falls back to the writable default.

```bash
CONVERSATION_ID="$(jq -r '.conversation_id // empty' "$ARTIFACT_DIR/run.json")"
FIX="$ARTIFACT_DIR/fix-$ROUND"
test -n "$CONVERSATION_ID" && test -s "$FIX.prompt.md" ||
  { printf 'Missing conversation id or fix prompt\n' >&2; exit 1; }
antigravity \
  --model <same-model> \
  --output-format json \
  --mode <same-mode> \
  --add-dir "$ARTIFACT_DIR" \
  --conversation "$CONVERSATION_ID" \
  -p "$(cat "$FIX.prompt.md")" < /dev/null \
  > "$FIX.json" 2> "$FIX.stderr.log"
status=$?
printf '%s\n' "$status" > "$FIX.exit-status"
```

`--continue` / `-c` resumes the most recent conversation; prefer the explicit
id so a concurrent run cannot be resumed by accident.

## Long Antigravity runs

Follow [Watching Long Runs](../SKILL.md#watching-long-runs). JSON output arrives
only at exit; use `--output-format stream-json` to see progress, and
`--log-file` for a per-run log when diagnosing.
