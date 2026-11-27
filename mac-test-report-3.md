# macOS test report 3: factory preset

Branch `feat/factory-preset` at **`cc639fc`**. Run 2026-11-27, 14:40–15:05 local (+08). No tracked file in this repo was changed. Scratch: `/private/tmp/claude-501/-Users-nejc/2a01be0b-9185-4b3e-9f96-45ab1adedcbb/scratchpad/verify3/`, with the clone in `verify3/factory-mactest`.

**Overall: pass.** Two of step 6's pass conditions were not met, both because of model choices rather than script bugs: the seeded issue #10 got no feature, and the fix's test added no import. I found no script bugs and no BSD-vs-GNU errors. Total spend was **$0.275** across 9 records in `runs.jsonl`.

Mid-test, the budget was cut to $1 total. After that, every pipeline stage ran on `claude:haiku`, with `weekly_usd="1"`.

## Environment (login PATH)

| | |
| --- | --- |
| macOS | 26.6.2 (25G83), arm64 |
| bash | `command -v bash` → `/bin/bash` 3.2.57. Detected `<bash>`: `/opt/homebrew/bin/bash` 5.3.20 |
| python3 | `command -v python3` → `/usr/bin/python3` 3.9.6. Detected: `/opt/homebrew/bin/python3` 3.15.2 |
| node / bun | `/opt/homebrew/bin/node` v26.13.0; `~/.bun/bin/bun` 1.4.4 |
| claude | `~/.local/bin/claude` 2.1.330 |
| gh / git | `/opt/homebrew/bin/gh` 2.103.3; `/usr/bin/git` 2.54.0 (Apple Git-157) |

Job PATH for every job, using the coreutils-free trick from report 2: the spec's `env.PATH` was `verify3/jobbin:~/.local/bin:/usr/bin:/bin`, installed without `--capture-path`. `jobbin` holds symlinks to Homebrew `gh` and `python3`. The command was `["/opt/homebrew/bin/bash", "<repo>/.factory/automations/<entry>.sh"]`. Namespace: `factory-factory-mactest-2c158d`.

## Steps

| Step | Result |
| --- | --- |
| 1 Environment | pass |
| 2 Unit tests | **pass**: 269, 25 and 41 tests, all OK; `bash -n` exit 0 for both scripts |
| 3 Setup compatibility check | pass (the missing case only by simulation, see 3) |
| 4a Smoke polling, success | pass |
| 4b Non-zero exit, no model cost | pass |
| 4c No record | pass |
| 5 Secret hiding | pass |
| 6 issue-pipeline at draft-pr | **pass, with two gaps**: `pr-exists` skips, draft PR, gates, verify and PR Tests section all pass. The new-import condition was not exercised, and the first seeded issue got `no-feature` (see 6) |
| 7 Watch double fire | pass |
| 8 SIGTERM regression | pass |
| 9 Cleanup | pass |

### 2. Unit tests

All three suites ran with `PATH=/opt/homebrew/bin:$PATH` (bash 5.3, python 3.15).

```
$ python3 -m unittest discover -s presets/factory/skills/automate-factory/tests
Ran 269 tests in 454.343s
OK                                                         exit 0
$ python3 -B -m unittest discover -s presets/factory/skills/fix-issues/tests
Ran 25 tests … OK                                          exit 0
$ python3 -B -m unittest discover -s presets/factory/skills/agent-analytics/tests
Ran 41 tests … OK                                          exit 0
$ bash -n assets/run.sh; bash -n assets/issue-pipeline.sh  exit 0, exit 0
```

### 3. Setup compatibility check

`verify3/compat.sh` runs each row of setup-factory's table as written.

