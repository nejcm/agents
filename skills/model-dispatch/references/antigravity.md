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
listed variant has no equivalent; say so instead of taking the default.

## Dispatch

`-p` takes the prompt as its own value, so put every other flag before it. A
bare `-p` followed by `--model` swallows the flag as the prompt and exits 2.

```bash
test -s "$PROMPT_FILE" || { printf 'Missing prompt: %s\n' "$PROMPT_FILE" >&2; exit 1; }
antigravity \
  --model <id-from-antigravity-models> \
  --output-format json \
  --mode plan \
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
| `--output-format json` | One JSON object: `conversation_id`, `status`, `response`, `usage`, and `denied_actions` when any |
| `--json-schema` | Enforce structured output, inline or as a schema file path |
| `--mode` | `plan`, `accept-edits`, or `auto` |
| `--sandbox` | Terminal restrictions for the delegate |
| `--add-dir` | Widen the workspace beyond the cwd (repeatable) |
| `--print-timeout` | Cap the turn; `0` (default) waits until it completes |

## Permissions and isolation

Headless mode cannot prompt: a tool needing approval is auto-denied, the run
still reports `"status":"SUCCESS"`, and the denial shows only in
`denied_actions` (often with an empty `response`). Check `denied_actions`
before trusting a result; any entry means partial work.

- **Read-only survey or review:** `--mode plan`. A request to write produces a
  plan instead of edits, and shell commands are planned, not run — write the
  diff or command output to a file and pass its path.
- **Writing:** a permission allow-rule in settings (`--settings` takes a
  session-only JSON object or file), `--mode accept-edits` for file edits, or
  `--dangerously-skip-permissions` only with explicit authorization. Keep
  `--sandbox` on.

The CLI has no worktree flag. Create the worktree first and run the delegate
from inside it; parallel writers each need their own.

## Resume for fixes

Save `conversation_id` from the JSON output and pass it back with the same
model:

```bash
CONVERSATION_ID="$(jq -r .conversation_id "$ARTIFACT_DIR/run.json")"
test -n "$CONVERSATION_ID" || { printf 'Missing conversation id\n' >&2; exit 1; }
antigravity --model <same-model> --output-format json \
  --conversation "$CONVERSATION_ID" \
  -p "$(cat "$FIX_PROMPT_FILE")" < /dev/null > "$ARTIFACT_DIR/fix.json"
```

`--continue` / `-c` resumes the most recent conversation; prefer the explicit
id so a concurrent run cannot be resumed by accident.

## Long Antigravity runs

Follow [Watching Long Runs](../SKILL.md#watching-long-runs). JSON output arrives
only at exit; use `--output-format stream-json` to see progress, and
`--log-file` for a per-run log when diagnosing.
