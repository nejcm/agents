---
name: retro
description: Use when the user asks for a retro on recent coding agent sessions, or to find where agents waste time navigating the repo or rely on out-of-date docs.
category: workflow
disable-model-invocation: true
---

Read my last 10 coding agent sessions and find ways to make my repo easier to navigate. Find where agents take too long to find relevant information, or rely on out-of-date docs.

- Transcripts live in `~/.claude/projects/` (Claude Code) and `~/.codex/sessions/` (Codex); match sessions by cwd and skip the current one.
- Strongest signal: the same thing searched for across several sessions, or a user correcting the agent ("it's in X", "that's outdated").
- Verify each finding against the current repo before reporting; drop anything already fixed.
- For each finding, cite the session and give the exact fix (file + change). Prefer correcting stale lines or adding a one-line pointer to `AGENTS.md` over writing new docs.
- Report only; apply fixes when asked.