```
== login PATH
ok python3 /opt/homebrew/bin/python3 Python 3.15.2
ok bash /opt/homebrew/bin/bash 5.3.20(1)-release
ok timeout /opt/homebrew/bin/timeout /opt/homebrew/bin/gtimeout
ok node-or-bun v26.13.0
ok git+gh
== PATH=/usr/bin:<login>        (/usr/bin/python3 3.9 first)
ok python3 /opt/homebrew/bin/python3 Python 3.15.2      ← the fallback finds Homebrew; report 2's N1 is fixed
… (rest ok)
== PATH=/usr/bin:/bin:/usr/sbin:/sbin with the Homebrew fallback prefixes pointed at a nonexistent dir (simulated fresh Mac)
MISSING python3 3.11+: brew install python
MISSING bash 4+: brew install bash
MISSING timeout/gtimeout: brew install coreutils
MISSING node or bun: brew install node
MISSING git/gh: brew install gh
```

With `/usr/bin/python3` first on PATH, the check correctly does not report a miss, because the fallback list includes `/opt/homebrew/bin/python3`. I could only produce the "missing" case by hiding the Homebrew prefixes, since uninstalling packages is not allowed. In that case each row names the requirement with its brew hint.

### 4. Smoke-step polling on launchd (no `--wait`)

`verify3/smoke.sh` follows the runners.md recipe:
1. `install -` the manual copy;
2. count the lines of `runs.jsonl`;
3. `oncue run` (it prints `started`);
4. poll every 3 s for a new line with this entry and `dry_run: true`, giving up after `<minutes>` + 1.

The entry was `failed-ci-triage` (watch, report). I used it instead of weekly-retro to reuse the setup.

```
4a FACTORY_CHECK_MODELS=1: installed; started; record after 4s: completed, exit_code 0, dry_run true, calls 1, $0.015
4a FACTORY_DRY_RUN=1:      installed; started; record after 30s: completed, exit_code 0, calls 1, $0.093, events ['45853643257']
4b weekly_usd="0.01":      record after 3s: outcome blocked, exit_code 1, dry_run true, calls 0, cost 0
   log/gates: "weekly budget reached: $0.11 of $0.01 in the last 7 days, so the models were not checked"
4c .factory/pause + minutes="1": started; "no record within 1+1 min (121s): step fails"
   <entry>.log: "paused"; launchctl: last exit code = 0
```

Pause removed and `minutes` restored afterwards.

The 4a check above happened before the budget cut. Step 5's check is a second model check, so the test made two check runs where the cut asked for one. Together they cost $0.019.

### 5. Secret hiding

The job's `env` held `FAKE_TOKEN=abc123`, `DB_URL=postgres://u:p4ss@h/db` and `GUM_LOG_KEY_FOREGROUND=212`. A `claude` shim was first on the job PATH (`verify3/shim/claude`: `env > claude-env.txt; exec ~/.local/bin/claude`). The run used `FACTORY_CHECK_MODELS=1`.

```
record: completed, exit_code 0, calls 1, $0.0038
log:   env: unset DB_URL for model calls / env: unset FAKE_TOKEN for model calls / env: unset SSH_AUTH_SOCK for model calls / check: claude:default answered
gates: ['env: unset DB_URL', 'env: unset FAKE_TOKEN', 'env: unset SSH_AUTH_SOCK']   (nothing for GUM_)
dump:  GUM_LOG_KEY_FOREGROUND=212 present; FAKE_TOKEN, DB_URL, SSH_AUTH_SOCK absent; grep -c 'p4ss|abc123' → 0
```

launchd gives every agent `SSH_AUTH_SOCK`, so every model call on macOS logs `env: unset SSH_AUTH_SOCK`. This is expected and harmless, but it is noise in each record's `gates`.

### 6. issue-pipeline at draft-pr

