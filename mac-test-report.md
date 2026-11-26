# macOS test report: factory preset

Branch `feat/factory-preset` at `ba87994`. Run 2026-11-26, 21:05–21:36 local (+08). Nothing in the repo was changed.

## Environment

| | |
| --- | --- |
| macOS | 26.6.2 (25G83), arm64 |
| `/bin/bash` | 3.2.57 |
| Homebrew bash | 5.3.20, installed during the test (`brew install bash coreutils`) |
| timeout | coreutils 9.12 installs **both** `/opt/homebrew/bin/timeout` and `gtimeout` |
| node | v26.13.0 (bun also present) |
| python3 | `/usr/bin/python3` 3.9.6 (first on PATH); Homebrew 3.15.2 |
| gh / git | `gh` logged in as nejcm; `/usr/bin/git` |
| Model CLI | `claude` 2.1.330 (has `--restricted`, `--safe-mode`, `--no-session-persistence`); `codex` and `agent` are also present but weren't used |
| Login PATH | `…:/usr/local/bin:…:/usr/bin:/bin:…:/opt/homebrew/bin:…`, so **`/bin` comes before Homebrew** and `command -v bash` → `/bin/bash` (3.2) |

## Steps

| Step | Result |
| --- | --- |
| 1 Environment | pass (Homebrew bash and coreutils were missing; installed with OK) |
| 2 Unit tests | **fail**: automate-factory won't import on system Python 3.9; on 3.15 + bash 5 it's 236/245 (8 failures, 1 error); fix-issues 24/24; agent-analytics 39/40 |
| 3a bash 3.2 guard | pass |
| 3b no timeout guard | pass |
| 3c gtimeout only | pass |
| 4 oncue on launchd | render, UNSUPPORTED, install, list and interval: pass. **`run --wait`: fail** (bug 1) |
| 5 End to end | pass, except that the smoke run's `run --wait` exits 4 (bug 1) |
| 6 SIGTERM | `launchctl kill TERM`: pass. **`launchctl bootout` during a model call: fail** (bug 2) |
| 7 Cleanup | pass |

### 2. Unit tests

```
$ python3 -m unittest discover -s presets/factory/skills/automate-factory/tests -q     # /usr/bin/python3 3.9.6
  File ".../automate-factory/tests/test_run.py", line 735
    final = f"printf '%s\\n' '{start.replace('{}', '{\"left-pad\": \"1\"}')}' > package.json; echo 2 > src/w"
SyntaxError: f-string expression part cannot include a backslash
Ran 9 tests … FAILED (errors=9)                                                    exit 1
```

With Homebrew `python3` 3.15 but `/bin/bash` first on PATH: `Ran 245 … FAILED (failures=346, errors=17)`, exit 1. Nearly all of these are `needs bash 4 or later`, which is expected. So the tests need bash 4 or later first on PATH.

With `PATH=/opt/homebrew/bin:$PATH` and Python 3.15: `Ran 245 tests in 426s, FAILED (failures=8, errors=1)`, exit 1. Root cause for each:

| Test | Cause | Script bug? |
| --- | --- | --- |
| `test_pipeline` `test_fixed_linked_merged_pr_verifies_and_linked_open_pr_skips`: `('skipped','ambiguous-baseline','none') != ('fixed','linked','none')` | BSD `wc -w` pads its output with spaces (bug 3) | **yes** |
| `test_pipeline` `test_fixed_merged_pr_not_confirmed_comments_and_stops`: `('skipped','ambiguous-baseline') != ('blocked','not-confirmed')` | same | **yes** |
| `test_triggers` `test_maintain_verification_flags_changed_features_until_the_skill_changes`: `'still flagged: none\n' not found in 'report\nstill flagged: \n…'` | BSD `paste -s` prints nothing for empty input (bug 4) | **yes** |
| `test_agy` and `test_cursor` `test_a_stage_timeout_blocks_the_item_and_the_queue_goes_on`: `exec: /usr/bin/timeout: cannot execute` | the test stub hard-codes `/usr/bin/timeout` (`test_agy.py:230`, `test_cursor.py:254`) | test only |
| `test_cursor` `test_an_unwritten_deny_config_fails_the_call_before_it_runs`: `FileNotFoundError …/reports/e` | the stub `exec /usr/bin/mkdir` (`test_cursor.py:149`); macOS has `/bin/mkdir` | test only |
| `test_codex` `test_provider_variables_are_unset_for_their_cli_only`: `'k\n' != 'k\n/g\n'` | BSD `printenv` takes one name only: `A=1 B=2 printenv A B` → `1` | test only |
| `test_watch` `test_a_sigterm_mid_fire_records_a_failure_and_settles_nothing`: `124 != 143` | `pkill -TERM -s <pid>` → `-TERM: illegal option -- s`, because BSD pkill has no `-s`. No signal is sent, so the held stub times out | test only |
| `test_watch` `test_a_kill_mid_fire_counts_an_attempt_and_three_failures_give_up`: `1 != -9` | BSD pkill skips its own ancestors unless given `-a`. The stub (`test_watch.py:21`) is a child of run.sh, so run.sh survives. Checked separately: `pkill-exit=1`, `parent-survived` | test only |

