---
name: model-orchestration
description: Claude Code execution mechanics for multi-model orchestration — dispatch order, orchestration patterns, the Codex CLI (codex exec / codex exec review) and its wrapper pattern for running GPT-5.6, delegation packets, result verification, and long-running work. Use when implementing an approved plan or design, or when starting any medium-to-high complexity task that may warrant delegation, parallel work, plan→build→judge/review→verify-and-fix.
---

# Model Orchestration

Claude Code-specific dispatch mechanics. The always-loaded `model-routing`
policy owns roles, effort, model preferences, family-independence requirements,
and fallback order. This skill only covers how to dispatch, delegate, and run
Codex here. Where they conflict, the user's instructions and repository rules
win.

## Dispatch Mechanics

Apply `model-routing` independently at every dispatch because role and effort
can change across one workflow. Then confirm that the selected mechanism and
model are available and support the required tools, isolation, and effort.
Never invent a capability or identifier; apply the policy's fallback and
disclosure rules when necessary.

Use the first capable mechanism:

1. A host-native subagent or workflow that supports the selected model, effort,
   tools, and isolation.
2. A non-interactive CLI such as `codex exec` or `claude -p`.
3. Local execution, with any lost specialization or independence disclosed.
   This fallback is not available for the staged workflow below, whose current
   session must remain orchestration-only.

Limits: at most three distinct automatic delegates per orchestration, at most
one per role unless scopes differ, and no duplicate work without a specific
reason. Resume the existing Builder for the fix pass rather than creating a
fourth delegate. Parallelize independent read-only work; sequence dependent
phases. Retry a failed delegation once with a concrete correction, then stop
and re-plan. If a delegate is _interrupted_ mid-task (session/API limit,
timeout) rather than wrong, resume it (`SendMessage` to its id or name) to
preserve its transcript instead of cold-respawning; reserve the corrected
retry for actually-wrong output. Infrastructure failures (Codex stdin block,
shell-timeout cap, sandbox runner) are _not_ wrong output: fix the invocation
and resume without spending the correction retry. That once-per-delegate budget
is for genuinely wrong results and is counted per delegate. Describe a review or second opinion as
independent only when another model actually performed it.

## Orchestration Patterns

Choose the smallest pattern that provides the needed benefit:

- **Specialist delegate** — one bounded task requiring different expertise or
  tools.
- **Parallel fan-out** — independent read-only surveys or reviews, followed by
  synthesis.
- **Plan → build → judge/review → verify and fix** — staged implementation
  work with independent evaluation and a final evidence-based correction pass.
- **Second opinion** — a read-only, cross-family challenge to a material
  decision or conclusion.

For staged work, the current session is an orchestrator only. It selects and
dispatches subagents, passes artifacts between them, resumes existing agents,
tracks progress, requests necessary user decisions, and reports the outcome.
It does not author the plan, inspect or edit implementation files, perform the
review, adjudicate findings, apply fixes, or run verification itself. All phase
work and repository commands run inside the assigned subagents. A final
coordination action the user explicitly authorizes — e.g. committing or
pushing the completed result — may run directly in the orchestrator
rather than spawning a subagent.

Keep phases sequential and prevent self-review. Follow this sequence:

1. **Plan.** If the user or conversation already supplies an accepted,
   executable plan, pass it forward and skip this dispatch. Otherwise, dispatch
   a **Planner** subagent to locate and assess any referenced plan or produce a
   concrete one with scope, success criteria, risks, and checks.
2. **Implement.** Dispatch a **Builder** subagent with the accepted plan. Require
   it to implement only the agreed scope and report changed files and checks
   run.
3. **Judge/review.** Dispatch an independent **Reviewer/Judge** subagent with the
   resulting diff and accepted plan. Apply the routing policy's
   family-independence preference. It reviews against the plan, user
   requirements, repository rules, and correctness.
4. **Verify and fix.** Resume the existing **Builder** to address actionable
   findings, then the **Reviewer/Judge** to verify the result. Follow **Handle
   Results** for adjudication and re-review criteria.

Do not use the full plan → build → judge/review → verify-and-fix sequence as a
default for all non-trivial work. Use it when staged implementation and
independent review materially reduce risk. Use a second opinion when explicitly
requested or when a decision is high-impact, disputed, hard to reverse,
security-sensitive, or held with low confidence.

## When `model-routing` selects GPT-5.6

- Entry points are `codex exec` and `codex exec review` with `-m gpt-5.6-sol`.
  A direct interactive shell call is the default only outside the staged
  workflow; its orchestrator-only boundary otherwise applies. For work the
  named entry points do not cover (investigation, data analysis), run
  `codex exec -m gpt-5.6-sol -s read-only` with a self-contained prompt.
- Workflow and subagent `model` parameters only accept Claude models, so wrap
  Codex in a thin host-native agent selected through `model-routing` (normally
  the **Cheap Worker** role). Its prompt writes a self-contained Codex prompt,
  runs `codex exec` via shell, and returns the report. Use the wrapper's
  `schema` option when structured output is useful. A thin cheap wrapper cannot
  reliably tell a genuine hang from a still-running job, so bake the standing
  Codex invocation pattern (stdin redirect and background+poll, both below) into
  its prompt rather than leaving it to diagnose failures on its own.
- Prefix every wrapper label with `gpt-5.6:`, e.g.
  `{label: 'gpt-5.6:review-auth'}`. The workflow UI shows the wrapper's Claude
  model, so the label is the only indication of the real worker.
- Codex runs routinely exceed the Bash tool's 10-minute (600000 ms) cap.
  Default to running the wrapper's `codex exec` in the background and polling
  for the `-o` artifact plus process exit; do not block a foreground call and
  then read its timeout as a Codex hang.
