# ADR-0013: Run dbt on the Fusion engine (`dbt` v2), not `dbt-core`/`dbt-duckdb`

Status: Accepted
Date: 2026-09-21

## Context

The project had been running dbt on the traditional Python stack: `dbt-core>=1.12.4` and `dbt-duckdb[glue]>=1.11.0` as `pyproject.toml` dependencies, invoked as `uv run dbt` / plain `dbt` (via `subprocess` in `src/iceduck/cli/main.py`).

dbt Labs has since shipped dbt v2 — "Fusion" — a from-scratch Rust rewrite: a local SQL compiler that validates queries before hitting the warehouse, an ADBC/Arrow connection layer, Parquet-based project metadata instead of JSON, and reported 2–70x faster parsing/compilation. It ships as a standalone binary (`brew install dbt`), not a PyPI package.

Two real risks made this worth verifying before switching, rather than assuming it would just work:

1. dbt's own docs were internally inconsistent about DuckDB adapter maturity under Fusion — one page called it GA (CLI-only), another implied it was still in preview, and open feature-request issues on `dbt-labs/dbt-fusion` (e.g. #110) suggested a purpose-built DuckDB adapter was still in progress.
2. Multiple published Fusion docs pages stated the bundled DuckDB driver **cannot load extensions** (`httpfs`, `iceberg`, `parquet`, `spatial`) and that a system-installed driver (via [`dbc`](https://docs.columnar.tech/dbc/)) is required to work around it. This project's entire dbt layer depends on both `httpfs` (S3 secrets against Floci) and `iceberg` (`iceberg_scan` reads via the `bronze_scan`/`silver_scan`-style macro from ADR-0010) — if that limitation were real, Fusion would be a non-starter without the extra driver install.

## Decision

Verified empirically on `feature/use-dbt-fusion-engine` rather than trusting the docs: ran `dbt build --select staging.health` and `dbt build --select marts.core` against real Glue-resolved bronze/silver Iceberg data, using the already-installed Homebrew `dbt` 2.0.6 binary directly. Both `httpfs` and `iceberg` loaded and worked with **no** system driver / `dbc` install — 19/19 and 28/28 model+test steps passed, external Parquet output was written correctly, and downstream `pyiceberg` publish succeeded (row counts matched at every layer). `dbt docs generate` (the newer Parquet/DuckDB-WASM-backed docs site) also worked unmodified. The documented "bundled driver can't load extensions" limitation did not hold for this DuckDB version/extension pair — the docs are stale or describe a narrower case than this project hits.

Given that, `dbt-core` and `dbt-duckdb[glue]` were removed from `pyproject.toml` entirely. dbt is now an external tool prerequisite (`brew install dbt`), the same category as Docker/OpenTofu/AWS CLI, not a Python dependency. No application code changed — `main.py`'s `subprocess.run(["dbt", ...])` calls were already engine-agnostic; the only reason `uv run dbt` previously resolved to `dbt-core` was that `.venv/bin/dbt` (installed by the now-removed PyPI package) shadowed the Homebrew binary on `PATH`. Removing the package let `uv run dbt` fall through to Fusion automatically.

## Consequences

- Build feedback is now near-instant (staging build 1.8s, marts build 1.9s for this project's size) versus the noticeably slower `dbt-core` interpreter startup + parse overhead previously.
- One fewer category of Python dependency drift: no `dbt-core`/`dbt-duckdb` version pin to keep in sync with the DuckDB CLI/extension versions used elsewhere in the project.
- New standing risk: Fusion is new and evolving fast, and its own documentation is demonstrably inconsistent (see Context). Any future dbt feature this project adopts (new materialization, `catalogs.yml`, semantic layer, etc.) should be verified empirically the same way, not assumed from docs — dbt-core's assumptions about adapter behavior no longer reliably apply.
- `dbt` now has to be a system-installed binary present in every environment that runs the pipeline (dev machine, CI once it exists) — it can no longer be pulled in transitively by `uv sync`. `README.md`'s prerequisites list was updated accordingly.
- The Fusion engine intentionally has no dbt-utils-style package ecosystem parity yet; this project doesn't use any dbt packages (`packages.yml` doesn't exist), so that's a non-issue here, but would need re-checking before adding one.
