# ADR-0011: Analyst dashboard is Streamlit, reading DuckDB directly — not Superset, not Athena

Status: Accepted
Date: 2026-09-18

## Context

Last item on the roadmap (`docs/TODO.md`): a dashboard for exploring gold-layer data, deliberately picked last since it's the biggest, most novel piece — needing both a tool choice and a read-path design, unlike the other two follow-on items (dbt docs, floci-dash), which reused existing mechanism outright.

**Tool choice.** Apache Superset was the first candidate discussed — a real, resume-recognized BI tool. But it needs its own Postgres (metadata store) and Redis (caching/async query execution) — a materially heavier footprint than anything else in this project, which has been deliberately minimal throughout: Floci is the only infrastructure container (ADR-0002), there's no orchestrator (ADR-0004), and "no separate metadata database" is stated as an explicit design principle for the medallion layers themselves. Adding Superset's own multi-container stack on top would be the first real architectural inconsistency in the project, not a natural extension of it.

**Read path.** Whatever tool was picked, "connect it to the data" needed a real decision too — and this session had already hit genuine, reproducible bugs in two separate Athena-based tools: DBeaver's Athena JDBC driver (needs a `.csv.metadata` S3 sidecar Floci's Athena emulation doesn't produce), and floci-dash's Athena query editor (a trailing-semicolon parser bug in how Floci wraps queries — see `docs/TODO.md` and ADR-0007's update). A third Athena-based integration would very plausibly hit a third variant of the same underlying gap (Floci's Athena emulation being the least mature part of Floci relative to Glue/S3, per the pattern established across ADR-0007/0008).

## Decision

- **Streamlit**, not Superset: single Python process, no extra infrastructure, matches the project's existing minimalism (ADR-0004's reasoning extends naturally here — add complexity only when something concrete justifies it, and nothing here does).
- **DuckDB directly, not Athena**: the dashboard (`dashboard/app.py`) reuses the exact resolve-then-`iceberg_scan` mechanism every other read path in this project already uses (ADR-0007) — `resolve_metadata_locations()` (`src/iceduck/core/glue_lookup.py`) to find each gold table's current `metadata_location`, then `iceberg_scan()` in a DuckDB session, cached across Streamlit reruns via `st.cache_resource`/`st.cache_data`. No new read mechanism, no Athena, no new bug surface — this was a deliberate choice to avoid repeating the DBeaver/floci-dash experience a third time.
- **Plotly** for charts (via `plotly.express`) over Streamlit's built-in chart types — nicer, more interactive, still a simple API, and a reasonable portfolio-quality touch.
- Dependencies kept in a `[project.optional-dependencies] dashboard` extra (`pyproject.toml`), not the core dependency list — someone running just the pipeline doesn't need Streamlit/Plotly pulled in.

## Consequences

- The dashboard has zero new bug surface beyond what's already proven working — its correctness was verified by running the exact same query/transform logic standalone (outside Streamlit's session machinery) against live data before considering it done; see `docs/plans/0010-streamlit-dashboard.md`.
- No live catalog browsing/click-to-explore-schema the way floci-dash's Glue pages give — this dashboard is analysis-first (KPIs, charts) with a raw-table browser tab, not a catalog explorer. floci-dash remains the answer for "what tables/columns exist"; this is the answer for "what does the data say."
- If a genuinely BI-tool-operating story becomes valuable later (e.g. specifically wanting to demonstrate Superset on a resume), that's still available as a later addition — this decision doesn't preclude it, it just doesn't default to the heavier option without a concrete reason.
