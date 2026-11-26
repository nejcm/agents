---
name: fix-issues
description: Use when the user asks to triage, reproduce or fix issues from a repo's tracker or a factory triage report (issue-pipeline, new-error-triage), on a repo set up with setup-factory
category: workflow
disable-model-invocation: true
---

# Fix issues

Take reported issues from triage to a proven fix in separate stages: triage, reproduce, fix,
verify. Each stage is its own agent with only the capability it needs. This session is the
coordinator: it fetches, dispatches, gates, commits, and is the only one that writes to the
tracker or GitHub. Run from the target repo's root, attended: the user writes each repro spec and
confirms every external write.

Invoking this skill is approval, for the issues the user names, to create directories under
`.factory/reports/fix-issues/` and local commit objects. Pushing, opening or updating a draft PR,
filing a ticket and commenting each need the user's confirmation at that step. Never merge, deploy,
force-push or close an issue.

Needs `.factory/profile.md` with `Run` and `Verification` sections (`setup-factory`). Without
them, say which phase to run and stop. Never run from a schedule: the scheduled path is
`automate-factory`'s `issue-pipeline` at `draft-pr`, which runs these stages unattended for
trusted sources; what differs there, and its ledger rows, are in its
[catalog entry](../automate-factory/references/catalog/issue-pipeline.md#state-draft-pr). This
skill is the attended follow-up for its reports and `new-error-triage`'s.

## Sources

Any issue or error source with a `Fetch` line in the profile's `Integrations`: GitHub Issues
through `gh`, the rest through [agent fetch](references/triage.md#agent-fetch), as
`<prefix>-<id>` items keyed by the source's own ID. A source without a `Fetch` line: say so and
stop. Writes go to GitHub through `gh`, and to a source with `Write` lines through its
[write back](references/triage.md#write-back); a write the profile does not record is skipped.

## Stages

| Stage | Role (`model-orchestration`) | Reads | Capability |
| ----- | ---- | ----- | ---------- |
| fetch | none, or [agent fetch](references/triage.md#agent-fetch) | tracker, `git` | read-only calls into the view |
| triage | Reviewer/Judge, `medium` | the view | file read and search only; report on stdout |
| reproduce | Verifier | user's spec, base export | shell; its directory is discarded |
| fix | Builder | user's spec, repro record, patch checkout | shell and edits; the coordinator commits them |
| verify | Verifier, fresh session | user's spec, repro record, base and commit exports | as reproduce |
| post | none (coordinator), or an [agent write](references/triage.md#write-back) | stage files, sent unchanged | one fixed destination per write |

Untrusted text (issue and comment bodies, error payloads, PR text from other authors) reaches the
triage stage only, which runs the isolated analyze command from automate-factory
[`safety.md`](../automate-factory/references/safety.md#steps) and follows its lethal-trifecta
rule. The coordinator holds credentials, so it reads no model prose at all: triage and stage
results reach it only as projected enum lines, and the user reads the reports and evidence.

## Steps

1. **Freeze** before any fetch, each value checked by the regex shown and never taken from stage
   output:
   - `repo=$(gh repo view --json nameWithOwner --jq .nameWithOwner)`, `^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$`
   - `remote_url`: `git remote get-url --push <name>` of the remote whose push URL is `$repo` on
     github.com (`git remote -v`); fetches and pushes use this URL, never a remote name
   - `base=$(gh repo view --json defaultBranchRef --jq .defaultBranchRef.name)`, then
     `git fetch "$remote_url" "$base"` and `base_sha=$(git rev-parse FETCH_HEAD)`
   - `me=$(gh api user --jq .login)`
   - the item IDs the user names: issue numbers, or `<prefix>-<id>` (`err-<source>-<id>` for
     error groups) as `check_items.py` named their files.
2. **Triage**: per [`references/triage.md`](references/triage.md), or start from a scheduled
   report's verdict lines, still building the view before any agent fetch or write back. Show the
   user the projected verdict table and the report path.
3. **Ticket**, for an `err-` item with verdict `new-bug` the user approves: per
   [Writes](#writes), then continue under the new issue number, or `<prefix>-<id>` of a ticket
   in another tracker. No other verdict files a ticket.
4. **Claim** each item the user continues with, per [Claims](#claims).
5. **Spec**: the user writes the repro spec in their own words: feature (a file in the verify
   skill's feature map), preconditions and data, steps, expected final state, broken final state.
   Save it verbatim to `$item/spec.md`. This is the only issue description a later stage sees.
   An item with no mapped feature stays `blocked`; offer pstack
   `maintain-verification-skill` for the missing feature. This work's own draft PR resumes the
   fix; otherwise verdict `fixed` goes to verify mode in
   [`references/reproduce.md`](references/reproduce.md#verify-an-existing-fix); never author over
   an existing fix.
6. **Reproduce**: [`references/reproduce.md`](references/reproduce.md). No confirmed
   reproduction, no fix.
7. **Fix and verify**: [`references/fix.md`](references/fix.md).
8. **Post** per [Writes](#writes). Move whatever of `$item/spec.md` and `$item/evidence` this run
   produced into `.factory/reports/fix-issues/items/<id>/`, keyed by item so any later retry
   finds it, and append a dated model-free entry to its `summary.md`: projected outcomes, tested
   SHAs, PR URL. Then release the claim. A stop after the claim does the same.

## Dispatch

Role, model and effort per `model-orchestration`; invocation per `model-dispatch`'s Claude CLI
reference. v1 runs every shell stage with Claude Code as a standalone process: a native subagent
would inherit this session's tools, permissions and context. Other CLIs are later.

```bash
item=$PWD/.factory/reports/fix-issues/tmp/fix-<id>  # absolute: the stage runs in $dir
check=$item/check/<stage> evidence=$item/evidence/<stage>
mkdir -p "$check" "$evidence"
git archive "<baseline sha>" .cursor/skills/verify-<app> | tar -x -C "$check"
cp <stage inputs> "$check/"
printf '%s\n' 'No git commit or git push, no gh, no tracker or chat writes, no edits outside the working directory and $evidence.' \
  'The reference above also covers the coordinator and other stages: do only the part for the stage named on the last line.' \
  > "$item/bans.md"
prompt="$(cat <reference file> "$item/bans.md"; echo "<the stage's record from Records>")
Stage: <stage>."
(unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_OAUTH_TOKEN ANTHROPIC_PROFILE \
  ANTHROPIC_FEDERATION_RULE_ID ANTHROPIC_ORGANIZATION_ID ANTHROPIC_BASE_URL ANTHROPIC_CUSTOM_HEADERS \
  CLAUDE_CODE_USE_BEDROCK CLAUDE_CODE_USE_VERTEX CLAUDE_CODE_USE_FOUNDRY CLAUDE_CODE_USE_MANTLE \
  CLAUDE_CODE_USE_ANTHROPIC_AWS CLAUDE_CODE_USE_ANTHROPIC_GOOGLE_CLOUD
cd "$dir" && check=$check evidence=$evidence timeout <stage minutes>m claude -p --model <model> \
  --effort <effort> --safe-mode --setting-sources '' --strict-mcp-config --no-session-persistence \
  --tools "<stage tools>" --allowedTools "<stage tools>" --max-turns <stage turns> \
  --permission-mode dontAsk "$prompt" < /dev/null)
```

- **Environment**: stages run in their directory under the user's normal `claude` subscription
  login. Isolation is the environment's job, recorded in the profile's `Environment`; see
  automate-factory [`safety.md`](../automate-factory/references/safety.md#lethal-trifecta-rule).
  `--setting-sources ''` skips user, project and local settings, so a tracked `apiKeyHelper` or
  `env` cannot switch auth; stages need none of them. Stages run as the user: they can change Git
  config and `PATH` and read the `gh` login, so bans and the coordinator split stop a wrong model,
  not an injected one; the isolated environment with a single-repo token bounds that.
- **Prerequisites**: `claude` logged in and no managed
  hooks, confirmed as in automate-factory
  [`runners.md`](../automate-factory/references/runners.md#analyze-command). Missing either: stop
  after triage.
- **Budget**: per stage from the profile's per-run caps (default 30 minutes, 200 turns):
  `timeout` and `--max-turns`.
- **Model tools**: reproduce and verify get `Bash,Read,Grep,Glob`; fix adds `Edit,Write`.
- **Inputs**: the coordinator copies each stage's inputs (its reference's Inputs list) into
  `$check` model-free, with the verify skill from the stage's baseline commit; the stage reads
  journeys only from there. The prompt is the reference file, then `bans.md`, which the
  coordinator writes with the two lines above, then the stage's record from [Records](#records),
  then `Stage: <stage>.` (`reproduce`, `fix` or `verify`).
- Stage reports end with one projected line ([Records](#records)); the coordinator reads only that
  line, and an invalid or missing one is `blocked`. An `escalated: <reason>` line
  ([escalate](references/reproduce.md#escalate)) ends the item: show the user the record; posting
  it is a Comment step.

### Records

The stage prompt states the record, so a stage run from another skill gets the same contract;
the references say only what goes in it. Triage's verdict line is in its
[Analyze](references/triage.md#analyze) prompt.

- reproduce: `$evidence/repro.md`, last line `repro: outcome=<reproduced|not-reproduced|blocked>`.
- fix: `$evidence/fix.md`, last line `fix: outcome=<changed|stopped>`.
- verify (both modes): `$evidence/verify.md`, last line
  `verify: outcome=<confirmed|insufficient|inconclusive>`.
- Any stage: `escalated: <credentials|prod-access|ambiguous|out-of-scope>` in place of the outcome
  line ([escalate](references/reproduce.md#escalate)).

## Claims

Work is keyed by the item ID, so a retry finds the same work:

- The claim is `mkdir "$item"`, with `item=.factory/reports/fix-issues/tmp/fix-<id>` (made
  absolute), only after the ignore check in [Rules](#rules) passes. If it exists,
  another run holds it or crashed: report the path and stop; the user releases it (below) to
  start over.
- This work's own draft PR, projected to fields checked as data:

  ```bash
  gh pr list --repo "$repo" --head "factory/fix-<id>" --state open \
    --json number,isDraft,author,baseRefName,headRepository,headRefOid,closingIssuesReferences \
    --jq ".[] | select(.isDraft and .author.login == \"$me\" and .baseRefName == \"$base\"
      and .headRepository.nameWithOwner == \"$repo\"
      and any(.closingIssuesReferences[]; .number == <id>)) | \"\(.number) \(.headRefOid)\""
  ```

  For a `<prefix>-<id>` item, drop the `closingIssuesReferences` clause; the branch name matches.

  A match is resumed: the fix starts from its head (`git fetch "$remote_url" "refs/pull/<n>/head"`,
  checked against `headRefOid`) and the PR is updated, never a second one opened. Any other PR on
  that branch name: report it and stop. `factory/fix-<id>` on `$remote_url` (`git ls-remote`)
  without a draft: when its SHA is this item's last line in
  `.factory/reports/fix-issues/pushed.tsv`, resume at Draft PR with that commit, the body built
  from `.factory/reports/fix-issues/items/<id>/` (its `spec.md` and stage records); otherwise
  report it and stop. When that last line is tagged `issue-pipeline` and `linked.tsv` has no row
  for the item, report it and stop: the next scheduled run opens its PR and comments.
- Release: `git -c core.hooksPath=/dev/null -c core.fsmonitor=false worktree remove --force "$item/patch"`,
  then remove `$item`, after the report is written.

## Writes

Only the coordinator writes, after showing the command and the file it sends and getting a yes.
Destinations come from step 1 or the profile; bodies are files sent unchanged with `--body-file` or
on stdin; titles are built from projected fields only.

- **Ticket**, into the tracker with a `ticket` `Write` line per
  [write back](references/triage.md#write-back), whose ticket dedupe replaces the marker search
  and gives the new `<prefix>-<id>` for `tickets.tsv`; without one, GitHub as below.
  `<group id>` is the item ID without `err-`, so `<source>-<id>`. First look for one
  already filed for the group, by the local map and by marker:
  `awk -v id="<group id>" '$1 == id' .factory/reports/fix-issues/tickets.tsv` and
  `gh issue list --repo "$repo" --state all --search "\"fix-issues-error: <group id>\" in:body" --json number --jq '.[].number'`.
  Search splits on `-`, so `calc-zde` also finds `calc-zde-1`: a hit counts only if
  `gh issue view <n> --repo "$repo" --json body --jq .body | tr -d '\r' | grep -qxF "fix-issues-error: <group id>"`.
  Found: continue under that number. Else build the body model-free from the triage section
  (`awk` in [`triage.md`](references/triage.md#projection)) plus the line
  `fix-issues-error: <group id>`, run
  `gh issue create --repo "$repo" --title "Error <group id>: <feature>" --body-file <body>`, and
  at once append `<group id> <number>`, the number ending the printed URL, to
  `.factory/reports/fix-issues/tickets.tsv`. No undo.
- **Push**: `git -c core.hooksPath=/dev/null -c core.fsmonitor=false push "$remote_url" "<commit>:refs/heads/factory/fix-<id>"`,
  never forced; a rejected push is a stop. Then at once append `<id> <commit>` to
  `.factory/reports/fix-issues/pushed.tsv`.
- **Draft PR**: when the profile's `Agent PR review` allows agent PRs. Body model-free:
  `Fixes #<id>` (or `Source item: <prefix>-<id>`), the tested `$before` and `$commit` SHAs, then
  `spec.md` and the stages' `repro.md`, `fix.md` and `verify.md` concatenated. Update the
  claimed PR with `gh pr edit <n> --repo "$repo" --body-file <file>`, else
  `gh pr create --repo "$repo" --draft --base "$base" --head factory/fix-<id> --title "fix: <#id or prefix-id> <feature>" --body-file <file>`.
- **Comment**: at most one per item per run, the file built from the projected outcome, the
  tested SHAs and the PR or artifact URL only. A GitHub issue, after
  `gh issue view <id> --repo "$repo" --json state` shows it open:
  `gh issue comment <id> --repo "$repo" --body-file <file>`. A `<prefix>-<id>` item, through its
  source's `comment` write with the native ID. Triage-only outcomes (duplicate, not a bug, needs
  info) are posted only when the user picks them.
- **Status**: `<prefix>-<id>` items only, after the draft PR is opened, through the source's
  `status` write: the one state recorded at setup, never a closing one.

## Rules

- **Secrets**: never ask for, read, store or write one. A stage that prints one is stopped and its
  files are kept out of every body.
- **Writes**: freely only to `.factory/`. Everything else is a [Writes](#writes) step. Local
  state (claims, specs, evidence, maps) lives under `.factory/reports/fix-issues/`,
  whose own `.gitignore` of `*` makes Git ignore it whatever the repo's rules say. Before the
  first write there, this preflight must pass; on a failure, report it and stop:

  ```bash
  s=.factory/reports/fix-issues
  for p in .factory .factory/reports "$s"; do [ ! -L "$p" ] || exit 1; done
  [ -z "$(find "$s" -path "$s/tmp/fix-*/*" -prune -o -type l -print 2> /dev/null)" ] || exit 1
  for p in pushed linked tickets merges fates; do [ ! -e "$s/$p.tsv" ] || [ -f "$s/$p.tsv" ] || exit 1; done
  [ -z "$(git ls-files -- "$s")" ] || exit 1  # tracked state: the user runs git rm -r --cached
  mkdir -p "$s" && { [ -e "$s/.gitignore" ] || (set -C; printf '*\n' > "$s/.gitignore"); }
  [ "$(cat "$s/.gitignore")" = '*' ] && git check-ignore -q "$item/spec.md"
  ```
- **Loading skills**: the verify skill and `debugging` are read by path inside the stage, never
  invoked; `disable-model-invocation` blocks that.
- **Git after a stage**: coordinator `add`, `commit`, `worktree` and `push` take
  `-c core.hooksPath=/dev/null -c core.fsmonitor=false`, against mistakes only.
- **Retries**: one corrected retry per stage, then stop and report, per `model-orchestration`.
- **Two machines** can both claim an item before its draft PR exists; the second push is
  rejected and stops. Attended v1 accepts that.