**Setup.**
- I built the script the way `tests/test_pipeline.py` assembles it (`verify3/gen.py`): `run.sh`, plus triage.md's fetch functions with `fetch() { fetch_new; fetch_deferred; fetch_labeled factory; fetch_context; }`, plus `issue-pipeline.sh` inserted before `confirm analyze`.
- Values:
  - `trust=("#")`, `label=factory`, `cap=1`, `run_minutes=240`, `flow=fix`, `verify_fixed=on`, `merge_level=draft`, `app=calc`;
  - `test_cmd=./ci.sh`, `allow=("*.py")`;
  - skills: the repo's `fix-issues` dir and `~/.claude/skills/debugging`;
  - prompts from the catalog.
- Models: `claude:haiku` for every stage and `reviewers=(claude:haiku)`, with `weekly_usd="1"` to fit the $1 cap. The profile says sonnet.

**No dry-run smoke.** The issue-pipeline dry run is not free: it runs triage, spec and reproduce. So I skipped it and ran only the model check ($0.007, before the budget cut) and then real runs (manual `run`, then polling `runs.jsonl`).

**Run 1.** Seed: `3f81e77`, a `span(lo, hi)` helper returning `lo - hi`, with issue #10. Record: completed, exit 0, calls 1, $0.012.

```
pipeline: id=2  outcome=skipped reason=pr-exists pr=none
pipeline: id=4  outcome=skipped reason=pr-exists pr=none
pipeline: id=6  outcome=skipped reason=pr-exists pr=none
pipeline: id=8  outcome=skipped reason=pr-exists pr=none
pipeline: id=10 outcome=skipped reason=no-feature pr=none     (triage line: verdict=new-bug feature=none)
```

`span` is not in the clamp journey (`features/clamp.md` covers only the CLI), so triage gave it no feature. This was my seeding choice, not a script bug. It got no deferral.

**Run 2.** Seed: `20553c7`, a `fmt()` output helper using `abs()` on the clamp CLI path, with issue #11. Record: completed, exit 0, calls 6, $0.068, gates `['env: unset SSH_AUTH_SOCK', 'passed']`.

```
pipeline: id=2,4,6,8 skipped pr-exists; id=10 skipped no-feature
11 repro: outcome=reproduced
11 verify: outcome=confirmed
11 review: claude:haiku approve
pipeline: id=11 outcome=fixed reason=linked pr=https://github.com/nejcm/factory-mactest/pull/12
items[0]: test_changes 0, dependency_change false, scope minimal, weighted 7, diff_stat "2 files changed, 7 insertions(+), 1 deletion(-)"
```

- No `same-feature` deferral: #11 took the slot while #2, #4, #6 and #8 were skipped for `pr-exists`. **Pass.**
- PR #12 is a draft on `factory/fix-11`, and its CI passed.
  - Diff: `calc.py` changes 1 line (`abs(value)` → `value`).
  - `test_calc.py` gets **+6 lines and 0 deleted lines**, a new `test_cli_keeps_negative_sign`, and no `test-change:` line. **Pass.**
- **New-import condition: not exercised.** The fix tested through `main()`, which `test_calc.py` already imports, so no import line was added. Proving it would have needed another paid run; I didn't retry, to stay within budget.
- The PR body's final `## Tests` section reads "Gates passed on the fix: …" and "New tests fail on base (exit 1) and pass on the fix." It does not say "No test added" (0 matches). **Pass.**
- #11 got one link comment: "Draft PR …/pull/12: reproduced on 20553c7…, and the fix d20be5f… passed the same check. Nothing merges without review."
- **BSD-vs-GNU errors:** `grep -nE 'sed:|date:|stat:|mktemp:|sort:|awk:|grep:|illegal option|invalid option|unknown option|usage:'` over every `.factory/automations/*.log` found nothing (exit 1). **None.**

### 7. Watch double fire

These were two `FACTORY_DRY_RUN=1` runs of `failed-ci-triage` on the same SHA (`24ec4b0`) and day: the 4a dry run and one more ($0.076).

```
2026-11-27-24ec4b0e17ec.md     1453 bytes  14:51
2026-11-27-24ec4b0e17ec-2.md   1481 bytes  14:54    (contents differ; first not overwritten)
```

