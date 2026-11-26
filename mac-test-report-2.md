# macOS test report 2: factory preset

Branch `feat/factory-preset` at `b07215e` (after af6528f, d900f86, b07215e). Run 2026-11-26 23:40 to 2026-11-27 00:01 local (+08). Nothing in the repo was changed (`git status -s` shows only the two untracked reports/plan). Scratch: `/private/tmp/claude-501/-Users-nejc/2a01be0b-9185-4b3e-9f96-45ab1adedcbb/scratchpad/verify2/`.

**Overall: pass.** Every previous script bug is fixed except oncue's `run --wait` (upstream, now documented with a working workaround). One new user-facing detection problem (python3, N1) and three minor doc points.

## Environment

Same machine as run 1: macOS 26.6.2 arm64, `/bin/bash` 3.2.57, Homebrew bash 5.3.20, Homebrew python 3.15.2, `/usr/bin/python3` 3.9.6, node v26.13.0, bun, `claude` 2.1.330, coreutils installed (not used by jobs, see 5).
Login PATH (`env -i HOME USER zsh -lic`): `…:/usr/local/bin:…:/usr/bin:/bin:…:/opt/homebrew/bin:…`, so `command -v bash` → `/bin/bash`, `command -v python3` → `/usr/bin/python3`.

## Steps

| Step | Result |
| --- | --- |
| 1 Environment | pass |
| 2 Unit tests | **pass**: automate-factory 247/247, fix-issues 24/24, agent-analytics 40/40 on 3.15 and on `/usr/bin/python3` 3.9 |
| 3 run.sh guards | pass (bash 3.2, python 3.9, no timeout/gtimeout) |
| 4 oncue on launchd | pass; `run --wait` still broken in oncue, documented workaround works |
| 5 End to end, watch | pass, job PATH without `timeout`/`gtimeout` |
| 6 SIGTERM (`kill TERM`, `bootout`) | **pass** both, recorded, no strays, ~1.5 s |
| 7 Cleanup | pass |

### 2. Unit tests

```
$ PATH=/opt/homebrew/bin:$PATH python3 -m unittest discover -s presets/factory/skills/automate-factory/tests   # bash 5.3, py 3.15
Ran 247 tests in 412.144s
OK                                                                              exit 0
$ … python3 -B -m unittest discover -s presets/factory/skills/fix-issues/tests
Ran 24 tests … OK                                                               exit 0
$ … python3 -B -m unittest discover -s presets/factory/skills/agent-analytics/tests          # 3.15
Ran 40 tests … OK                                                               exit 0
$ /usr/bin/python3 -B -m unittest discover -s presets/factory/skills/agent-analytics/tests   # 3.9.6
Ran 40 tests … OK                                                               exit 0
```

- `TMPDIR=/var/folders/…` (symlinked) and `test_symlinked_repo_alias_is_in_scope` passes: bug 6 fixed.
- Every `automate-factory/tests/*.py` compiles under `/usr/bin/python3` 3.9 (the old `test_run.py:735` f-string is gone). No `/usr/bin/timeout`, `/usr/bin/mkdir`, multi-name `printenv`, `pkill -s` or `pkill -f` left in the tests.
- `bash -n run.sh`, `bash -n issue-pipeline.sh`: exit 0.
- The full automate-factory suite was not run under `/usr/bin/python3`: `run.sh` itself requires 3.11 (option B of the plan was taken), so it would only exercise the guard.

### 3. run.sh guards

Scratch repo, script at `.factory/automations/t.sh` (copy of `assets/run.sh`).

```
3a $ /bin/bash .factory/automations/t.sh
   needs bash 4 or later: set the job spec's <bash> to one (macOS: brew install bash) and reinstall the job     exit 1
3b $ PATH=<bash5 only>:/usr/bin:/bin bash t.sh            # python3 = /usr/bin/python3 3.9.6
   needs python3 3.11 or later (macOS: brew install python)                                                   exit 1
3c $ PATH=<bash5 + py3.15>:/usr/bin:/bin bash t.sh        # command -v timeout gtimeout: none
   gate: weekly budget <weekly usd> is not empty or a number of USD                                           exit 1   (past both guards)
```

The run 1 guard "needs GNU timeout or gtimeout" no longer exists; 3c proves a missing `timeout` no longer blocks.

### 4. oncue on launchd

Bash detection per SKILL.md step 1 under the login PATH:

```
$ bash -c 'type -ap bash'; then /opt/homebrew/bin/bash, /usr/local/bin/bash
/bin/bash -> 3   /opt/homebrew/bin/bash -> 5   (first ≥4: /opt/homebrew/bin/bash → <bash>)
```

