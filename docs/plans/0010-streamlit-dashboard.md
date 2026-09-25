# 0010 — Streamlit Dashboard

Status: applied
Date: 2026-09-18

See [ADR-0011](../adr/0011-streamlit-dashboard-duckdb-not-athena.md) for the tool choice (Streamlit over Superset) and read-path decision (DuckDB direct, not Athena).

## Context

Last of the three follow-on items recorded in `docs/TODO.md`. Built after the GUI (floci-dash) and dbt docs items, deliberately — an analyst-facing dashboard for exploring gold-layer data, the biggest and most novel piece of the three.

## What was built

- `pyproject.toml`: `[project.optional-dependencies] dashboard = ["streamlit", "plotly"]` (added via `uv add --optional dashboard streamlit plotly`, resolved to streamlit 1.64.0 / plotly 7.1.0) — kept optional so the core pipeline install stays lean.
- `dashboard/app.py` (new): a single-file Streamlit app.
  - `st.cache_resource`-wrapped DuckDB connection (installs `httpfs`/`iceberg`, creates the `floci_s3` secret — same values used everywhere else in this project).
  - `st.cache_data(ttl=300)`-wrapped `resolve_metadata_locations()` call (reusing `src/iceduck/core/glue_lookup.py` and `GLUE_DATABASE_GOLD` from `src/iceduck/core/settings.py` directly, no new core module) plus a sidebar "Refresh data" button that clears both caches, so a `build-gold` rerun doesn't leave the dashboard pinned to a stale snapshot.
  - KPI row (patients, encounters, organizations, total claim cost), 5 Plotly charts (encounters over time, by class, cost by organization, top 10 conditions, top 10 medications), and a raw-table browser (dropdown over all 7 gold tables, `st.dataframe`).
- `Makefile`: `dashboard` target.
- `README.md`: new "Dashboard" section.
- `docs/adr/0011-streamlit-dashboard-duckdb-not-athena.md`: the tool/read-path decision record.

## Verification

Streamlit only executes the app script inside a websocket session, not on a plain HTTP GET — so a `curl` against the running server only proves the static shell loads, not that the actual data logic (queries, merges, aggregations) works. Verified server startup cleanly (`uv run --extra dashboard streamlit run dashboard/app.py --server.headless true`, confirmed `200` via `curl localhost:8501`, no exceptions in the server log), **then separately ran the exact same data logic standalone** (a throwaway script mirroring `app.py`'s queries/transforms line for line, outside any Streamlit machinery) against live gold-layer data:

```
dim_patient: 15 rows       fct_encounters: 358 rows
dim_provider: 32 rows      fct_medications: 124 rows
dim_organization: 32 rows  fct_conditions: 73 rows
dim_date: 15954 rows

KPIs: Patients=15, Encounters=358, Organizations=32, Total claim cost=$46,187.61
Encounters by class: ambulatory 147, wellness 137, outpatient 56, emergency 13, urgentcare 3, inpatient 2
Top condition: Viral sinusitis (disorder) / Normal pregnancy (13 each)
Top medication: Hydrochlorothiazide 25 MG Oral Tablet (49)
ALL CHECKS PASSED
```

All row counts match every prior verification this session (bronze/silver/gold reconciliation, Athena/DuckDB interop). Visual confirmation of the actual rendered charts (client-side React, can't be checked via curl) is left to the user opening `make dashboard` in a browser.

## Follow-up: SQL console tab (2026-09-24)

Prototyping a dbt model meant `duckdb -ui` plus a manual `aws glue get-table … metadata_location` lookup per table. The dashboard is now two tabs (`st.tabs`): the existing dashboard (body moved into `render_dashboard()`, unchanged) and a **SQL console** (`dashboard/sql_console.py`).

- `src/iceduck/core/duckdb_session.py` (new, shared so a future `make sql` DuckDB-UI target can reuse it): `connect_floci()` (the S3-secret setup previously inline in `app.py`), and `register_lake_views(con)`, which creates `bronze.*`/`silver.*`/`gold.*` views over `iceberg_scan(<metadata_location>)`. Tables come from `glue_lookup.list_metadata_locations()` (paginated `GetTables`, non-Iceberg tables skipped), not a hardcoded list, so new marts appear without code changes.
- The console has its **own** cached DuckDB connection, so a stray `DROP`/`SET` can't affect the dashboard; views are pinned to the snapshot current at creation, and the sidebar "Refresh data" re-pins them. Results are capped at 10,000 rows (`limit` pushed into the query, not fetched then cut); `duckdb.Error` renders inline via `st.error`. It is deliberately not a sandbox — any SQL runs, including writes via the S3 secret — acceptable for a local dev tool.

Verified headlessly (`streamlit.testing.v1.AppTest`) against the live full-dataset lake: 20 views registered (6 bronze, 6 silver, 8 gold); `select * from gold.fct_readmissions` → 1,838 rows; a silver count, a gold join, an unknown table (inline error, no exception), a DDL statement ("OK"), and a 20,000-row query (truncated to 10,000) all behave as expected; the dashboard tab still renders all 7 KPIs. Unit tests cover the view DDL builder and the Glue pagination.

## Not in scope for this phase

Filters (date range, encounter class, organization) on the dashboard itself — the current scope is KPIs + fixed charts + a raw browser, not an interactive filterable BI tool; a reasonable future addition if the dashboard proves useful enough to invest further.