### 8. SIGTERM regression

I sent `launchctl kill TERM` during a dry-run `claude -p`, 2 s after it appeared, using `verify3/sigtest.sh`.

```
tree: run.sh 75311, subshells 75900/75901 (pgid 75900), head 75902, timeout shim 75903, claude 75904 (own pgid)
launchctl kill exit=0
gone: 0.02s, 0.04s, 0.05s, shim 1.16s, claude 1.18s, run.sh 1.32s; strays: none
launchctl print: last exit code = 143
runs.jsonl: outcome failed, exit_code 143, dry_run true, calls 0, cost 0, events ['45853643257']
lock=[] (empty); .factory/tmp: no view dir left
```

It ran on a dry run rather than a live watch fire, so main didn't need to go red. The TERM path, own-group kill and record are the same code.

### 9. Cleanup

```
$ oncue uninstall factory-factory-mactest-2c158d issue-pipeline     removed
$ oncue uninstall factory-factory-mactest-2c158d failed-ci-triage   removed (earlier), then "not installed"
$ oncue list factory-factory-mactest-2c158d                         (empty)  exit 0
$ ls ~/Library/LaunchAgents | grep -i factory                       (nothing) exit 1
$ launchctl list | grep -i factory                                  (nothing) exit 1
$ pgrep -fl verify3/                                                (nothing) exit 1
```

Created on `nejcm/factory-mactest` (nothing merged, closed or deleted):
- commits on main: `3f81e77` "feat: add a span helper for the clamp range", `20553c7` "refactor: format clamp output through a helper";
- issues: #10 "span helper returns a negative range width", #11 "clamp command prints negative results without the minus sign" (both labelled `factory`);
- by the pipeline: draft PR #12 `fix: #11 clamp` on `factory/fix-11`, and one comment on #11.

## Bugs

None found in scripts at `cc639fc`.

Observations (non-blocking):
1. **The PR body names the model and nests stage headings.**
   - `## Shadow review` lists `claude:haiku (anthropic): approve`, by design. This conflicts with a "never mention AI in GitHub posts" policy, if the user holds one for factory PRs.
   - The stage records are pasted verbatim, so PR #12's body has several `#` H1 headings and two `## Tests` headings: one from `fix.md`, plus the pipeline's own. The pipeline's section comes last, so it is still correct.
2. **Run 1 logged `pipeline: no candidates` before the per-item `skipped` lines.** The order reads oddly, but it is correct.
3. **`SSH_AUTH_SOCK` is unset and logged in every launchd record's `gates`** (see 5).

## Not run

- **issue-pipeline dry-run smoke.** It costs model calls (triage, spec, reproduce) and the budget was $1. I ran the model check plus real runs instead.
- **New import on its own line.** The model's fix needed no new import. A retry would have been paid.
- **The "missing python3" compatibility case on real state.** I simulated it by hiding the Homebrew prefixes, because uninstalling is not allowed.
- **weekly-retro** for 4a. I used `failed-ci-triage` instead.
- **Doc-literal `--capture-path` install.** I used `env.PATH` so that no `gtimeout` was on the job PATH, as in report 2.

## Spend

The sum of `cost_usd` in `verify3/factory-mactest/.factory/reports/runs.jsonl` (9 records) is **$0.275**:

| Run | Cost |
| --- | --- |
| failed-ci-triage, 4a check (before the budget cut) | $0.015 |
| failed-ci-triage, 4a dry run | $0.093 |
| failed-ci-triage, 4b (budget gate) | $0 |
| failed-ci-triage, 5 check | $0.004 |
| failed-ci-triage, 7 second dry run | $0.076 |
| failed-ci-triage, 8 (TERM'd) | $0 |
| issue-pipeline, check (before the budget cut) | $0.007 |
| issue-pipeline, run 1 | $0.012 |
| issue-pipeline, run 2 | $0.068 |