agent-analytics:

```
FAIL: test_symlinked_repo_alias_is_in_scope
AssertionError: '| Sessions | 2 | 1 |' not found in '…| Sessions | 1 | 1 | not found | 2 |…'
```

The cause is that macOS's temp dir `/var/folders/…` is a symlink to `/private/var/…`. `repo_roots(alias)` (`agent_analytics.py:96`) returns `{/var/…/alias, /private/var/…/real}`, so a Claude project dir encoded from `/var/…/real` is never globbed. With `TMPDIR` set to a non-symlinked dir the suite passes (`OK`). This only shows up when the repo's real path itself sits under a symlinked parent. Low impact, but it is a code limitation, not just a test artefact (see bug 6).

`bash -n run.sh` and `bash -n issue-pipeline.sh`: exit 0 for both. The embedded Python blocks in `run.sh` (`record_py`, `ci_py`, `deps_py`) compile under Python 3.9.

GNU-only flags (`date -d`, `sed -i`, `find -printf`, `stat -c`, `readlink -f`, `sha256sum`): none of these caused a failure. `wc` and `paste` did.

### 3. run.sh guards

Run from a scratch repo, with the script at `.factory/automations/t.sh`.

```
3a $ /bin/bash .factory/automations/t.sh
   needs bash 4 or later (macOS: brew install bash)                                exit 1
3b $ PATH=<dir with bash 5 only>:/usr/bin:/bin bash .factory/automations/t.sh
   needs GNU timeout or gtimeout (macOS: brew install coreutils)                   exit 1
3c $ PATH=<dir with bash 5 + gtimeout>:/usr/bin:/bin bash .factory/automations/t.sh
   gate: weekly budget <weekly usd> is not empty or a number of USD                exit 1   (past both guards)
```

### 4. oncue on launchd

```
$ oncue render spec.json
==> /Users/nejc/Library/LaunchAgents/factory-mactest.probe.plist
<key>Label</key><string>factory-mactest.probe</string> …                          exit 0
$ oncue render spec-timeout.json            # "timeout":30 added
oncue: UNSUPPORTED: launchd: timeout is not supported                              exit 2
$ oncue install spec.json --capture-path node,python3,git,gh,bash,gtimeout
installed                                                                          exit 0
   → EnvironmentVariables PATH = /opt/homebrew/bin:/usr/bin:/bin:/usr/local/bin
$ oncue list factory-mactest
probe                                                                              exit 0
$ oncue run factory-mactest probe --wait
oncue: COMMAND_FAILED: gui/501/factory-mactest.probe: launchctl print reports no exit code   exit 4
$ cat probe.log      # the run itself did happen
ok Thu Nov 26 21:11:38 +08 2026
PATH=/opt/homebrew/bin:/usr/bin:/bin:/usr/local/bin
GNU bash, version 5.3.20(1)-release (aarch64-apple-darwin25.6.0)
/opt/homebrew/bin/bash
```

- The logged PATH has Homebrew before `/usr/bin`, and `bash` inside the job is 5.3: pass. That holds for this tool list only; see bug 5.
- Interval (`{"kind":"interval","minutes":2}`): oncue renders it as `StartCalendarInterval` with Minute 0, 2, …, 58, so it fires on even wall-clock minutes, not every 2 minutes from install. It fired unprompted at 21:14:04 and 21:16:05. `oncue status factory-mactest probe` → `probe: active, last exit 0`.
- Label format: `<namespace>.<name>`, e.g. `factory-mactest.probe`. The plist is `~/Library/LaunchAgents/<namespace>.<name>.plist` and the domain target is `gui/501/factory-mactest.probe`. `launchctl print` shows `minimum runtime = 10` and `exit timeout = 5`.

### 5. End to end (`failed-ci-triage`, watch, report)

