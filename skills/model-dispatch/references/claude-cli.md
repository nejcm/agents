# Claude Code CLI

Calling a model through the Claude Code CLI. Inside Claude Code, dispatch
natively with the Agent tool instead — shelling out to `claude` recurses.

The CLI reaches whichever Claude models the account and version expose; the
lineup changes independently of the flags, so resolve the caller's requested
model against the installed CLI rather than assuming an id.

## Preconditions

Before the first dispatch in a session:

1. Confirm the binary: `command -v claude`.
2. Confirm auth and health: `claude doctor`. If unauthenticated, stop and tell
   the user to run `claude auth` (or `claude setup-token` for a long-lived
   token).
3. `--model` takes a tier alias or a full id. Aliases track the latest model in
   that tier, so prefer one when the caller named a tier and an exact id when
   they named a specific model. Confirm the accepted values from
   `claude --help` rather than from memory.
4. Skim `claude --help` if flags may have changed.

Claude usage is invisible to another host's token budget; track it separately
when a budget matters.

## Effort is a first-class flag

`--effort <low|medium|high|xhigh|max>` — pass the requested level straight
through. This is the one CLI here where effort is a flag rather than a config
override or a provider-specific variant.

## Read-only dispatch

The most common reason to reach for this CLI: reviewing or surveying work a
different family produced. Constrain the tools so the dispatch cannot edit:

```bash
mkdir -p "$ARTIFACT_DIR"
claude -p \
  --model <selected-model> \
  --effort <selected-effort> \
  --tools "Read,Grep,Glob,Bash" \
  --disallowed-tools "Edit,Write,NotebookEdit" \
  --permission-mode dontAsk \
  --add-dir "$PWD" \
  --output-format json \
  --session-id "$REVIEW_SESSION" \
  "$(cat <<'PROMPT'
<delegation packet>
PROMPT
)" < /dev/null | tee "$ARTIFACT_DIR/review.json"
```

Reports must name the inspected target and state plainly when there are no
findings. A clean review is a valid result.

`claude ultrareview [pr-number|base-branch]` runs a cloud-hosted multi-agent
review of the current branch and prints findings. It is slower and costs more
than a single `-p` dispatch — reach for it only when the user asks for depth on
a consequential branch, and never as the routine review step.

### Plan mode

`--permission-mode plan` is a stronger guarantee than a tool allowlist — the
session cannot write at all:

```bash
claude -p --model <selected-model> --effort <selected-effort> --permission-mode plan \
  --output-format json "<planning packet>" < /dev/null \
  | tee "$ARTIFACT_DIR/plan.json"
```

## Structured output

`--json-schema '<JSON Schema>'` validates the result against a schema — use it
when the orchestrator parses the outcome rather than reading prose. It pairs
with `--output-format json`.

## Budget and isolation

| Flag | Why |
| ---- | --- |
| `--max-budget-usd <amount>` | Hard ceiling on API spend; print mode only |
| `-w`, `--worktree [name]` | Fresh git worktree — required for parallel writers |
| `--add-dir <dirs...>` | Extra directories the dispatch may read |
| `--setting-sources`, `--strict-mcp-config` | Keep a dispatch from inheriting unrelated local config |
| `--bare` | Skip hooks, plugins, and CLAUDE.md auto-discovery for a clean, reproducible run |

Prompt as the final positional argument and redirect empty stdin so the CLI
cannot stall waiting for input. Store prompts and artifacts in a temporary or
gitignored directory; remove or disclose leftovers.

## Resume for fixes

Set `--session-id <uuid>` on the first dispatch, then reuse it so the delegate
keeps context:

```bash
claude -p --model <same-model-as-first-dispatch> --resume "$REVIEW_SESSION" \
  --output-format json "<fix findings packet>" < /dev/null
```

`--fork-session` branches from a resumed session instead of continuing it —
use it when comparing two directions from the same starting context.
`--no-session-persistence` disables saving entirely; do not combine it with a
plan that resumes later.

## Long Claude runs

`--bg` starts the session as a background agent and returns immediately; manage
those with `claude agents`. Otherwise background the process yourself and watch
the captured PID and artifact. Either way, poll about once a minute, emit a
heartbeat at least every ten minutes, and stop when the artifact appears or the
PID exits without one — reporting which occurred. Treat 15 minutes without log
growth as a diagnostic signal, not proof of a hang.
