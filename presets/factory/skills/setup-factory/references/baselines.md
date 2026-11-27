# Phase 6: Repo baselines

Measure once what already exists, so later agent work can be compared against it. No ongoing
tracking. Uses the CI facts in the profile's `Repo` section and, for local timings, the `Run`
section.

## Sources

Use successful first attempts only. Record the event, SHA range and run count behind every
number.

1. **Workflow duration**, sampled per workflow and per event it runs on, since PR runs carry the
   PR's head branch, not the default branch:

   - push: `--event push --branch <default>`
   - pull request: `--event pull_request` (all PR branches; note it when PRs target more than the
     default branch)

   ```bash
   gh run list --workflow <file> <event filter> --status success --limit 20 \
     --json databaseId,headSha,attempt,startedAt,updatedAt \
     --jq '.[] | select(.attempt == 1) | [.databaseId, .headSha[0:7], ((.updatedAt | fromdate) - (.startedAt | fromdate))] | @tsv'
   ```

   Record the median and max seconds and the number of runs, per event. `updatedAt` stands in
   for the end time; the attempt filter drops re-runs, whose `updatedAt` is later.
2. **Build and test step durations**, from named steps of the most recent run above:

   ```bash
   gh run view <run-id> --json jobs \
     --jq '.jobs[] | .name as $job | .steps[] | select(.conclusion == "success") | [$job, .name, ((.completedAt | fromdate) - (.startedAt | fromdate))] | @tsv'
   ```

   Keep the steps whose names say build, test, lint or typecheck, with job and step names as
   written. A step with no telling name is not guessed at.
3. **Bundle size**, only when CI uploads a named artifact with the build output or a size report
   (`actions/upload-artifact` in a workflow file). Take it from a run at a recorded SHA:

   ```bash
   mkdir -p .factory/tmp
   [ -e .factory/tmp/.gitignore ] || echo '*' > .factory/tmp/.gitignore
   dir=$(mktemp -d .factory/tmp/artifact.XXXXXX)
   gh run download <run-id> -n <artifact-name> -D "$dir" \
     && find "$dir" -type f -exec cat {} + | wc -c
   rm -rf "$dir"
   ```

   A failed download is unavailable, not zero.

   Record the artifact name, run id, SHA and total bytes (or the size report's own numbers). An
   expired artifact or none at all is unavailable.
4. **Local build and test time**, only when cheap: the `Run` section works, the command needs no
   services beyond it, and the CI step took under 5 minutes. Run each command once, time it with
   `time`, and record warm or cold cache.

## Rules

- A metric that cannot be measured from these sources is `unavailable: <reason>` (no CI, `gh` not
  logged in, no named step, no artifact, expired). Never estimate from repo size or similar repos.
- Read only run metadata and named artifacts. Do not download logs, and do not trigger or re-run
  workflows.
- When a number looks bad (CI over 10 minutes, one step dominating, a large bundle), say so in
  your reply and point to the `ci-speed` skill for CI or `performance` for bundle and local
  timings. Do not start that work here.

## Output

The profile's `Baselines` section, at the SHA measured: each metric with value, source command or
artifact, run count and SHA range; unavailable ones with the reason.
