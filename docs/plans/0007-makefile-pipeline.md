# 0007 — Makefile Pipeline (`demo` / `reset`)

Status: applied
Date: 2026-09-18

## Context

Build Order step 9 from [`0001-lakehouse-architecture-outline.md`](0001-lakehouse-architecture-outline.md): the `Makefile` only had `floci-up/down` and `infra-init/validate/plan/apply/destroy` — every pipeline step (`s3-upload-raw`, `ingest-all`, `build-silver`, `build-gold`) had to be invoked individually via `uv run iceduck ...`, as documented piecemeal in the README. This phase adds the missing `raw`, `ingest`, `dbt`, `demo`, and `reset` targets so the whole pipeline — infra through gold — is a single `make demo` away, per [ADR-0004](../adr/0004-no-orchestrator.md)'s "Makefile + CLI, no orchestrator" decision.

## What was built

- `raw`, `ingest`, `dbt`: thin wrappers around `iceduck s3-upload-raw`, `iceduck ingest-all`, and `iceduck build-silver && iceduck build-gold` respectively — one-word entry points for each pipeline stage.
- `demo`: `floci-up` (now `docker compose up -d --wait`, so it actually blocks until Floci reports healthy rather than returning immediately) → `tofu apply -auto-approve` (a separate non-interactive invocation, not a reuse of the existing `infra-apply` target — that target stays interactive on purpose, matching the README's documented "review the plan, confirm" quickstart step) → `raw` → `ingest` → `dbt`. Runs entirely against the small, already-committed `sample_data/health/fixtures/*.csv` — no Kaggle token needed, matching "runs unattended end-to-end on fixture data" from the build order text exactly.
- `reset`: `docker compose down -v` (stops Floci **and drops its named volume** — `FLOCI_STORAGE_MODE=persistent` means a plain `down` alone would leave old S3/Glue state behind) plus removing the local, gitignored `infra/tofu/.terraform/`, `terraform.tfstate*`, and `dbt/iceduck/target/`/`logs/` — so a subsequent `make demo` starts from a genuinely clean slate instead of a local `tofu`/`dbt` cache pointing at resources that no longer exist. Does **not** touch `infra/tofu/.terraform.lock.hcl` (a committed file, not local state).

## Verification

`make demo` was run against the already-provisioned dev Floci instance (this repo's `infra/tofu/terraform.tfstate` already matched reality, so `tofu apply` correctly reported "No changes... Apply complete! Resources: 0 added, 0 changed, 0 destroyed" rather than trying to recreate existing resources) and completed successfully end-to-end:

```
$ make demo
...
No changes. Your infrastructure matches the configuration.
...
Demo complete: raw CSVs -> bronze -> silver -> gold, all real Iceberg tables in Glue (iceduck_bronze/iceduck_silver/iceduck_gold).
```

All 6 bronze entities, 6 silver staging tables, and all 7 gold mart tables (28/28 `dbt build` tests passing) came out with the same row counts already independently verified in phases 6–8 (patients 15, providers 32, organizations 32, medications 124, encounters 358, conditions 73; `dim_date` 15954).

`make reset` was **not** executed as part of this verification — Floci is a single long-running Docker container shared across this machine's git worktrees, not something scoped per-worktree, so `docker compose down -v` would have destroyed the live bronze/silver/gold data built and verified in earlier phases (including data actively being queried via `duckdb -ui` in the same session). Its recipe was reviewed and dry-run (`make -n reset`) instead, confirming the command sequence is correct; a true from-scratch `make reset && make demo` run is a reasonable thing to do once, deliberately, outside an active work session.

## Follow-up: full-dataset runs (2026-09-23)

`s3-upload-raw` previously hardcoded `sample_data/health/fixtures/`, so the full Kaggle dataset `download.py` already fetched into the gitignored `full/` had no supported way in. Added `iceduck s3-upload-raw --dataset {fixtures,full}` (default `fixtures`), a `DATASET ?= fixtures` Makefile variable threaded into `raw`, and a `demo-full` target (`make demo DATASET=full`). Both datasets land at the same `raw/<entity>/<entity>.csv` keys and every layer is drop-and-recreate, so nothing downstream changed. `make demo` stays fixtures-only and token-free.

Verified on the running Floci via `make raw ingest DATASET=full && make dbt`: bronze patients 1171, providers 5855, organizations 1119, medications 42989, encounters 53346, conditions 8376 (matching the CSVs); gold `dim_date` 39364; `dbt build` 28/28 passing. Note that `tests/integration/test_ingest_and_lookup.py` compares bronze to the fixture CSVs, so reload fixtures before `make test-integration`.

## Not in scope for this phase

Build Order step 10 (unit/integration tests, `ICEDUCK_IT=1`-gated) and the remainder of step 11 (`docs/architecture.md`).
