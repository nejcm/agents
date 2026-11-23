# Phase 3: Run

Start the whole system for real, against isolated test data, prove it is usable, and tear it down.
The recipe that works becomes the profile's `Run` section and the base for phase 4.

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
5. **Teardown**: stop only what you started (by PID, container or compose project name, never by
   process name). Remove scratch data. Confirm the ports are free.

## When start or readiness fails

Run step 5 for everything started so far, then stop. Report the failed command or readiness
check, its output
(trimmed to the error, credentials and connection strings redacted), and what you checked.
Propose fixes as diffs or commands, and apply none without the user's confirmation. Record the
failure in the profile's `Run` section so phase 4 does not start against a broken base.

## Output

The profile's `Run` section: prerequisites, isolation choices, start commands in order, the
readiness check and what it proved, teardown commands, timings (cold start, ready), and known
gaps.
