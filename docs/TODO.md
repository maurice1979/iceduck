# TODO

Items explicitly deferred or considered out of scope for now, per `CLAUDE.md` and [`docs/plans/0001-lakehouse-architecture-outline.md`](plans/0001-lakehouse-architecture-outline.md).

## Out of scope for now

- **CI/CD.** No pipeline exists yet (no GitHub Actions, etc.). Revisit once the core pipeline (ingestion → dbt → marts) is built and there's something meaningful to run on every push.
- **Orchestration.** No Dagster/Airflow. A Makefile + the `iceduck` CLI drive steps in order; revisit only if the pipeline grows enough dependencies/scheduling needs to justify the added complexity.

## Pending upstream merge

- **[ ] Switch `docker/docker-compose.yml`'s `floci` service back to the official `floci/floci` image once [floci-io/floci#3738](https://github.com/floci-io/floci/pull/3738) merges and ships in a release.** We're currently building Floci from our own fork's commit (`maurice1979/floci@feat/athena-iceberg-table-reads`) instead of pulling the official image, specifically to get Athena's Iceberg-table support before it's released upstream — see [ADR-0008](adr/0008-pin-floci-fork-for-athena-iceberg-fix.md) for the full rationale, the pin commit, and the exact revert steps. Don't forget: reprovision infra (`rm infra/tofu/terraform.tfstate* && tofu apply`) after switching back, since a fresh image means fresh Floci-side state.

## Future exploration

### Athena Iceberg-read support in Floci — fixed upstream, pending merge

The spike in [`docs/plans/0003-iceberg-glue-spike.md`](plans/0003-iceberg-glue-spike.md) found that Floci's Athena emulation couldn't read genuine Iceberg tables — it format-sniffed `StorageDescriptor.InputFormat`/`SerializationLibrary` and fell back to `read_csv_auto`, which failed outright on Iceberg's Parquet data files. See [ADR-0007](adr/0007-iceberg-reads-via-glue-resolved-metadata-location.md) for the full original finding.

