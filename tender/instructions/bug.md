Run this ticket with the `orchestration` skill: load it, and `model-dispatch` before the first delegated
call. Its "Local or Delegated" rule picks the pattern: a small ticket with a clear spec you build
yourself; anything else follows its staged implementation. Either way, these hold for an unattended run:

- The rules above and the protocol below override the skill. The protocol is your approval to commit,
  push and open the PR; never merge.
- Plan questions are never asked in this session: write them to the question file and stop. A plan with
  no open questions is approved; do not wait for anyone.
- Keep the plan and every report in `.tender/run/` (git ignores it). Record the plan's phases in the
  phases file.
- Review and fix rounds stop when no confirmed findings remain, or after 2 rounds; list what is still
  open in the PR body.

Steps:

1. Clarify. Read the ticket and the code it touches first: do not ask what the code, its tests or its
   docs already answer. If the acceptance criteria are missing or ambiguous in a way that changes what
   you would build, write your questions to the question file and stop.
2. Plan. Scope, success criteria, checks and phases, per the skill.
3. Build. Read the code before changing it, find every caller, test, fixture, config and doc the change
   must reach, and follow the patterns already there. Reproduce the bug first with a test that fails for
   the reported reason, then fix the root cause and keep the test as a regression test. Make the smallest
   change that fully solves the ticket: no refactors, options or abstractions it did not ask for, no
   comments or docstrings on code you did not change. Add or update tests in the existing style, then run
   {{verify}} and make them pass. Fix the code, not the tests: never skip, weaken or delete a test, or
   hard-code values to pass one.
4. Review and fix. A reviewer of another model family, chosen by the skill's review routing, reviews the
   diff against the ticket; fix only the findings you confirm against the code. If no such reviewer is
   available, say so and set `reviewed` to `false` in the merge file.
5. Verify on the real surface (CLI, API, UI). If the repo has a verification skill
   (`.agents/skills/verify-*/`, or `.claude/skills/verify-*/`), follow it; you may start the app on the
   `TENDER_PORT_*` ports, present only when the repo's type declares `needs`. Proof goes under
   `.tender/proof/` and is never committed. For the PR body, note what you ran and what you saw: the
   command and its output, not "it works". If you could not verify beyond the tests, say so. A failure
   goes back to step 3, then 4 for the fix.
6. Commit with a message that references {{id}}, in the style `git log` already uses, and only the files
   the change needs: no build output, temp files, `.tender/run/` or `.tender/proof/`.
