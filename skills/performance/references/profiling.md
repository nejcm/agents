# Profiling

## Tools

Account for profiler overhead and permissions. Prefer sampling profilers for
production-like workloads; reproduce invasive profiling in a safe environment.

### Node.js

- Built-in CPU profiler: `node --prof app.js`, then `node --prof-process isolate-*.log`
- Clinic Doctor for event-loop and system diagnostics
- Clinic Flame or `0x` for interactive CPU flamegraphs
- Clinic Bubbleprof for async-operation relationships
- Heap snapshots, allocation timelines, and `--inspect` for memory
- Autocannon for HTTP load; vary concurrency, duration, pipelining, and payloads deliberately

### Python

- `py-spy record -o profile.svg -- python app.py` for low-overhead sampling
- `py-spy top --pid <pid>` or `py-spy dump --pid <pid>` for a running process
- `python -m cProfile -o output.prof script.py` plus `pstats` for deterministic profiling
- `memory_profiler`, `tracemalloc`, or heap tooling suited to the allocator and runtime

### System and Data Layers

- Linux `perf` for system-wide CPU, kernel, and native stacks
- Platform-native tracing when app profilers cannot explain scheduler, I/O, or syscall time
- Slow-query logs and `EXPLAIN` / `EXPLAIN ANALYZE` for queries
- Browser performance traces and bundle analyzers for frontend execution, rendering, delivery

## CPU and Flamegraphs

- Width is accumulated samples or time; wide frames are candidates, not bugs.
- Height is stack depth, not cost.
- Color is usually categorical or arbitrary; check the profiler's convention.
- Self time is work inside a function; total time includes callees.
- Wide leaf frames often mean direct CPU work; wide parents, an expensive path.
- Runtime, GC, kernel, and library frames may reflect app allocation or I/O
  patterns; analyze before discarding.
- Deep stacks do not prove excessive abstraction; thin frames do not justify inlining.

Correlate with wall time, CPU utilization, off-CPU time, request traces, and
workload phase. A CPU profile cannot explain time spent waiting.

Query large artifacts (`.cpuprofile`, heap snapshot) by loading them into sqlite,
one row per sample or node, instead of reading them. A frame without a source
mapping is not yet a diagnosis. Without a paired before/after capture to diff,
call the finding a hypothesis.

## Memory

Distinguish:

- **Leak**: retained live objects grow across equivalent workload cycles.
- **Expected growth**: caches, pools, JIT, or workload state reach a bounded steady state.
- **Churn**: high allocation and collection without sustained retention.
- **Native growth**: RSS rises while the managed heap stays flat.

Compare repeated heap snapshots or allocation traces and their retaining paths.
Exercise cleanup paths: listeners, timers, subscriptions, caches, file handles,
connections. Do not infer a leak from RSS growth alone.

## Load Tests

Verify the load generator is not saturated. Track:

- Throughput and completed work
- p50, p95, p99, and max latency
- Error, timeout, and retry rates
- CPU, memory, GC, network, disk, database, and pool saturation
- Coordinated omission and open- versus closed-loop behavior

Warm up runtimes where relevant, isolate setup from measurement, and use
production-like payloads and data cardinality. Compare runs on equivalent
environments.