```
$ oncue render spec.json                    # command ["/opt/homebrew/bin/bash", probe.sh], interval 2
<key>ProgramArguments</key><array><string>/opt/homebrew/bin/bash</string><string>…/probe.sh</string></array>
<key>StartCalendarInterval</key> Minute 0,2,…,58                               exit 0
$ oncue render spec-timeout.json            # "timeout":30
oncue: UNSUPPORTED: launchd: timeout is not supported                          exit 2
$ PATH=<login> oncue install spec.json --capture-path gh,git,python3
installed                                                                      exit 0
   PATH = /opt/homebrew/bin:/usr/bin:/usr/local/bin:/bin
$ oncue list factory-mactest
probe                                                                          exit 0
$ oncue run factory-mactest probe --wait    # fresh job
oncue: COMMAND_FAILED: gui/501/factory-mactest.probe: launchctl print reports no exit code   exit 4, took 0s
```

- Bug 1 still present (oncue upstream, plan step 6). runners.md now documents it.
- Documented workaround (`run` without `--wait`, poll `launchctl print` until `runs` rises and `state = not running`), scripted in `verify2/runpoll.sh`, on a manual probe with `sleep 3; exit 3`: `started`, `runs 0->1, last exit code = 3, took 3s`. It works.
- Probe log in the job: `BASH=/opt/homebrew/bin/bash 5.3.20`, `python3 = /opt/homebrew/bin/python3 3.15.2`.
- Interval: fires at 23:42:04 and 23:44:05 (on the clock), matching the new runners.md line. A 7-minute interval renders `StartInterval 420` ("any other interval counts from install"): matches.
- `oncue status factory-mactest probe` → `probe: inactive, last exit 0` (it was a manual copy at that point), exit 0.

### 5. End to end (`failed-ci-triage`, watch, report)

- Clone of `nejcm/factory-mactest` in scratch. Profile hand-written as in run 1 (same shortcut). `run.sh` filled with the catalog's two blocks: `trigger=watch`, `daily_cap=6`, no window, `workflows=("CI")`, `claude:default`, `report`, `minutes=10`, `notify=(/opt/homebrew/bin/bash verify2/notify.sh)` (appends to `verify2/notify.out`).
- Namespace `factory-factory-mactest-84de74` (30 chars). The hash is the same from `/sbin/sha256sum` and `shasum -a 256`.
- `oncue list factory-factory-mactest-84de74` exit 0. The job spec `command` is `["/opt/homebrew/bin/bash", "<repo>/.factory/automations/failed-ci-triage.sh"]` with no `timeout`, and the rendered plist `ProgramArguments` matches.
- **Job PATH without `timeout`/`gtimeout`.** oncue on macOS always appends `/opt/homebrew/bin` (N2). Even `PATH=/usr/bin:/bin oncue install … --capture-path git` gives `/usr/bin:/opt/homebrew/bin:/usr/local/bin:/bin`, with node or bun. So `--capture-path` cannot produce a coreutils-free PATH here. For steps 5 and 6 the spec's `env.PATH` was set to `verify2/jobbin:~/.local/bin:/usr/bin:/bin`, where `jobbin` holds symlinks to Homebrew `gh` and `python3` only, and installed without `--capture-path`. Plist `EnvironmentVariables` shows that PATH, and `PATH=<it> command -v timeout gtimeout` finds nothing (the probe run under it logged `timeout/gtimeout: none`).
- I pushed `7a68e39` ("test: make CI green", removed `FAIL`) first, so the old failures (A, B) get settled.

Smoke run (manual copy on stdin, then the polling workaround):

```
FACTORY_CHECK_MODELS=1: installed; started; runs 0->1, last exit code = 0, took 3s
   log "check: claude:default answered"; runs.jsonl completed, exit 0, dry_run true, calls 1
FACTORY_DRY_RUN=1:      installed; started; runs 0->1, last exit code = 0, took 22s
   report 2026-11-26-b5a66ba7b2e0.md (latest failed SHA in 30 days); runs.jsonl completed, exit 0, dry_run true, calls 1, events ['45829549696']
$ oncue install - < live.json      # interval 2, env PATH
installed                                                                      exit 0
```

(A first check run, under a PATH that still had `/opt/homebrew/bin`, also passed. I re-ran it under the coreutils-free PATH, shown above.)

