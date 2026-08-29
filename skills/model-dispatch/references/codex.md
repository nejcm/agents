# Codex CLI

Calling a model through the Codex CLI. Do not use this path from inside Codex
itself — dispatch natively there.

Codex is a harness, not a model. It reaches whichever models the install
exposes, and the lineup changes independently of the flags, so list the
available ids rather than assuming one. `codex --help` and the config docs are
the source of truth for both ids and effort levels.

`codex exec` runs a prompt; `codex exec review` runs a review. Both take the
model as `-m <model>` and the effort as a config override,
`-c "model_reasoning_effort=<level>"` — the two are passed separately, so carry
whichever model and level the caller specified rather than defaulting either.

If the host can only dispatch its own family natively, run Codex behind a thin
wrapper agent — see "Wrapping Another Family" in `SKILL.md`.

Before relying on an invocation, check the installed CLI help. Give Codex a
self-contained prompt and pass the selected model and effort separately:

```bash
mkdir -p "$ARTIFACT_DIR"
codex exec -m <selected-model> -C "$PWD" -s read-only \
  -c "model_reasoning_effort=<selected-effort>" \
  -o "$ARTIFACT_DIR/result.md" \
  "<focused prompt>" < /dev/null
```

For a dispatch that edits, state permitted files, required behavior,
exclusions, branch authority, and verification. Prefer an isolated branch or worktree;
working directly on one branch is valid for sequential phases because there
are no parallel writers to isolate. Prompt as the final positional argument and
redirect empty stdin: on Windows, piped or absent stdin can stall at `Reading
additional input from stdin...`. Distinguish that stall from a sandbox failure.
If the sandbox fails before commands start, repair that mode and retry once
with broader isolation only when host and user policy permit it. Keep the prompt
tightly scoped and disclose the reduced isolation.

For review, select exactly one target (`--uncommitted`, `--base`, or `--commit`)
_or_ use a focused prompt; the CLI does not allow both. A clean review is a
valid result. Reports must name the inspected target and clearly state when
there are no findings. `--uncommitted` includes untracked files, so discard
findings caused only by unrelated scratch or local-settings files. Do not rerun
an unchanged, already-triaged diff to force findings.

```bash
codex exec review -m <selected-model> --uncommitted \
  -c "model_reasoning_effort=<selected-effort>" \
  -o "$ARTIFACT_DIR/review.md"
```

## Sandbox mode

`-s` takes `read-only`, `workspace-write`, or `danger-full-access`. Choose it
by whether the dispatch must *execute* the project's checks.

`read-only` blocks the temp directory too, so a dispatch that runs tests or a
build fails partway with `EROFS` rather than at launch, and retrying it
unchanged reproduces it. Reasoning over a diff keeps `read-only` — hand it the
verification result instead of the assignment. Anything that must run checks
needs `-s workspace-write` in a throwaway worktree (`--add-dir` for writable
paths outside it). Require reports to name the checks actually executed.

`codex exec resume <session-id>` preserves context but not necessarily the
recorded model: always supply `-m`. Check that any prompt file is non-empty
before resuming. Store prompts and reports in a temporary or gitignored
artifact directory and remove or disclose leftovers.

For computer use, state the flow, environment, whether edits are allowed, and
the screenshot, video, or other evidence required. Confirm that the invoked
Codex environment exposes the necessary tools; CLI availability alone does not
establish computer-use availability.

## Long Codex runs

Launch lengthy `codex exec` runs in the background. Watch the captured PID,
output artifact, and a per-run JSONL log created by redirecting `--json`
stdout. Poll about once a minute; emit a heartbeat at least every ten minutes.
Stop when the artifact appears or the captured PID exits without one, and
report which condition occurred. Treat 15 minutes without log growth as a
diagnostic signal, not proof of a hang.