- Parallel Codex implementation wrappers must use `isolation: 'worktree'`;
  never give parallel writers the same worktree.
- Workflow token budgets count only Claude tokens. Codex usage is invisible to
  `budget.spent()`; track it separately when a budget matters.

## Calling Codex

Verify syntax with the installed `codex --help`, `codex exec --help`, and
`codex exec review --help`. Use a self-contained, direct prompt; do not prompt
Codex as if it were Claude. Pass the supported effort selected through
`model-routing` with `-c model_reasoning_effort=<selected-effort>`; this is
separate from any wrapper's effort. Create `$ARTIFACT_DIR` before every
invocation and write results there so they survive long runs and wrapper
timeouts. Use a temp or gitignored directory and clean it up (or tell the user)
when done, so stray prompt/report files do not linger in `git status`.

Investigation (read-only):

```bash
mkdir -p "$ARTIFACT_DIR"
codex exec -m gpt-5.6-sol -C "$PWD" -s read-only \
  -c "model_reasoning_effort=<selected-effort>" \
  -o "$ARTIFACT_DIR/result.md" "<focused investigation prompt>" < /dev/null
```

Implementation: prefer a separate branch. State the permitted files,
required behavior, exclusions, and verification. When phases
must land as sequential commits on one branch (e.g. review gates
between them), working directly on that branch — no worktree — is a valid
pattern; isolation buys nothing without parallel writers. Two things Codex
needs stated explicitly, or it stalls or fails:

- **Branch authority.** On a branch it treats as protected (`master`/`main`)
  Codex stops and asks before editing. Grant it up front — "you may edit
  branch X directly; do not commit."
- **Sandbox fallback.** If every command fails before starting (e.g. Windows
  `sandbox: timed out ... connecting runner pipe-in`), the sandbox runner is
  broken, not the prompt; rerun once with `-s danger-full-access` plus the
  host's sandbox-disable flag only when user and host policy permit it, keep
  the prompt tightly scoped, and disclose the reduced isolation. Don't spend
  multiple retries on the same broken mode.
- **Stdin block (Windows).** `codex exec` can hang on `Reading additional
input from stdin...` when it does not receive the prompt as an argument.
  Always pass the prompt as the final positional argument and redirect stdin
  from empty — `codex exec … "$(cat "$ARTIFACT_DIR/prompt.txt")" < /dev/null`;
  never pipe the prompt in through stdin. This is a distinct failure from the
  sandbox timeout above — same ~10-minute stall, different cause — so don't
  misdiagnose it as a sandbox or long-run problem.

Review — select exactly one target (`--uncommitted`, `--base <branch>`, or
`--commit <sha>`). A focus prompt cannot be combined with a target flag; the
CLI rejects it:

```bash
mkdir -p "$ARTIFACT_DIR"
# Target-flag mode (no prompt argument):
codex exec review -m gpt-5.6-sol --uncommitted \
  -c "model_reasoning_effort=<selected-effort>" \
  -o "$ARTIFACT_DIR/review.md"

# Focus mode (prompt, no target flag) — describe the target in the prompt:
codex exec review -m gpt-5.6-sol \
  -c "model_reasoning_effort=<selected-effort>" \
  -o "$ARTIFACT_DIR/review.md" \
  "Review the uncommitted changes to src/foo.ts for <focus>."
```

`--uncommitted` also reviews untracked files; expect noise findings on local
scratch/settings files (e.g. `.claude/settings.local.json`) and discard them
rather than acting on them.

Computer use: state the flow, environment, expected evidence, screenshot or
video requirements, and whether edits are allowed. Confirm the invoked Codex
environment actually has the needed tools; CLI availability alone does not
prove computer-use availability.

On timeout, inspect the process and artifact before applying the retry or
resume policy in **Dispatch Mechanics**. If a review that inspected its target
finds no issues, accept that; do not rerun to force findings. If a diff was
already reviewed (and findings triaged) this session and has not changed, cite
that review instead of dispatching another. Reports must name the inspected
target and state clearly when there are no findings.

## Delegation Packet

Send only the context required for the assignment — no whole-codebase dumps or
raw transcripts:

```text
Objective: <specific outcome>
Success criteria: <observable result>
Role: <planner | builder | reviewer/judge | cheap worker>
Effort: <supported effort>
Context: <compressed facts, relevant files, commands, or links>
Constraints: <repository rules, user requirements, safety, scope, budget>
Workspace/mode: <read-only or isolated writable worktree>
Do not: <explicit exclusions>
Verify with: <tests, checks, or evidence>
Return: outcome, evidence, changed files, checks, confidence, blockers
```

## Handle Results

Enforce the Delegation Packet's `Return` contract. Verification evidence must
cite repository tools, tests, or primary sources. Summarize results instead of
forwarding raw transcripts. Between staged phases, preserve the objective,
constraints, accepted plan, diff or result report, and unresolved risks.

Do not let the Builder make the final decision on critiques of its own work.
Have the Reviewer/Judge subagent adjudicate every finding the Builder rejects
or skips, then directly inspect the fix diff and run the relevant checks.
Resume it for a full second review only when fixes are material or touch logic,
not when they merely add or adjust tests.

Treat duration and change size as risk signals, not proof of quality: a fix
that takes unexpectedly long or touches broad architecture should receive more
Reviewer/Judge scrutiny, and a quick fix still requires subagent verification.
Ask the user when a product or safety decision cannot be inferred safely.

## Long-Running Work

For a long-running goal, keep a plan checklist with observable completion
criteria and update it as work lands. A persistence request does not authorize
new external effects: rebasing, closing or merging PRs, changing branches, and
deploying require the user's explicit authority. Preserve human control of
production even when staging and merges are automated.
