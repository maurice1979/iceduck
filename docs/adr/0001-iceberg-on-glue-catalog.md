# ADR-0001: Apache Iceberg on AWS Glue Data Catalog as the single lakehouse catalog

Status: Accepted
Date: 2026-09-15

## Context

IceDuck needs a genuinely "modern lakehouse" architecture, not just DuckDB + Parquet + dbt. That means an open table format with ACID transactions, schema evolution, and time travel, rather than plain Parquet files.

DuckLake was considered first but was dropped: it would have required forcing Glue to act as DuckLake's catalog, or standing up a separate metadata database (e.g. Postgres) purely to hold catalog state — extra infrastructure with no benefit over using a real AWS-native catalog directly, especially since one of this project's explicit goals is practicing AWS-shaped infrastructure.

Research confirmed Apache Iceberg on AWS Glue Data Catalog is achievable with the rest of the stack: `dbt-duckdb` has experimental native support for persisting Iceberg tables into Glue (via the `dbt-duckdb[glue]` extra and dbt's `catalogs.yml`), and DuckDB can attach to Glue as an Iceberg REST-compatible catalog.

## Decision

Use Apache Iceberg tables for all three medallion layers (bronze, silver, gold), every one registered in AWS Glue Data Catalog — emulated locally via Floci (see ADR-0002), the same catalog against real AWS. No DuckLake, no separate metadata database (no Postgres).

## Consequences

- Glue becomes the **single catalog** for the entire lakehouse — no extra catalog infrastructure to run or reason about.
- Enables the project's central interoperability claim: because a real Iceberg table is queryable by any Iceberg-aware engine, the same gold tables are independently readable via emulated Athena as well as a fresh DuckDB session — proving genuine multi-engine interoperability on one physical table, not an engine-specific format.
- The Glue-Iceberg write path via `dbt-duckdb[glue]` is labeled experimental, so this decision carries verification risk — mitigated by an early spike and a `pyiceberg`-based fallback write path (see ADR-0005).
- Ties the project to AWS Glue's specific Iceberg REST-compatible semantics; porting to a different catalog (e.g. a pure Iceberg REST catalog, Nessie) later would mean re-verifying both write paths against the new catalog.