- Throwaway repo: `nejcm/factory-mactest` (private). It has a `CI` workflow that runs `./ci.sh`, which fails when a file named `FAIL` exists. I worked in a scratch clone.
- **Shortcut:** I didn't run `setup-factory`; I wrote a minimal `.factory/profile.md` by hand (Repo, Interview, Run sections). The rest followed automate-factory SKILL.md and runners.md. I filled `run.sh` with the catalog's two blocks, using `trigger=watch`, `daily_cap=6`, no window, `workflows=("CI")`, `claude:default` and `report`. Reports, logs and `.factory/tmp/` went in `.git/info/exclude`.
- Namespace: `factory-factory-mactest-c340e3`. That's 30 characters, and the hash is the same from `shasum -a 256` and `sha256sum`.
- Runner detection (SKILL.md step 1): `oncue list factory-factory-mactest-c340e3` exits 0. **But under the login PATH, `bash --version` reports 3.2**, so the documented check fails even though Homebrew bash is installed (doc mismatch 1).
- Job spec: no `timeout`. `render` gives `Label factory-factory-mactest-c340e3.failed-ci-triage`.
- `--capture-path claude,gh,git,python3,bash,timeout` under the login PATH captured `/Users/nejc/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/local/bin`.

Smoke run, done the way runners.md describes (a manual copy on stdin, then `run --wait`):

```
$ <manual copy, env FACTORY_CHECK_MODELS=1> | oncue install - --capture-path claude,gh,git,python3,bash,timeout
installed                                                                          exit 0
$ oncue run factory-factory-mactest-c340e3 failed-ci-triage --wait
oncue: COMMAND_FAILED: …: launchctl print reports no exit code                     exit 4   (took 0s)
   actual run (launchctl print): last exit code = 0; log: "check: claude:default answered"
   runs.jsonl: outcome completed, exit_code 0, dry_run true, calls 1
$ <manual copy, env FACTORY_DRY_RUN=1> | oncue install - …                         installed, exit 0
$ oncue run … --wait                                                               exit 4, same message
   actual run: last exit code = 0; log: "no event to analyze" (CI green so far) → active (unexercised)
$ oncue install .factory/automations/failed-ci-triage.job.json --capture-path …
installed                                                                          exit 0
```

If I had followed runners.md literally, it would have reported exit 4 as an oncue error and left the entry `proposed`. So the smoke run gate can't pass on launchd (bug 1).

The live watch job:
- Quiet ticks at 21:18, 21:20 and 21:22, each `last exit code = 0`. `runs.jsonl` stayed at 2 lines, the log stayed at 51 bytes, and `reports/failed-ci-triage/` stayed empty: pass.
- I pushed `0d2b5a1` ("test: make CI fail (A)"), and CI run 45828559432 failed. The 21:24 tick fired once:
  - `reports/failed-ci-triage/2026-11-26-0d2b5a1ab761.md` classed the run as a regression and correctly cited `repo/ci.sh:2` and `repo/FAIL`.
  - One `runs.jsonl` line: `outcome completed, exit_code 0, calls 1, trigger watch, events ['45828559432'], cost_usd 0.067`.
  - `seen.tsv`: `45828559432 failed …` then `45828559432 done …`.
- The ticks at 21:26 and 21:28 didn't fire again: `runs.jsonl` stayed at 3 lines, still one report: pass.
- `git status --short` showed only `?? .factory/`. Nothing tracked changed: pass.

### 6. SIGTERM through launchd

For this step I set `notify` to append to a file, then pushed `b5a66ba` ("CI fail (B)"), which failed as CI run 45829549696.

**6a. `launchctl kill TERM`, which signals `run.sh` only.** I sent it at 21:30:14, while `claude -p` was running.

```
$ launchctl kill TERM gui/501/factory-factory-mactest-c340e3.failed-ci-triage      exit 0
run.sh gone at 21:30:28, 14s after TERM (waited for the model call; known limit)
launchctl print: last exit code = 143
runs.jsonl: outcome failed, exit_code 143, calls 0, events ['45829549696']
seen.tsv:   45829549696 failed b5a66ba… (no done)
lock:       empty (released)
notify:     "21:30:28 failed-ci-triage: b5a66ba7b2e0 failed"
```

Pass. One side effect: the model call finished, but `calls` is 0, so its cost is missing from the record (bug 2b).

**6b. `launchctl bootout`.** I sent it at 21:32:12, during the retry fire's `claude -p`.

