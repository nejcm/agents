---
name: testing-best-practices
description: "Use when writing, adding, or changing tests in any language, or when asked whether something needs a test."
---

# Writing tests

Default to fewer tests. Every test is code to maintain; add one only if it earns its place.

## 1. Decide if a test is warranted

Test behaviour that can break and matters:
- branching logic, parsing, state transitions
- money, security, data loss
- a bug being fixed (add a regression test that fails before the fix)
- public contracts (API, CLI output, file formats)

Do NOT test:
- trivial getters/setters, constants, simple data holders
- framework, library, or language behaviour
- private helpers already exercised through the public API
- pure wiring or glue with no logic
- a restatement of the implementation
- permutations of the same code path

If nothing above applies, write no test and say so.

## 2. Budget

- One test per distinct behaviour.
- Extend an existing test or table before adding a new one; add a new file last.
- Mirror the repo's test style, helpers, and fixtures.
- No new test framework, library, or dependency.

## 3. How

- Test through the public interface. Assert outputs and observable effects, not internals or call order.
- Real over mocked for what you own: temp dirs, local DB, in-process services. Mock what you don't own (third-party APIs, email, payment, external queues), and only via your own thin wrapper. Never mock the unit under test or its pure collaborators.
- Mocks mirror the real shape (all fields downstream code reads). Never assert on the mock itself.
- If mock setup outweighs the test, test one level up with real parts instead.
- Deterministic: freeze time and TZ, seed randomness, no real network. Wait on a condition with a timeout, never a fixed sleep (unless timing is the behaviour under test).
- Isolated: no order dependence, no shared mutable state. Use unique IDs rather than relying on cleanup; always tear down long-lived resources (containers, processes, cloud resources).
- No test-only methods in production code; put helpers in test utils.
- Roundtrips, normalizers, sort/compare: prefer a property test (roundtrip, idempotence, invariant) if the repo already has a PBT library.
- Edge cases worth it: boundaries (both sides of a threshold, off-by-one), empty/invalid input at trust boundaries, error paths that prevent data loss. Skip speculative cases with no plausible failure.
- Name tests by behaviour: `rejects expired token`, not `test_validate_2`.
- Failures must be readable: assert with actual vs expected diff or a message. One behaviour per test (table/subtests are fine).

## 4. Self-check before keeping a test

- A new test must fail once against broken code (for a bug fix, against the unfixed code).
- Mutate the code in your head (flip a comparison, change rounding, drop a branch). If the test still passes, it is worthless: fix or delete it.
- Would a harmless refactor break it? If yes, it is coupled to the implementation: rewrite it against behaviour.
- Is it a near-duplicate of another test? Merge or delete.

## 5. Finish

- Run the relevant tests (focused, not the whole suite unless needed) and confirm they pass.
- Report what is tested and what was deliberately not tested.