This has since been fixed and submitted upstream as [floci-io/floci#3738](https://github.com/floci-io/floci/pull/3738) (fixing [issue #3737](https://github.com/floci-io/floci/issues/3737)) — implemented by Claude, verified independently twice against live instances (including reproducing the exact orphaned-file/multi-snapshot scenario from ADR-0007 and confirming correct manifest-based resolution, not a glob). IceDuck currently runs on a pinned fork build with this fix included — see the "Pending upstream merge" item above and [ADR-0008](adr/0008-pin-floci-fork-for-athena-iceberg-fix.md).

**Build Order step 8, done**: with the gold layer built, this was verified against real project data, not just the spike's throwaway table — an Athena query against `iceduck_gold.fct_encounters` and a fresh DuckDB `iceberg_scan` session against the same table returned identical row counts and identical row content. See [`docs/plans/0006-athena-duckdb-interop.md`](plans/0006-athena-duckdb-interop.md). The only remaining item is the "Pending upstream merge" one above — switching off the pinned fork once #3738 ships in a release.

Remaining open question, independent of whether/when #3738 merges: **Floci still has no Iceberg REST Catalog endpoint for Glue** (blocks `dbt-duckdb`'s native write path and a literal DuckDB `ATTACH` to Glue — see ADR-0005 and ADR-0007). Re-check upstream periodically; if it's ever added, revisit `ICEBERG_WRITE_MODE=duckdb_native` as a real option.

### AWS Lake Formation

Floci added Lake Formation support (~Sept 2026): full CRUD for data lake settings, resource registration, permissions, and LF-Tags (`services/lakeformation`), enough for the corresponding Terraform/OpenTofu resources (`aws_lakeformation_data_lake_settings`, `aws_lakeformation_resource`, `aws_lakeformation_permissions`, `aws_lakeformation_lf_tag`) to apply and converge. See [floci's Lake Formation docs](https://github.com/floci-io/floci/blob/main/docs/services/lakeformation.md) and [tracking issue #2310](https://github.com/floci-io/floci/issues/2310).

Caveat: it's CRUD-only, no enforcement — grants are creatable/listable/revocable, but Floci doesn't actually gate Glue catalog reads based on them. `ListPermissions` also returns all granted permissions without caller-based filtering. Useful for practicing the IaC side, not for testing real access-control behavior.

Today, `infra/tofu/iam.tf` grants direct Glue/S3/Athena IAM policy actions to a single role — there's no per-database or per-table governance layer. As a future exploration (extra IaC practice, not required for the pipeline to work):

- Register the lakehouse S3 bucket as a Lake Formation resource.
- Express access to `iceduck_bronze`/`iceduck_silver`/`iceduck_gold` as Lake Formation database/table grants instead of (or alongside) the current IAM policy actions — closer to how a real governed lakehouse is set up on AWS.
- Since enforcement isn't emulated, this would be a modeling/IaC exercise rather than something with observable runtime effect against Floci — worth calling out explicitly if pursued, so it isn't mistaken for an access-control feature that's actually being tested.

Record the decision (pursue or skip, and why) in a new `docs/plans/000X-*.md` if this is ever picked up, per the project's convention of documenting *why* non-trivial decisions were made.

### A GUI for browsing tables (get users familiar with the data)

DBeaver's Amazon Athena JDBC driver got real progress in one session: `AthenaEndpoint`/`S3Endpoint`/`WorkGroup` driver properties confirmed reaching Floci and actually running a query — but then hit a wall. `ResultFetcher=auto` (the default) needs a `.csv.metadata` S3 sidecar file that Floci's Athena emulation doesn't produce; the alternative, `ResultFetcher=GetQueryResultsStream`, avoids that but calls AWS's separate streaming API endpoint, which needed `AthenaStreamingEndpoint` pointed at Floci too — left untested whether Floci implements that streaming API at all. **Parked, not proven impossible.**

What works today (`duckdb -ui`, documented in the README) requires manually resolving each table's `metadata_location` via `aws glue get-table` before every query — real, but no catalog tree, no click-to-browse.

Three directions, either worth picking up:
- **Cheap, reuses proven mechanism**: a small `iceduck` CLI command that resolves every bronze/silver/gold table's current metadata location and creates named views in a local persistent DuckDB file, then launches `duckdb -ui` against it. Turns the existing resolve-then-`iceberg_scan` pattern (ADR-0007) into a real catalog tree without any new tool.
- **Finish the DBeaver path**: pick the `AthenaStreamingEndpoint` experiment back up and see whether Floci's streaming API works at all; if not, that's a genuine Floci gap worth documenting (in the spirit of ADR-0007/0008) rather than a DBeaver misconfiguration.
- **[floci-dash](https://github.com/ofsazib/floci-dash)**: a Docker-based, AWS-console-style admin dashboard for Floci (React + Cloudscape frontend), with real Glue support (database/table browsing, schema drill-down) and Athena support — though its documented Athena feature set is "work groups, query executions (list/get/stop), data catalogs, databases, table metadata," which reads as execution-management rather than a SQL editor for submitting new ad hoc queries. Worth trying hands-on for browsing the Glue catalog structure (what tables/columns exist across `iceduck_bronze`/`_silver`/`_gold`) even if it doesn't end up replacing DuckDB for actually querying row data.

### dbt docs site

`dbt docs generate` + `dbt docs serve` renders a full model DAG (bronze → staging → marts) plus schema and test coverage, sourced from the project's existing `dbt/iceduck/models/staging/health/_health__models.yml` and `dbt/iceduck/models/marts/core/_core__models.yml` — both already exist with real test coverage, just no `description:` fields written yet. Structurally ready today; cheapest of these three items to pick up. Would need: model/column descriptions added to those two YAML files, then `dbt docs generate && dbt docs serve` (maybe worth a `make dbt-docs` target).

### Analyst-facing dashboard

The most involved of these three — needs a real tool choice (e.g. Streamlit+DuckDB, Metabase, Superset, and Evidence.dev are the realistic candidates for a local/portfolio setup) and its own read-path design, since whatever connects to the data hits the same Glue-resolve-then-`iceberg_scan` constraint (ADR-0007) as everything else in this project — not a given that every candidate tool supports that cleanly. Should get its own ADR/plan doc when actually picked up rather than being designed inline here.
