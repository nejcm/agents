# Optimization

## Playbook

Choose only changes supported by evidence:

- **Algorithms**: improve complexity or data structures before micro-optimizing syntax.
- **Databases**: inspect plans and row estimates; add narrowly justified indexes;
  eliminate N+1; batch or reshape queries; select only needed data; size pools.
- **I/O**: move blocking work off latency-sensitive paths; batch calls; reduce
  round trips; parallelize only independent, bounded work.
- **Caching**: cache expensive reusable results with explicit keys, freshness,
  invalidation, capacity, and failure behavior.
- **Memory**: reduce retention and churn; bound caches and queues; release
  listeners, timers, buffers, handles, and native resources.
- **APIs**: paginate or stream large results; shrink serialization and payloads;
  apply backpressure and concurrency limits.
- **Frontend**: split on real navigation/use boundaries; remove unused code;
  optimize images and fonts; defer non-critical work; diagnose main-thread and
  rendering costs.
- **Runtime**: tune pools, GC, worker counts, and concurrency only after
  measuring saturation and tail-latency effects.

Every optimization can move cost elsewhere. Report effects on readability,
complexity, memory, latency tails, throughput, correctness, and operational risk.

## Key Metrics

- **Backend**: p50/p95/p99 latency, throughput, error and timeout rate, queue
  time, query time, CPU, memory, GC, I/O, saturation
- **Frontend**: LCP, INP, CLS, FCP, total blocking time, JS execution,
  transferred bytes, route-level bundle size
- **Memory**: managed heap, RSS, allocation rate, retained size, GC pause and
  frequency, open resources
- **Cost**: CPU-seconds, memory-time, database work, network transfer, and
  infrastructure cost per unit of useful work
