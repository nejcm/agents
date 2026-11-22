Run this ticket with the `orchestration` skill: load it, and `model-dispatch` before the first delegated
call. A docs change is built in this session; only the review is delegated. These hold for an
unattended run:

- The rules above and the protocol below override the skill. The protocol is your approval to commit,
  push and open the PR; never merge.
- Questions are never asked in this session: write them to the question file and stop.
- Keep every report in `.tender/run/` (git ignores it).
- Review and fix rounds stop when no confirmed findings remain, or after 2 rounds; list what is still
  open in the PR body.

Steps:

1. Clarify. Read the ticket and the docs and code it touches first: do not ask what they already answer.
   If the acceptance criteria are missing or ambiguous in a way that changes what you would write, write
   your questions to the question file and stop.
2. Write the docs change. Change docs only: if the code is wrong, list it in the findings file. Every
   statement matches what the code does. Match the existing tone, structure and formatting, and add no
   sections, examples or caveats the ticket did not ask for.
3. Check. Add no tests. Run {{verify}} and make them pass. Check every command, snippet and link you
   changed: run a command only if it is read-only and safe in this clone, never one that deploys,
   publishes, migrates or deletes data; check the rest against the code. Note what you ran for the PR
   body.
4. Review and fix. A reviewer of another model family, chosen by the skill's review routing, reviews the
   diff against the ticket and the code it describes; fix only the findings you confirm. If no such
   reviewer is available, say so and set `reviewed` to `false` in the merge file.
5. Commit with a message that references {{id}}, in the style `git log` already uses, and only the files
   the change needs: no temp files or `.tender/run/`.
