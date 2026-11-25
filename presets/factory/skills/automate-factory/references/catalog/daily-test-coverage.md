# Daily test coverage

- **Trigger**: daily, 06:00 on weekdays.
- **Requires**: `gh` logged in; a coverage report uploaded as a CI artifact on the default branch (profile's `CI`
  or `Baselines`); without one the entry is unavailable, since running the suite here would
  execute code outside the view.
- **Runners**: local.
- **Input**: the latest default-branch coverage artifact and the paths changed in the last day.
  Trusted: the repo's own CI output and tracked files.
- **Writes**: report to `.factory/reports/daily-test-coverage/<date>.md`; at `draft-pr` or
  `pr`, new tests as one PR.
- **Write levels**: report, draft-pr and pr. `allow`: test paths only (`tests/*`,
  `*.test.*`, `*_test.go`, the repo's own pattern).
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

## Edit prompt

```text
Read report.md and profile.md. For at most 3 of the riskiest gaps, add tests in the repo's existing
style that pass on the current code and would fail if the covered behaviour broke. Change no
non-test file and no existing test. Run the profile's test recipe. Stop if no gap can be covered
that way.
```

## Follow-up (attended)

At `report`, the user picks a gap and asks their harness to write that test and open a draft PR.