Live watch job:
- 23:48 tick: exit 0. `seen.tsv` got `45828559432 done` and `45829549696 done` (a later success on main), with no fire, record or report. 23:50 tick: exit 0, `runs.jsonl` stayed at 3 lines, log at 62 bytes. Pass.
- I pushed `7d992cd` ("test: make CI fail (C)"), and CI run 45853003495 failed. The 23:52 tick fired once:
  - report `2026-11-26-7d992cd15059.md`: regression, cites `repo/ci.sh:2` and `repo/FAIL:1`;
  - `runs.jsonl`: completed, exit 0, calls 1, trigger watch, events ['45853003495'], cost 0.063;
  - `seen.tsv`: `failed` then `done`;
  - notify: `23:52:28 failed-ci-triage: 7d992cd15059 completed`.
- 23:54 tick: no refire (`runs.jsonl` 4 lines, 3 files in the report dir). Lock file empty. Pass.
- `git status --short` in the clone: empty (`.factory/` in `.git/info/exclude`).

### 6. SIGTERM through launchd

I pushed `24ec4b0` ("test: make CI fail (D)"), and CI run 45853643257 failed. `verify2/sigtest.sh` waited for the `timeout 10m claude` shim and its `claude -p` child, captured the job's process tree, sent the signal, then polled each PID.

**6a `launchctl kill TERM`** at 23:56:12, during `claude -p`:

```
tree: run.sh 35246, subshells 35438/35439 (pgid 35438), head 35440, timeout shim 35441, claude 35443 (own pgid)
launchctl kill exit=0
gone: 35438 0.02s, 35439 0.03s, 35440 0.05s, shim 1.21s, claude 1.24s, run.sh 1.39s; strays: none
launchctl print: last exit code = 143
runs.jsonl: outcome failed, exit_code 143, calls 0, cost 0, events ['45853643257']
seen.tsv:   45853643257 failed (no done); lock: empty; .factory/tmp: no view dir
notify:     23:56:13 failed-ci-triage: 24ec4b0e17ec failed
```

**6b `launchctl bootout`** at 23:58:11, during the retry fire's `claude -p`:

```
tree: run.sh 38514, subshells 38696/38699, head 38700, shim 38701, claude 38705 (own pgid)
launchctl bootout exit=0
gone: 38696 0.02s, 38699 0.03s, 38700 0.05s, shim 1.36s, claude 1.38s, run.sh 1.53s  (< launchd exit timeout 5s); strays: none
runs.jsonl: outcome failed, exit_code 143, calls 0, events ['45853643257']
seen.tsv:   second failed line; lock: empty; view dir removed
notify:     23:58:13 failed-ci-triage: 24ec4b0e17ec failed
```

Recovery: I reinstalled the job (`installed`). The 00:00 tick, the third attempt, completed: report `2026-11-27-24ec4b0e17ec.md`, `seen` became `done`, calls 1, notify `00:00:27 … completed`. No `took over` line was needed this time because the lock had been released.

### 7. Cleanup

```
$ oncue uninstall factory-factory-mactest-84de74 failed-ci-triage   removed        exit 0
$ oncue uninstall factory-mactest probe                             not installed  exit 0 (removed earlier: "removed")
$ oncue uninstall factory-mactest probe2                            not installed  exit 0 (bun check job, removed earlier)
$ ls ~/Library/LaunchAgents | grep -i factory                       (nothing)      exit 1
$ launchctl list | grep -i factory                                  (nothing)      exit 1
$ pgrep -fl verify2/                                                (nothing)      exit 1
```

`nejcm/factory-mactest` main is red again (`FAIL` = "FAIL D", head `24ec4b0`), as expected. I left the scratch dir in place.

## Previous bugs

| # | Status | Evidence |
| --- | --- | --- |
| 1 `run --wait` on launchd | **still present** (oncue upstream; plan step 6) | `exit 4, took 0s` on a fresh job. The doc workaround verified (step 4). |
| 2 bootout: no record, orphaned model call | **fixed** | 6b: exit 143 recorded, notify, lock released, no strays, 1.53 s |
| 2b finished call after TERM not counted | **not retestable as such** | the call is now killed in ~1.3 s, so it never finishes. `calls 0, cost 0` records nothing for the killed call's partial usage. |
| 3 `wc -w` padding | **fixed** | `issue-pipeline.sh:296` `-eq 3`; `test_pipeline` passes |
| 4 BSD `paste -s` empty | **fixed** | `maintain-verification.md:50` `${f:-none}`; `test_triggers` passes |
| 5 captured PATH reaches Homebrew bash by accident | **fixed** | `command` `[<bash>, script]`; the job ran `/opt/homebrew/bin/bash` with no Homebrew dir on PATH |
| 6 `repo_roots` symlinked parent | **fixed** | test passes with `TMPDIR=/var/folders/…`, 3.9 and 3.15 |
| test-only (f-string, `/usr/bin` stubs, `printenv`, `pkill`) | **fixed** | 247/247; all test files compile on 3.9 |

