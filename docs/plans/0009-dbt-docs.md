# 0009 — dbt Docs Site

Status: applied
Date: 2026-09-18

## Context

First of three follow-on items recorded in `docs/TODO.md` (GUI browsing, dbt docs, dashboard), picked as the starting point because the project already had real structure to document: 13 models across staging and marts, all with `unique`/`not_null`/`relationships` test coverage, just no `description:` fields. `dbt docs generate` + `dbt docs serve` turns that into a browsable site — the model DAG plus per-model/column documentation and test coverage.

Two real problems were found and fixed along the way, not assumed away — both are the kind of thing that only shows up once you actually run the thing, consistent with how every other phase of this project was verified.

## What was found and fixed

**1. `dbt docs generate` hard-failed before any docs existed.** Building `manifest.json` requires *compiling* every model's Jinja — including the custom `iceberg_source(layer, entity)` macro (`dbt/iceduck/macros/iceberg_source.sql`), which does `var(layer ~ "_metadata_locations")[entity]`. That var is only ever supplied by `iceduck build-silver`/`build-gold`'s `--vars` flag for a real run; running `dbt docs generate` on its own hit `Required var 'silver_metadata_locations' not found`. Fixed by giving the macro a default: `var(layer ~ "_metadata_locations", {}).get(entity, "")` — compiles fine (to `iceberg_scan('')`) when no vars are supplied, while real builds are unaffected since the real vars dict always has the key. Trade-off accepted: a genuinely missing/misnamed key during an actual build now fails at *run* time (the empty-string `iceberg_scan('')` errors when DuckDB tries to execute it) instead of at *compile* time with a clearer message — acceptable for what this buys (docs generation that needs no live Floci at all).

**2. The DAG was 13 disconnected nodes, not a lineage graph.** Every model reads its source via `{{ iceberg_source(...) }}`, not dbt's own `ref()`/`source()` — necessarily, since Floci has no Iceberg REST Catalog endpoint for a live `ATTACH` (ADR-0007), so every read has to resolve a Glue metadata pointer at runtime instead. But dbt builds its dependency graph by statically detecting `ref()`/`source()` calls in each model's raw Jinja — since none of our models called those, `manifest.json`'s `depends_on` was `[]` for every single model. The headline reason to build this at all (a visual DAG) would have rendered as nothing but 13 disconnected boxes.

Fixed with the standard dbt pattern for dependency-only registration: `{% do source(...) %}` / `{% do ref(...) %}` statements added near the top of each model, purely to register the graph edge — their return value is discarded (`do`, not `{{ }}` output), the actual data read is still `iceberg_source(...)` below. Added `dbt/iceduck/models/staging/health/_health__sources.yml` declaring the 6 bronze tables as a `source` (so staging models have something to point at — bronze itself isn't a dbt model, it's written by `pyiceberg` outside dbt entirely), then one `{% do source('bronze', '<entity>') %}` per staging model and one or more `{% do ref('stg_<entity>') %}` per mart model (`dim_date` needs three, since it reads `stg_encounters`/`stg_medications`/`stg_conditions`).

Verified via `manifest.json`'s `depends_on.nodes` directly — every model now shows the correct real edges (`dim_date` ← `stg_encounters`, `stg_medications`, `stg_conditions`; every staging model ← its bronze source; every other mart ← its one silver source).

## What was added

- `description:` on all 13 models plus the ~15 columns that already carry tests (`dbt/iceduck/models/staging/health/_health__models.yml`, `dbt/iceduck/models/marts/core/_core__models.yml`) — not full column-by-column coverage (100+ columns total), out of proportion for the "start cheap" item.
- `dbt/iceduck/models/staging/health/_health__sources.yml` (new) — the bronze source declaration described above.
- `Makefile`: `dbt-docs` target (`dbt docs generate && dbt docs serve`).
- `README.md`: pointer under a new "dbt docs" section.

## Verification

```
$ dbt docs generate --profiles-dir .
Found 13 models, 34 data tests, 6 sources, 501 macros
Building catalog
Catalog written to .../target/catalog.json
```
`catalog.json` came back empty (`0 nodes, 0 sources`) — confirmed by inspecting the file directly. This is the same root cause ADR-0010 already documented for `dbt test`: `profiles.yml` uses `path: ":memory:"` and every model is `external`-materialized, so nothing persists across the separate process `dbt docs generate` runs in. Doesn't matter for what this feature actually delivers: `manifest.json` — the DAG, descriptions, and test coverage — is pure static compilation and needs no live catalog at all, confirmed by inspecting it directly (all 13 models present, correct descriptions, correct dependency edges) and by actually serving the site (`dbt docs serve --port 8180`, `curl` returned `200` and a real ~750KB `manifest.json` over HTTP).

Regression-checked that the `{% do source/ref %}` additions don't affect the real pipeline: re-ran `iceduck build-silver` and `iceduck build-gold` after all changes — all 19/19 and 28/28 dbt build+test steps still passed, every row count unchanged from prior verification.

## Not in scope for this phase

Full column-by-column documentation (only tested columns got descriptions). The remaining two `docs/TODO.md` items (GUI browsing, dashboard).
