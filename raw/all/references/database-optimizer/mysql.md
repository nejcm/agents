# MySQL Database Optimizer Reference

Read this file only after MySQL has been identified as the target engine. It supplements the shared workflow in `agents/database-optimizer.md`; it does not replace its safety, authorization, baseline, validation, or output requirements.

## Baseline and Plan Analysis

Use the slow-query log and `performance_schema` statement digests when available. Capture the query shape, representative parameters, calls, total/average/max latency, rows examined/sent, errors, and the observation window.

```sql
EXPLAIN FORMAT=JSON
SELECT ...;
```

Use `EXPLAIN ANALYZE` only on supported versions and safe statements. It executes the query and may acquire locks or cause side effects. For unsafe statements, use plain `EXPLAIN`, a safe staging copy, or a representative read-only workload.

Inspect:

- Access type, possible keys, selected key, key length, and rows examined
- Estimated versus actual rows and filtered rows
- Join order and join algorithms
- Covering-index indicators such as `Using index`
- `Using filesort`, temporary tables, spills, and sort/aggregate cost
- Partition pruning, index condition pushdown, and residual filtering
- InnoDB buffer-pool reads, redo/undo pressure, lock waits, and transaction age

Useful diagnostics:

```sql
-- MySQL 8: top statement digests by total wait time
SELECT SCHEMA_NAME, DIGEST_TEXT, COUNT_STAR,
       ROUND(SUM_TIMER_WAIT / 1000000000000, 3) AS total_seconds,
       ROUND(AVG_TIMER_WAIT / 1000000000000, 3) AS average_seconds,
       SUM_ROWS_EXAMINED, SUM_ROWS_SENT
FROM performance_schema.events_statements_summary_by_digest
WHERE SCHEMA_NAME IS NOT NULL
ORDER BY SUM_TIMER_WAIT DESC
LIMIT 20;

-- Current long-running statements; confirm version/schema before use
SELECT ID, USER, HOST, DB, COMMAND, TIME, STATE,
       LEFT(INFO, 300) AS query
FROM information_schema.PROCESSLIST
WHERE COMMAND <> 'Sleep'
ORDER BY TIME DESC;

EXPLAIN FORMAT=JSON
SELECT ...;
```

Confirm that the required Performance Schema instruments and consumers are enabled before drawing conclusions from absent data.

## Index Design

- Design indexes around the leftmost-prefix rule and the query’s equality, range, join, ordering, and projection needs.
- MySQL has no PostgreSQL-style `INCLUDE`; covering columns become index key columns and add storage and write cost.
- Do not apply a blanket “most selective first” rule. Test column order against actual predicates, cardinality, ordering, and workload frequency.
- Inspect existing indexes and constraints for redundant prefixes before creating another index.
- Use generated columns or functional indexes only when supported by the target version and when the query expression matches the indexed expression.
- Use full-text indexes for supported full-text search rather than leading-wildcard B-tree lookups.
- Account for index width, secondary-index maintenance, buffer-pool residency, and replication cost.

Before a large-table index change, verify online DDL behavior for the exact MySQL/InnoDB version and table:

```sql
ALTER TABLE example
    ADD INDEX idx_example (tenant_id, created_at),
    ALGORITHM=INPLACE,
    LOCK=NONE;
```

Do not assume `ALGORITHM=INPLACE` or `LOCK=NONE` guarantees no blocking for every operation. Check metadata locks, table rebuild behavior, temporary disk use, redo/undo pressure, and replica impact. Preserve an exact rollback and use the project’s migration mechanism.

Never drop an index solely because a short-lived usage counter is zero. Verify representative traffic, foreign-key/constraint dependencies, workload coverage, and rollback.

## Statistics, Schema, and Partitioning

- Use `ANALYZE TABLE` when statistics are the demonstrated problem and the operational impact is understood.
- Consider histograms for skewed, non-indexed columns when supported and justified by estimate errors.
- Evaluate partitioning only when partition pruning, lifecycle operations, or archival materially help. Partitioning is not a general substitute for indexes and imposes key, uniqueness, and query restrictions.
- Use range partitioning for data lifecycle patterns only with a partition-management plan, boundary tests, and monitoring for the catch-all partition.
- Select data types and row formats with storage, comparison, index width, and conversion behavior in mind. Avoid implicit type conversion in predicates and joins.
- Do not recommend the removed MySQL 8.0 query cache.

## InnoDB, Configuration, and Replication

- Treat `innodb_buffer_pool_size` as a capacity decision based on total workload, connection memory, OS needs, and co-located services; do not apply a fixed percentage blindly.
- Treat `max_connections`, temporary-table limits, flush/durability settings, and redo-log sizing as workload and reliability decisions, not isolated speed switches.
- Investigate long transactions, history-list growth, row-lock waits, deadlocks, hot rows, and metadata locks before changing configuration.
- Verify replication format, parallel apply behavior, transaction size, and replica lag after schema or index changes.
- Read replicas are useful only when staleness, routing, failover, and read-after-write behavior are acceptable.

## Validation

Repeat the same query with equivalent parameters, data, cache state, and concurrency. Compare plan shape, estimates, execution time distribution, rows examined/sent, CPU/I/O, temporary tables, locks, writes, and replica lag. Validate result equivalence and observe index usage and write impact over a representative period before declaring success.
