# GPT-5.6 via Codex

Default Builder path. Use when `model-routing` selects GPT-5.6 / Codex, or
when the Builder fallback is not needed.

Use `codex exec` or `codex exec review` with
`-m <variant selected by model-routing>`. For Builder dispatches, apply the
Builder matrix: use `gpt-5.6-luna` at `xhigh` (or `max` when extra depth is
worth the latency) for bounded simple-to-medium work, and `gpt-5.6-sol` at
`medium` or `high` for medium-to-very-complex work. In the overlapping medium
band, select Luna only for bounded, easily verified work; otherwise select Sol.

Do not hard-code one GPT-5.6 variant for every role. If host workflows accept
only Claude models, use a thin host-native wrapper selected by the
Claude-specific model defaults (normally Sonnet 5) that runs Codex and returns
its artifact. Use its schema option when structured output helps. Prefix its
label with `gpt-5.6:` so the UI does not misrepresent the actual worker; if a
reused wrapper changes roles, rename it or disclose the mismatch. Parallel
writers need separate worktrees. Codex usage is invisible to Claude workflow
token budgets, so track it separately when a budget matters.

Before relying on an invocation, check the installed CLI help. Give Codex a
self-contained prompt and pass the selected variant and effort separately:

```bash
mkdir -p "$ARTIFACT_DIR"
codex exec -m <selected-variant> -C "$PWD" -s read-only \
  -c "model_reasoning_effort=<selected-effort>" \
  -o "$ARTIFACT_DIR/result.md" \
  "<focused prompt>" < /dev/null
```

For implementation, state permitted files, required behavior, exclusions,
branch authority, and verification. Prefer an isolated branch or worktree;
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
codex exec review -m <selected-variant> --uncommitted \
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