```
$ launchctl bootout gui/501/factory-factory-mactest-c340e3.failed-ci-triage        exit 0
run.sh gone 5s after bootout (launchd's exit timeout = 5, then SIGKILL)
orphaned: `timeout 30m claude -p …` (pid 31238) and `claude -p …` (31240) kept running until 21:32:31
runs.jsonl: no record for this run
seen.tsv:   45829549696 failed … (second failed line, no done): correct
lock:       holds dead PID 31161
notify:     nothing
.factory/tmp/failed-ci-triage.wzulL7: view dir left behind
```

**Fail** against claim 5: no exit 143, no `failed` record and no notify. I reinstalled the job, and the 21:34 tick logged `lock: took over from gone PID 31161`, refired, and completed: a report was written, `seen` became `done`, and notify printed `completed`. Recovery works. The view dir from the killed run is never removed.

### 7. Cleanup

```
$ oncue uninstall factory-mactest probe                         removed   exit 0
$ oncue uninstall factory-mactest waitprobe                     removed   exit 0
$ oncue uninstall factory-factory-mactest-c340e3 failed-ci-triage   removed   exit 0
$ ls ~/Library/LaunchAgents | grep factory                      (nothing)  exit 1
$ launchctl list | grep factory                                 (nothing)  exit 1
```

I deleted the scratch dirs. `nejcm/factory-mactest` is left for you, and its `main` is red: `FAIL` is still committed.

## Bugs

1. **`oncue run --wait` doesn't wait on launchd.** macOS only. This is in oncue (the bundle), and it surfaces in runners.md:392–395.
   - Reproduce: `install` a fresh manual job, then `run <ns> <name> --wait`. It returns at once with `COMMAND_FAILED: … launchctl print reports no exit code` and exit 4 (`last exit code = (never exited)`). After a previous run, it returns at once with **that** run's exit code:
     - a job sleeping 2 s and set to exit 0, run after the previous run exited 3, gave `exit 3, took=0s`;
     - the log showed the new run ending 3 s later, and `launchctl print` then said `last exit code = 0`.
   - Calls made within launchd's 10 s throttle also return `already running; no new run started`, exit 4.
   - Effect: the smoke run gate can't be trusted on macOS. It always exits 4 because every step installs a fresh copy, and a reinstalled job can report a stale pass or fail.
   - Suggested fix in oncue's launchd backend:
     - record `runs` before `kickstart`;
     - poll `launchctl print` until `runs` goes up and `state = not running`;
     - only then read `last exit code`;
     - treat `(never exited)` as "keep polling".
2. **`launchctl bootout` during a model call: no record, no notify, and an orphaned model process.** macOS only (systemd signals the whole cgroup). In `run.sh:315` (`trap 'exit 143' TERM`) and `run.sh:624` (the model call runs in the foreground).
   - launchd sends TERM to `run.sh` only, then SIGKILL after `exit timeout = 5`. The trap waits for the foreground call, so it never runs. `timeout`/`claude` live in their own process group and keep running.
   - Reproduce: step 6b.
   - Suggested fix (either):
     - run each model call in the background with `wait $!`, so the TERM trap runs at once, and have the trap kill the child's process group (`kill -TERM -- -$pgid`);
     - set `ExitTimeOut` in the plist, above the longest model call (oncue).
   - The first option also removes the known limit in step 6a.
   - 2b, all platforms: a call that finishes after TERM isn't added to `calls`/`cost_usd`, so the weekly budget undercounts (6a: `calls 0` after a ~24 s claude call).
3. **`issue-pipeline.sh:296`: `[ "$(git rev-list --parents -n 1 "$after" | wc -w)" = 3 ]`.** macOS (BSD) only.
   - BSD `wc` prints `       3`, so the string compare always fails and every merged-PR verification without `k=1` is `skipped ambiguous-baseline`.
   - Reproduce: `test_pipeline` (2 tests).
   - Fix: `[ "$(… | wc -w)" -eq 3 ]`, or `awk '{print NF}'`.
   - The other `wc -c` uses (`run.sh:550, 816, 917, 918`, `issue-pipeline.sh:37`) use `-le`/`-gt`, which tolerate the padding. Checked: `[ "      3" -le 5 ]` is true and `= 3` is false.
4. **`references/catalog/maintain-verification.md:50`: `paste -sd, flagged.txt | sed 's/^$/none/'`.** macOS only.
   - For empty input, BSD `paste -s` prints nothing, while GNU prints `\n`. So `sed` never sees a line, and the report says `still flagged: ` instead of `none`.
   - Reproduce: `test_triggers` `test_maintain_verification_flags_changed_features_until_the_skill_changes`.
   - Fix: `f=$(paste -sd, …); printf 'still flagged: %s\n' "${f:-none}"` (after the `, ` substitution).
