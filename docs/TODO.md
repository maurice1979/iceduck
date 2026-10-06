# TODO

Items explicitly deferred or considered out of scope for now, per `CLAUDE.md` and [`docs/plans/0001-lakehouse-architecture-outline.md`](plans/0001-lakehouse-architecture-outline.md).

## Out of scope for now

- **Orchestration.** No Dagster/Airflow. A Makefile + the `iceduck` CLI drive steps in order; revisit only if the pipeline grows enough dependencies/scheduling needs to justify the added complexity.

## Future exploration

### Athena Iceberg-read support in Floci — fixed upstream, released in Floci 2.2.0

The spike in [`docs/plans/0003-iceberg-glue-spike.md`](plans/0003-iceberg-glue-spike.md) found that Floci's Athena emulation couldn't read genuine Iceberg tables (see [ADR-0007](adr/0007-iceberg-reads-via-glue-resolved-metadata-location.md)). We fixed it upstream in [floci-io/floci#3738](https://github.com/floci-io/floci/pull/3738) (closes [#3737](https://github.com/floci-io/floci/issues/3737)), which shipped in Floci 2.2.0. IceDuck ran a pinned fork build until then ([ADR-0008](adr/0008-pin-floci-fork-for-athena-iceberg-fix.md)) and now uses the official `floci/floci:2.2.0` image ([ADR-0015](adr/0015-official-floci-release-image.md), [`0011-official-floci-image.md`](plans/0011-official-floci-image.md)). The Athena ↔ DuckDB check on `iceduck_gold.fct_encounters` is in [`0006-athena-duckdb-interop.md`](plans/0006-athena-duckdb-interop.md).

Remaining open question: **Floci still has no Iceberg REST Catalog endpoint for Glue** (blocks `dbt-duckdb`'s native write path and a literal DuckDB `ATTACH` to Glue — see ADR-0005 and ADR-0007). Re-check upstream periodically; if it's ever added, revisit `ICEBERG_WRITE_MODE=duckdb_native` as a real option.

### AWS Lake Formation

Floci added Lake Formation support (~Sept 2026): full CRUD for data lake settings, resource registration, permissions, and LF-Tags (`services/lakeformation`), enough for the corresponding Terraform/OpenTofu resources (`aws_lakeformation_data_lake_settings`, `aws_lakeformation_resource`, `aws_lakeformation_permissions`, `aws_lakeformation_lf_tag`) to apply and converge. See [floci's Lake Formation docs](https://github.com/floci-io/floci/blob/main/docs/services/lakeformation.md) and [tracking issue #2310](https://github.com/floci-io/floci/issues/2310).

Caveat: it's CRUD-only, no enforcement — grants are creatable/listable/revocable, but Floci doesn't actually gate Glue catalog reads based on them. `ListPermissions` also returns all granted permissions without caller-based filtering. Useful for practicing the IaC side, not for testing real access-control behavior.

Today, `infra/tofu/iam.tf` grants direct Glue/S3/Athena IAM policy actions to a single role — there's no per-database or per-table governance layer. As a future exploration (extra IaC practice, not required for the pipeline to work):

- Register the lakehouse S3 bucket as a Lake Formation resource.
- Express access to `iceduck_bronze`/`iceduck_silver`/`iceduck_gold` as Lake Formation database/table grants instead of (or alongside) the current IAM policy actions — closer to how a real governed lakehouse is set up on AWS.
- Since enforcement isn't emulated, this would be a modeling/IaC exercise rather than something with observable runtime effect against Floci — worth calling out explicitly if pursued, so it isn't mistaken for an access-control feature that's actually being tested.

Record the decision (pursue or skip, and why) in a new `docs/plans/000X-*.md` if this is ever picked up, per the project's convention of documenting *why* non-trivial decisions were made.

### A GUI for browsing tables (get users familiar with the data) — done, via floci-dash

DBeaver's Amazon Athena JDBC driver got real progress in one session: `AthenaEndpoint`/`S3Endpoint`/`WorkGroup` driver properties confirmed reaching Floci and actually running a query — but then hit a wall. `ResultFetcher=auto` (the default) needs a `.csv.metadata` S3 sidecar file that Floci's Athena emulation doesn't produce; the alternative, `ResultFetcher=GetQueryResultsStream`, avoids that but calls AWS's separate streaming API endpoint, which needed `AthenaStreamingEndpoint` pointed at Floci too — left untested whether Floci implements that streaming API at all. **Parked, not proven impossible**, but superseded by the option below.

Floci's own official `floci-ui` console (bundled with the Floci install, runs at `http://localhost:4500`) was also checked — it's a service-status dashboard (which of Floci's 21 emulated services are available, resource counts per service), with no Glue/Athena-specific pages at all. Not useful for this.

**Adopted: [floci-dash](https://github.com/ofsazib/floci-dash)** — a third-party, Docker-based, AWS-console-style admin dashboard for Floci (React + Cloudscape frontend). Real Glue database/table browsing with schema drill-down, and — better than its own docs suggested — a working "Run Query" Athena SQL editor, not just execution-management. Two non-obvious things needed to actually get results back, both confirmed live against this project's data and worth knowing before using it:

1. **Strip trailing semicolons from every query.** Floci's Athena emulation executes queries by wrapping them as `COPY (<your SQL>) TO 's3://...'` via its internal `floci-duck` sidecar, and doesn't strip a trailing `;` before embedding it — `select * from dim_organization limit 10;` fails with `Parser Error: syntax error at or near ";"`; the same query without the `;` succeeds. **This is a genuine Floci bug** (same category of finding as ADR-0007/0008), not a floci-dash issue — worth fixing upstream if anyone picks that up, same pattern as the Iceberg-read fix in ADR-0008.
2. **Fill in the "Database" field, or fully-qualify table names.** floci-dash's Run Query form has a "Database (optional)" field that isn't actually optional in practice — leaving it blank and using a bare table name (`select * from dim_organization`) fails with `Catalog Error: Table with name dim_organization does not exist!` (it suggests the fix itself: `iceduck_gold.dim_organization`). Either set Database to `iceduck_bronze`/`iceduck_silver`/`iceduck_gold` as appropriate, or fully-qualify every table reference in the SQL.

Setup: see the README's "Browsing data with floci-dash" section.

The `iceduck` CLI + local-persistent-DuckDB-file idea (pre-resolve every table into named views, launch `duckdb -ui` against it, no third-party tool) remains a viable no-workarounds alternative if floci-dash ever stops being satisfactory — not built, since floci-dash covers the need today.

### dbt docs site — done

`dbt docs generate` + `dbt docs serve` renders the full model DAG (bronze sources → 6 staging models → 7 mart models) plus schema and test coverage. See [`docs/plans/0009-dbt-docs.md`](plans/0009-dbt-docs.md) — two real bugs were found and fixed getting this working (a hard `var()` lookup blocking `dbt docs generate` entirely, and the DAG initially rendering as 13 disconnected nodes since the project's custom `iceberg_source()` macro bypasses `ref()`/`source()`). Run via `make dbt-docs`.

### CI — done (offline checks)

GitHub Actions runs lint, format, mypy, Python unit tests and `make dbt-check` (dbt parse, dbt unit tests, seeds) on every PR and push to `main` — see [ADR-0014](adr/0014-ci-offline-checks.md). Still open: a job that starts Floci in Docker to run `make demo` + the integration tests and the dbt data tests on real models. No CD.

### Analyst-facing dashboard — done

Built with Streamlit + Plotly, reading `iceduck_gold` directly via DuckDB (resolve-then-`iceberg_scan`, same as everywhere else — no Athena, deliberately, given the real Athena bugs hit with DBeaver and floci-dash above). Apache Superset was considered and rejected — its own Postgres+Redis footprint would be the first real architectural inconsistency in an otherwise deliberately minimal project (ADR-0004). See [ADR-0011](adr/0011-streamlit-dashboard-duckdb-not-athena.md) for the full decision and [`docs/plans/0010-streamlit-dashboard.md`](plans/0010-streamlit-dashboard.md) for the build record. Run via `make dashboard`.
