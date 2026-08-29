---
name: model-dispatch
description: How to call another agent CLI — per-CLI invocation references (Codex, Cursor `agent`, `claude`, OpenCode), passing whichever model and effort the caller selected, isolation, resume, structured output, and watching long runs. Use when shelling out to another agent CLI.
---

# Model Dispatch

How to call another agent CLI correctly. Each CLI is a harness that can drive
several models; the caller supplies which model and effort to use. This skill
does not choose them, holds no model preferences, and takes no position on
whether the work should have been delegated at all. Any model id appearing
below is an illustrative placeholder — discover the real ids from the CLI.

Nothing here assumes an orchestration pattern — use it for a single delegated
call as readily as for one step of a larger workflow.

## Know Your Host

Before the first dispatch in a session, establish two things:

1. **Which host you are.** Codex, Claude Code, Cursor, OpenCode, or ForgeCode.
   Never shell out to your own host's CLI — that recurses. Use the host's
   native subagent/workflow mechanism for same-host work.
2. **Which CLIs exist.** `command -v codex claude agent cursor-agent opencode`.
   Absence of a binary rules that path out; say so rather than
   pretending the dispatch happened. A CLI being installed does not mean it is
   authenticated — each reference opens with its own precondition check.

Read only the references you need:

| Reference                  | CLI                                                    |
| -------------------------- | ------------------------------------------------------ |
| `references/codex.md`      | `codex exec` — any model and effort the install exposes |
| `references/agent-cli.md`  | Cursor `agent -p` — any model in `agent models`         |
| `references/claude-cli.md` | `claude -p` — any model alias or id the install accepts |
| `references/opencode.md`   | `opencode run` — any `provider/model` it can reach      |

Each reference covers one CLI: preconditions, the invocation, how that CLI
expresses effort, isolation, resume, and long-run watching.

Do not load more than the current path needs; load a second only when
switching paths mid-run or comparing mechanisms.

## Invocation Contract

These hold for every CLI, whatever the reference adds:

- **Never invent a capability or identifier.** Model ids, effort levels, flags,
  and sandbox modes come from `--help` or a models listing, not from memory. A
  CLI's model lineup changes without the flags changing; list before assuming.
- **Confirm the mechanism supports the assignment** — model, effort, tools, and
  isolation — before dispatching. If it cannot, pick another path or say so.
- **Effort is per-CLI.** Some expose it as a flag, some as a config override,
  some as a provider-specific variant with no clean mapping. Translate the
  requested level onto what the CLI offers, and tell the caller when there is
  no equivalent instead of silently taking the default.
- **Prompt last, stdin empty.** Pass the packet as the final positional
  argument and redirect `< /dev/null`; piped or absent stdin can stall a CLI
  that is waiting for more input.
- **Match isolation to the job.** Read-only for reasoning over a diff; a
  writable worktree for anything that must run checks. Parallel writers each
  need their own worktree.
- **Artifacts go to a temporary or gitignored directory.** Keep prompts and
  reports out of the working tree; remove or disclose leftovers.
- **Resume by explicit id**, not "the last session", so a concurrent run cannot
  be resumed by accident.
- **Ask for structured output** when the caller parses the result rather than
  reading it.

Cross-CLI usage is invisible to the host's own token budget; track it
separately when a budget matters.

## Wrapping Another Family

Most hosts can only spawn subagents of their own model family. Dispatching to a
different family therefore means a thin wrapper agent: a host-native subagent
whose whole job is to shell out to the other CLI, wait, and return the
artifact.

Keep the wrapper thin: it launches, waits, and returns. The reasoning belongs
in the delegate, not in the process launching it. Use the host's
structured-output option when a parsed result helps.

Label the wrapper with the model that actually does the work, not the CLI and
not the wrapper's own model, so the host UI credits the right one. If a reused
wrapper changes model or role, rename it or disclose the mismatch.

A wrapper's completion only confirms that it launched the delegate. Resume it
after the artifact exists to collect the outcome.

## Watching Long Runs

Launch lengthy runs in the background and watch the captured PID, the output
artifact, and the per-run log described in that CLI's reference. Poll about
once a minute and emit a heartbeat at least every ten minutes. Stop when the
artifact appears or the captured PID exits without one, and report which
condition occurred.

Treat 15 minutes without log growth as a diagnostic signal, not proof of a hang
or a reason to terminate a live process. Before retrying or resuming after a
timeout, inspect the PID, artifact, and log. On Windows, poll the captured PID
with `tasklist`, not `kill -0` or a process-name check.

## Reporting a Dispatch

Name the model and effort that actually ran, not the ones you were asked for —
they differ whenever a fallback engaged. A dispatch that failed to launch is
not a result: fix the invocation rather than reporting its absence as a
finding.
