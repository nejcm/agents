# Daily test coverage

- **Trigger**: daily, 06:00 on weekdays.
- **Requires**: a coverage report uploaded as a CI artifact on the default branch (profile's `CI`
  or `Baselines`); without one the entry is unavailable, since running the suite here would
  execute code outside the view.
- **Runners**: local, GitHub Actions.
- **Input**: the latest default-branch coverage artifact and the paths changed in the last day.
  Trusted: the repo's own CI output and tracked files.
- **Writes**: report to `.factory/reports/daily-test-coverage/<date>.md` or the job summary.
- **Steps**: fetch, read-only:

  ```bash
  fetch() {
    local id
    id=$(gh run list --branch <base> --workflow <workflow> --status success --limit 1 \
      --json databaseId --jq '.[0].databaseId')
    gh run download "$id" --name <coverage-artifact> --dir "$view/input/coverage"
    git log "$ref" --since=yesterday --format=%H --name-only > "$view/input/changes.txt"
  }
  ```

- **Choices**: workflow and artifact name.

## Prompt

```text
From the coverage report in input/coverage/ and the paths changed in input/changes.txt, list
changed code in repo/ with no test covering it, riskiest first, with file and lines, and for each a
one-line test idea that needs no mock of the unit under test. Change nothing.
```

## Follow-up (attended)

The user picks a gap and asks their harness to write that test and open a draft PR.
