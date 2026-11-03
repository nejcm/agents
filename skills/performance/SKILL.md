---
name: performance
description: Use when the user asks to profile, benchmark, load-test, or speed something up, reduce latency, memory, CPU, bundle size, query time, or cost, or investigate a slowdown, leak, or performance regression.
category: workflow
---

# Performance

Find bottlenecks, validate their causes, and improve efficiency. Optimize for
measurable user and system outcomes, not synthetic scores.

Scope: CPU and event-loop hotspots, memory and leaks, benchmarks and load tests,
database queries, algorithmic and I/O work, frontend delivery and Core Web
Vitals, production latency, saturation, and cost.

## Workflow

1. Define the workload and success metric, and write the claim you expect to
   ship ("export is 30% faster at p50 on the 60k-row dataset"). Record hardware,
   runtime, dependency versions, data volume, concurrency, warm-up, and config.
2. Read the harness for what it times, counts, and ignores. Check machine load
   (`uptime` against `nproc`). Establish a baseline with at least 5 runs per
   side, alternating A, B, A, B when comparing; report median and range.
3. Profile the representative workload. Separate CPU, I/O, lock contention,
   memory pressure, downstream latency, and load-generator limits.
4. Rank findings by total impact and confidence; focus on code the project controls.
5. Form one falsifiable hypothesis and make the smallest relevant change.
6. Re-run the same benchmark; compare before/after, including resource use and
   correctness. A gap inside run-to-run variation is no measurable difference.
7. Check for shifted bottlenecks, regressions, and operational tradeoffs. Add a
   budget or regression test when practical.

When results are noisy or irreproducible, fix the experiment before recommending
code changes. When iterating, keep a change only if it beats noise with
correctness intact; otherwise revert it before the next. Never stack untested
changes.

## Before Trusting a Number

- **Name the limiter.** Say what stops it from being 2x faster: CPU, memory
  bandwidth, I/O, a lock, a downstream call, the load generator.
- **Check the ceiling.** A speedup larger than the optimized fraction allows
  (Amdahl), or throughput above memory, disk, or network bandwidth, means the
  measurement is wrong.
- **Tune every side.** Run each as production does: release build, production
  flags, cache warmth, same data and versions. One side on defaults compares
  configurations, not implementations.
- **Confirm the work ran inside the timed region**: no unawaited async, lazy
  evaluation, dead-code elimination, cache hits, or setup leaking in or out.
  Count errors and non-success results; rejections are fast, timeouts slow.

## References

Load on demand:

- `references/profiling.md`: tools per stack, reading flamegraphs, memory
  analysis, load-test hygiene.
- `references/optimization.md`: optimization playbook and key metrics.

Use tools already in the project. Check current docs before introducing new ones.

## Rules

- Measure before optimizing; do not guess from code shape.
- Benchmark before and after under equivalent conditions.
- Preserve correctness; validate outputs, not only timing.
- Focus on the largest evidenced bottleneck.
- Never claim a speedup without data and methodology.
- Never hide variance, errors, warm-up effects, or profiler overhead.
- Do not trade readability or operational safety for negligible gains.
- Keep production changes incremental, observable, and reversible.
- Treat thresholds as workload-specific budgets, not universal pass/fail numbers.

## Deliverables

1. Workload and environment
2. Baseline, method, run count, and variability
3. Evidence and ranked bottlenecks
4. Root-cause hypothesis, named limiter, and confidence
5. Recommended or applied change
6. Before/after results using the same method, led by a verdict: faster, slower,
   no measurable difference, or inconclusive (limiter unnamed, a side untuned, or
   errors or work unchecked; name the gap)
7. Tradeoffs, limitations, rollback, and next bottleneck
8. Regression guard or monitoring recommendation
