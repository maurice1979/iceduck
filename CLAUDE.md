# CLAUDE.md

Guidance for Claude Code sessions working in this repository.

## What this project is

**IceDuck** — a Data Engineering **learning/portfolio project**: a modern lakehouse built from open-source tooling — DuckDB, dbt, Apache Iceberg on AWS Glue Data Catalog, Floci (local AWS emulator), OpenTofu, and Docker. The name reflects the core of the stack: **Ice**berg on **Duck**DB. Full architecture and rationale: [`docs/plans/0001-lakehouse-architecture-outline.md`](docs/plans/0001-lakehouse-architecture-outline.md). Dataset: Olist Brazilian E-Commerce. Repo folder is `lakehouse/`; package/CLI/Glue-database naming uses `iceduck`.

Key architectural facts to keep consistent across the codebase:
- **Single catalog**: AWS Glue Data Catalog (emulated via Floci) is the catalog for every medallion layer — bronze, silver, and gold are all real Apache Iceberg tables in Glue databases `iceduck_bronze`/`iceduck_silver`/`iceduck_gold`. There is no DuckLake and no separate metadata database (no Postgres).
- **Bronze** is written via `pyiceberg`'s `GlueCatalog` directly (not through dbt).
- **Silver/gold** are written by `dbt-duckdb`, attached to Glue as an Iceberg catalog. The exact write mechanism (native `dbt-duckdb[glue]` materialization vs. a `pyiceberg`-based fallback) is decided by the `ICEBERG_WRITE_MODE` env var, resolved by an early spike — check `docs/plans/` for the recorded verdict before assuming either path.
- Everything runs against Floci (`http://localhost:4566` by default), not real AWS — but should require only endpoint/credential changes to point at real AWS.
- Package name: `iceduck`. CLI entry point: `iceduck`. Python source lives under `src/iceduck/`; dbt project under `dbt/iceduck/`.

## Working agreements (from the project owner)

- **This repo exists to learn and practice Data Engineering.** When working here, proactively point out weak, outdated, or inconsistent architectural/technical decisions — including the user's own suggestions — and explain the better alternative. Don't silently comply with an approach that doesn't hold up; correcting course is the explicit point of this project, not a courtesy.
- **Keep `README.md` current.** Whenever a change meaningfully affects what's built, how to run it, the architecture, or the tech stack, update `README.md` in the same change — treat it as living documentation, not a one-time artifact.
- Design decisions and their rationale belong in the repo, not just in conversation — future sessions (and portfolio reviewers) should be able to reconstruct *why* a decision was made by reading it alone. Two complementary conventions cover this:
  - `docs/adr/` — Architecture Decision Records: one atomic, consequential decision per file (Context/Decision/Consequences), numbered independently of `docs/plans/`. See `docs/adr/README.md`.
  - `docs/plans/` — phase/build-order narratives: one file per build phase, following the numbering in `0001-lakehouse-architecture-outline.md`, covering what was built and how it was verified, and referencing the ADR(s) it implements.

## Conventions

- Python dependency management: `uv` (not pip/poetry).
- No orchestrator (no Dagster/Airflow) — pipeline steps are driven by a Makefile and a small `click`-based CLI (`iceduck`).
- No CI/CD yet (tracked as a future addition in `docs/TODO.md`) — don't assume a CI pipeline exists.