5. **The captured PATH reaches Homebrew bash only by accident.** macOS. See runners.md:84–88 and claim 4.
   - `--capture-path` adds each tool's *own* dir. With the common macOS login PATH, where `/usr/bin:/bin` come before `/opt/homebrew/bin`, `bash` resolves to `/bin`. Its dir only adds `/bin`.
   - Reproduce, using the login PATH:
     - `--capture-path claude,gh,git,python3,bash,timeout` → `~/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:…`. The job gets bash 5.3, but only because `gh` lives in Homebrew.
     - `--capture-path git,python3,bash,timeout` → `/usr/bin:/bin:/opt/homebrew/bin:…`. The job gets `/bin/bash` 3.2, and `run.sh` would exit `needs bash 4`.
   - Suggested fix (either):
     - make the job spec's `command` `["<abs path of a bash ≥ 4>", "<script>"]`, where detection finds it via `command -v -a bash` or `/opt/homebrew/bin/bash`/`/usr/local/bin/bash`;
     - capture that bash's dir explicitly before `/usr/bin`.
6. **agent-analytics `repo_roots`** (`agent_analytics.py:96`). Shows up most on macOS (`/tmp` and `/var` are symlinks).
   - It doesn't include the unresolved spelling of the real path, so sessions recorded under `/var/…/real` are missed when the repo is passed as an alias.
   - Minor. Fix: also add `os.path.normpath(os.path.abspath(os.path.realpath(repo)))` variants, or match on realpath of each project dir's recorded `cwd` instead.

Test-only (not script bugs, but the suite can't pass on macOS):
- `test_run.py:735` needs Python 3.12+ (backslash inside an f-string expression). macOS's `/usr/bin/python3` is 3.9.6.
- The stubs hard-code `/usr/bin/timeout` (`test_agy.py:230`, `test_cursor.py:254`) and `/usr/bin/mkdir` (`test_cursor.py:149`).
- `test_codex.py:237` uses `printenv A B`.
- `test_watch.py:241` uses `pkill -s`, and `test_watch.py:21` uses `pkill -f` without `-a`.
- The automate-factory tests run `bash` from PATH, so they need bash 4 or later first on PATH.

## Doc mismatches

1. **SKILL.md:20–22** says to detect `bash --version` 4 or later. With Homebrew bash installed but the default macOS login PATH, `bash` is `/bin/bash` 3.2, so detection says "no" while the job can still work (or the reverse; see bug 5). It should look for any bash ≥ 4 (`command -v -a bash`), not the first one.
2. **runners.md:392–395** says `run --wait` "waits for that run and exits with its exit code". On launchd it does neither (bug 1).
3. **Handoff claim 5 and runners.md:301–302** say SIGTERM "for example from `launchctl bootout`" is recorded as `failed` with exit 143. That holds for `launchctl kill TERM`, but not for `bootout` while a model call is running (bug 2).
4. **runners.md:84–88 and claim 4** say adding `bash` and `timeout` last makes the job reach Homebrew bash. That depends on `bash` already resolving to Homebrew in the installer's PATH (bug 5).
5. **runners.md:69**: `shasum -a 256` on macOS works, but macOS 26 also ships `/sbin/sha256sum`, which gives the same output. This isn't wrong, just no longer needed.
6. **runners.md:72–78**: an `interval` schedule on launchd becomes wall-clock-aligned `StartCalendarInterval` (even minutes for 2), not "every n minutes from install". The first fire can come in under n minutes. This is worth one line.
7. **runners.md:88 and handoff step 4** say `--capture-path` with `gtimeout`. Current Homebrew coreutils (9.12) also links plain `timeout` into `/opt/homebrew/bin`, so "`gtimeout` on macOS without `timeout`" rarely applies now. That's fine, just noting it.
8. **The required Python version isn't stated anywhere.** Runtime works on 3.9; the tests need 3.12+.

## Not run

- **`setup-factory`.** I wrote the profile by hand to keep the test on automate-factory, so `setup-factory`'s own macOS behaviour is untested.
- **Other CLIs and modes.** I only used `claude:default`. `codex`, `agy` and `agent` picks, the `comment`, `draft-pr` and `pr` levels, `issue-pipeline` and the change triggers weren't run end to end on macOS (unit tests only).
- **`daily_cap` and `given-up`.** Neither was reached in the live job; both are covered by unit tests.
- **Logged-out behaviour.** I didn't test a launchd agent while logged out (runners.md says it runs only while the user is logged in).
