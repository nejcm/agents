# Plan: fewer macOS install deps for the factory preset

Branch `feat/factory-preset`, after `af6528f`. Source: the decision subagent's proposal.

## Target

| | Install line |
|---|---|
| Before `af6528f` | `xcode-select --install; brew install bash coreutils gh node` + `python` (3.11 floor) |
| Now (`af6528f`) | `xcode-select --install; brew install bash python gh node` |
| After this plan (step 4 option A) | `xcode-select --install; brew install bash gh node` (or bun instead of node) |

Plus one model CLI. `git` and `/usr/bin/python3` (3.9.6) come with the Command Line Tools.

## Already done in `af6528f`

- SKILL.md step 1 detects a bash 4+ `<bash>` (PATH first, then `/opt/homebrew/bin/bash`, `/usr/local/bin/bash`).
- runners.md records `<bash>` unresolved. Job `command` is `[<bash>, <script>]`, so the login PATH order doesn't matter.
- A python3 `timeout()` replaces GNU `timeout`, so jobs no longer need `coreutils`.
- The test suites are portable to macOS.

## Remaining steps

1. **setup-factory bash check matches detection.**
   - In `setup-factory/SKILL.md:33`, `bash -c 'echo $BASH_VERSION'` only checks the PATH bash, so it reports 3.2 on a Mac that already has Homebrew bash.
   - Replace it with the same probe as automate-factory step 1: the first of `type -ap bash`, `/opt/homebrew/bin/bash`, `/usr/local/bin/bash` whose version is 4 or later.
   - About 1 line.
2. **Node or bun is needed at install time only.**
   - Add one line to `runners.md` near line 66: `<oncue>` needs node or bun only to install and manage jobs, because the plist runs `[<bash>, script]`.
   - Mirror it in the setup-factory table's node row ("install/manage only").
   - About 2 lines.
3. **One macOS install line.**
   - Add the single line from the Target table to `README.md:106` and to setup-factory, next to the table. Today the user has to piece it together from 5 rows.
   - About 3 lines.
4. **Python floor: decision needed.** `tomllib` is the only 3.11 need. It is lazily imported in `run.sh` `pyproject()` and `cargo()`, at lines 784 and 794, and is used only by the dependency gate on TOML manifests.
   - **A (recommended):**
     - Lower the `run.sh:7` floor to 3.9.
     - Wrap the two `import tomllib` calls so that an ImportError blocks only that gate, with "pyproject/Cargo gate needs python3 3.11 (brew install python)".
     - Drops `brew install python` for repos without TOML manifests.
     - Cost:
       - about 6 lines;
       - running the suite under `/usr/bin/python3`;
       - auditing the embedded Python for 3.10+ syntax (`match`, `X | Y` annotations, `zip(strict=)`, parenthesized context managers).
     - Risk: 3.9 is EOL upstream, but Apple still ships it.
   - **B:** keep 3.11. No code change. The install line keeps `python`.
   - **Rejected: vendoring a TOML parser.** That would be a dependency we'd have to keep.
5. **Optional: the guard names the spec.**
   - Extend the `run.sh:6` message with "or set the job spec's `<bash>` to a bash 4+".
   - This catches a spec that was rendered before Homebrew bash existed.
   - 1 line.
6. **oncue `run --wait` on launchd (upstream).**
   - `--wait` returns before the launchd job finishes.
   - Fix it in the oncue repo, where the bundle's source is not vendored here. Then rebuild `assets/oncue.mjs`.
   - Then delete the `launchctl print` polling workaround in `runners.md`.
   - This is separate from the deps work; track it as an issue.

## Rejected

- **Port to bash 3.2.** The scripts rely on associative arrays (`declare -A`, 4 sites), `mapfile` (2) and `BASHPID` (1), and fire-time ledgers would lose O(1) lookups. A port would touch the core of `run.sh` and `issue-pipeline.sh` for a single `brew install bash`.
- **zsh as the runner.** Same rewrite cost, and the scripts would diverge from Linux.

## Verification

- automate-factory, fix-issues and agent-analytics suites:
  - on macOS with Homebrew bash;
  - with option A, also with `/usr/bin/python3` first on PATH.
- One launchd install, fire and bootout on `nejcm/factory-mactest`, then uninstall.
- Linux run of the suites (not yet done for `af6528f`).
