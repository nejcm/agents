# Phase 3: Run

Start the whole system for real, against isolated test data, prove it is usable, and tear it down.
The recipe that works becomes the profile's `Run` section and the base for phase 4.

A repo with nothing long-running (a library, a one-shot CLI) has no services or ports: its run
proof is a real consumer, the CLI's main command or a documented example importing the built
package, and those fields are `not applicable`. With no executable surface at all, record that
in `Known gaps`, mark phase 4 unavailable and continue with phases 5 and 6; never invent an app.

## Steps

1. **Dependent repos**: for each one phase 1 found, reuse the path recorded in the profile's `Run`
   section, else ask the user for a local path or URL. Never clone without asking. Record the path or URL, the branch or SHA used, and how it is started.
2. **Isolate**: use a fresh data dir, a throwaway database or schema, non-default ports, and test
   accounts or seed data. Never point at a shared or production instance. If isolation is not
   possible (fixed port, single shared DB), stop and say so. Keep production integrations
   (error trackers, analytics, payment, email) disabled or pointed at test modes.
3. **Start**: use the repo's own commands from phase 1, in dependency order (services, migrations,
   seed, dependent repos, the app). Note each resource as it starts, for teardown. Record each
   command as run, with credentials as env var references (`$DATABASE_URL`), never inline values.
4. **Readiness**: usable, not just a process answering. Exercise the primary surface once the way
   a user would (load a page that reads seeded data, call an endpoint that hits the DB, run the
   CLI's main command). A health check that passes while migrations or seeds are still running
   does not count.
5. **Test recipe**: write one command line that passes in a fresh checkout with nothing installed
   (a Git worktree has no `node_modules`, virtualenv or build output): the dependency install or
   bootstrap command, then the test command from phase 1, run from the repo root, as this phase
   or the CI test job ran them. Name the env vars and services it needs. `automate-factory` runs
   it unchanged in new worktrees as its test gate. If no such line can be established, record
   `unavailable: <reason>`; never record the bare test script as the recipe.
6. **Teardown**: stop only what you started (by PID, container or compose project name, never by
   process name). Remove scratch data. Confirm the ports are free.

## When start or readiness fails

Run step 6 for everything started so far, then stop. Report the failed command or readiness
check, its output
(trimmed to the error, credentials and connection strings redacted), and what you checked.
Propose fixes as diffs or commands, and apply none without the user's confirmation. Record the
failure in the profile's `Run` section so phase 4 does not start against a broken base.

## Output

The profile's `Run` section: prerequisites, isolation choices, start commands in order, the
readiness check and what it proved, teardown commands, timings (cold start, ready), the test
recipe, and known gaps.
