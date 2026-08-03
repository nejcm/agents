# PostgreSQL Database Optimizer Reference

Read this file only after PostgreSQL has been identified as the target engine. It supplements the shared workflow in `agents/database-optimizer.md`; it does not replace its safety, authorization, baseline, validation, or output requirements.

## Baseline and Plan Analysis

Use `pg_stat_statements` when available. Capture the query shape, representative parameters, calls, total/mean/stddev execution time, rows, shared blocks hit/read, and the observation window.

```sql
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, SETTINGS, FORMAT TEXT)
SELECT ...;
```

`ANALYZE` executes the statement. Do not use it on writes or side-effecting statements unless explicitly authorized and safely isolated. For unsafe statements, use plain `EXPLAIN`, a safe test transaction, a staging copy, or a representative replica.

Inspect:

- Planning versus execution time
- Estimated versus actual rows at every important node
- Loops and row multiplication
- Sequential, index, bitmap, and index-only scans
- Nested-loop, hash, and merge joins
- Shared buffers hit/read, temporary blocks, sort/hash spills, and parallel workers
- `Rows Removed by Filter`, partition pruning, and memory usage where reported

An index scan is not automatically better than a sequential scan. Judge the plan against table size, selectivity, cache state, and workload cost.

Useful diagnostics:

```sql
-- Top statements by total execution time
SELECT queryid, calls,
       round(total_exec_time::numeric, 2) AS total_ms,
       round(mean_exec_time::numeric, 2) AS mean_ms,
       round(stddev_exec_time::numeric, 2) AS stddev_ms,
       rows, shared_blks_hit, shared_blks_read,
       left(query, 300) AS query
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 20;

-- Active sessions and wait events
SELECT pid, usename, application_name, state,
       now() - query_start AS duration,
       wait_event_type, wait_event,
       left(query, 300) AS query
FROM pg_stat_activity
WHERE state <> 'idle'
ORDER BY query_start;

-- Index activity; interpret over representative traffic
SELECT schemaname, relname AS table_name,
       indexrelname AS index_name, idx_scan,
       idx_tup_read, idx_tup_fetch,
       pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
ORDER BY pg_relation_size(indexrelid) DESC;
```

## Index Design

- B-tree is the default for equality, range, join, and ordering predicates.
- Use `INCLUDE` for narrow covering indexes when index-only scans are demonstrated and the extra storage/write cost is justified.
- Use partial indexes for stable, selective predicates; verify that the query predicate implies the index predicate.
- Partial-index predicates must use immutable expressions. A rolling predicate such as `created_at > now() - interval '30 days'` is not a self-maintaining strategy; use partitioning or a managed refresh/rebuild process.
- Use expression indexes only when the query expression matches and the function is suitable for indexing.
- Use GIN for supported JSONB, array, and full-text patterns; GiST for range, geometric, and PostGIS workloads; BRIN for very large append-oriented tables with useful physical correlation.
- For composite indexes, align equality predicates, range predicates, ordering, and covering needs with real query patterns. Do not apply a blanket “most selective first” rule.
- Inspect existing indexes, primary/unique constraints, and left-prefix redundancy before creating another index.

For a production build:

```sql
CREATE INDEX CONCURRENTLY idx_example
    ON public.example (tenant_id, created_at DESC);
```

`CREATE INDEX CONCURRENTLY` cannot run inside a transaction, can consume substantial I/O, may leave an invalid index after failure, and still needs monitoring. Confirm migration tooling supports non-transactional DDL. For bloat, consider `REINDEX INDEX CONCURRENTLY` where supported and appropriate.

Never remove an index only because `idx_scan = 0` immediately after a reset, restart, deployment, or index creation. Verify representative traffic, dependencies, constraint ownership, storage, and rollback.

## Statistics and Maintenance

- Run `ANALYZE` after material data changes when authorized; investigate stale or insufficient statistics when estimates diverge from actual rows.
- Use per-column statistics targets only for demonstrated skew/cardinality problems; higher targets increase analysis cost and catalog size.
- Inspect `pg_stat_user_tables` for dead tuples, analyze/vacuum freshness, and autovacuum behavior.
- Investigate long-running transactions and replication slots before blaming vacuum.
- Treat `VACUUM FULL` as a disruptive rewrite requiring an exclusive lock and extra disk space. Prefer regular vacuum, autovacuum tuning, or an online rewrite strategy when appropriate.

## Configuration and Concurrency

- `work_mem` applies per sort/hash operation and can multiply across concurrent queries and parallel workers. Prefer a session-level experiment before changing it globally.
- `effective_cache_size` informs planner cost estimates; it does not allocate memory.
- Do not change `shared_buffers`, `random_page_cost`, parallel settings, checkpoint/WAL settings, or durability settings from generic heuristics alone. Measure the hardware and workload first.
- Use `SET enable_* = off` only to test a hypothesis about plan alternatives, never as a durable production fix.
- Inspect `pg_locks`, blocking relationships, transaction age, pool saturation, and isolation behavior for contention or deadlocks.
- Route reads to replicas only when replica staleness and failover behavior are acceptable. Monitor replay and WAL lag after changes.

## Validation

Repeat the same query with equivalent parameters, data, cache state, and concurrency. Compare plan shape, estimates, execution time distribution, buffers hit/read, CPU/I/O, writes, lock waits, and replica lag. Validate result equivalence and observe index usage and write impact over a representative period before declaring success.