## Previous doc mismatches

| # | Status |
| --- | --- |
| 1 SKILL.md bash detection | **fixed**: the step 1 probe finds `/opt/homebrew/bin/bash` under the login PATH. The same pattern remains for python3 (N1). |
| 2 runners.md `--wait` | **fixed** in the doc: launchd caveat and polling recipe, verified |
| 3 bootout recorded as failed 143 | **fixed** (6b) |
| 4 capture `bash`/`timeout` last | **fixed**: no longer needed. The doc now says to list `/usr/bin`/`/bin` tools last. |
| 5 `shasum` note | **fixed**: "where `sha256sum` is missing, as on older macOS" matches (`/sbin/sha256sum` present, same hash) |
| 6 interval on launchd | **fixed**: the new line matches (2 → calendar, 7 → `StartInterval 420`) |
| 7 `gtimeout` vs `timeout` | **fixed**: jobs need neither (python3 `timeout()` shim, 5 and 6 ran with neither on PATH) |
| 8 Python version unstated | **fixed**: run.sh, SKILL.md, README and setup-factory say 3.11; agent-analytics says 3.9+, which is verified |

## New docs checked

- **macOS install line** (README, setup-factory): `brew install bash python gh node` plus a model CLI matches what jobs actually used: Homebrew bash, python 3.15 and gh; node only for oncue. See N3 for coreutils.
- **Bash detection** (SKILL.md step 1, setup-factory table): matches (step 4).
- **node/bun scope**: the job's plist runs `/opt/homebrew/bin/bash` and the job PATH in 5 and 6 had no node or bun. Install and uninstall worked with node and with bun. Matches.
- **run.sh:6 guard message**: matches 3a.

## New findings

- **N1, user-facing, detection only: `python3` detection uses the first `python3` on PATH.**
  - SKILL.md step 1 says "`python3` 3.11 or later". setup-factory's check is `python3 -c 'import sys; print(sys.version)'`.
  - Under this Mac's login PATH, with `/usr/bin` before `/opt/homebrew/bin` and Homebrew python 3.15 installed: `python3 -c …` → `3.9.6`, and `which -a python3` → `/usr/bin/python3 /opt/homebrew/bin/python3`.
  - So setup-factory reports python too old, and step 1 records no python 3.11, even though the job itself gets Homebrew python. On this machine the job PATH resolved Homebrew python3 3.15, because oncue appends `/opt/homebrew/bin` and `gh` lives there.
  - It's the same shape as run 1's doc mismatch 1, fixed for bash but not for python3.
  - Suggested: probe `type -ap python3` (then `/opt/homebrew/bin/python3`, `/usr/local/bin/python3`) for one at 3.11 or later, as for bash.
- **N2, doc: the oncue PATH suffix on macOS.**
  - runners.md:96–98 says `--capture-path` adds the tools' dirs "then `/usr/local/bin:/usr/bin:/bin`".
  - On this Mac, oncue also adds `/opt/homebrew/bin`. `PATH=/usr/bin:/bin oncue install … --capture-path git` gives `/usr/bin:/opt/homebrew/bin:/usr/local/bin:/bin`, the same with node or bun.
  - Harmless, and it rescues N1 at job time, but the doc is inaccurate. It also means a captured job PATH always contains coreutils' `timeout`/`gtimeout` when coreutils is installed, which is irrelevant now since `run.sh` shadows `timeout` with a shell function.
- **N3, doc, minor: the one-line install omits `coreutils`.**
  - setup-factory's table and `fix-issues/SKILL.md:127` still need `timeout`/`gtimeout` for interactive `fix-issues`.
  - README and setup-factory's "On macOS" line (`brew install bash python gh node`) don't mention it, so interactive `fix-issues` on a fresh Mac lacks `timeout`.
  - The table row does say so; consider "add `coreutils` for interactive fix-issues" on the install line.

## Not run

- `setup-factory` itself (I ran its compat-check commands by hand), other CLIs, `comment`/`draft-pr`/`pr`, `issue-pipeline`, change triggers, `daily_cap`/`given-up`, and logged-out behaviour: same scope as run 1.
- The full automate-factory suite under `/usr/bin/python3`: `run.sh` requires 3.11 by design.
- Doc-literal `--capture-path` for the live job: replaced by `env.PATH` to meet the "no gtimeout on the job PATH" criterion, because oncue always adds `/opt/homebrew/bin` (N2).
