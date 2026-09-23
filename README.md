# IceDuck

A modern, from-scratch lakehouse built entirely on open-source tooling — a Data Engineering portfolio project focused on learning and practicing real lakehouse architecture, not just wiring up a demo.

The name reflects the core of the stack: **Ice**berg (the table format) on **Duck**DB (the query engine).

## Why this project

Most "lakehouse" portfolio projects stop at DuckDB + Parquet + dbt. This one goes further: it builds a genuine open **table format** (Apache Iceberg) on a real **catalog** (AWS Glue Data Catalog), provisioned as actual infrastructure (OpenTofu) against a local AWS emulator (Floci) — so the same code and IaC should, with minimal changes, work against real AWS. The explicit goals are to:

- Build a real medallion (bronze/silver/gold) lakehouse on Iceberg, not just files
- Get hands-on practice with OpenTofu/Terraform-style infrastructure-as-code
- Demonstrate genuine multi-engine interoperability: the same physical tables are real Iceberg tables in a real catalog, not an engine-specific format, and are readable from both a fresh **DuckDB** session and **AWS Athena** (emulated) — verified end-to-end against a real gold table (Build Order step 8, [`docs/plans/0006-athena-duckdb-interop.md`](docs/plans/0006-athena-duckdb-interop.md)); see the note in the Architecture section on the pinned, not-yet-merged upstream fix this depends on
- Keep everything reproducible in Docker, with no cloud account or cost required to run it

## Architecture

The full narrative — why every write goes through `pyiceberg`, how reads resolve a Glue-held metadata pointer instead of a live `ATTACH`, and how the multi-engine interoperability claim was actually verified, not just asserted — is in [`docs/architecture.md`](docs/architecture.md). A draw.io diagram of the pipeline is at [`docs/architecture-diagram.drawio`](docs/architecture-diagram.drawio) (open at [diagrams.net](https://app.diagrams.net/) or with a draw.io editor extension).

```
raw CSV (S3 landing)
   │
   ▼
bronze (Iceberg, Glue DB: iceduck_bronze)     ← written via pyiceberg
   │
   ▼   dbt Fusion (DuckDB, external Parquet) + a pyiceberg publish step
silver (Iceberg, Glue DB: iceduck_silver)     ← staging models (1:1 with bronze, built)
   │
   ▼
gold (Iceberg, Glue DB: iceduck_gold)         ← dimensional marts (facts + dims, built)
   │
   ├── queryable from a fresh DuckDB session (via iceberg_scan on the metadata
   │   location Glue resolves — not a live catalog ATTACH; Floci doesn't
   │   implement Glue's Iceberg REST Catalog endpoint, see ADR-0007)
   └── queryable from Athena (emulated) — works today via a pinned fork build
       with an unmerged upstream fix, see ADR-0008; verified against a real
       gold table (fct_encounters, 358/358 rows matching a fresh DuckDB read
       exactly, same content) — see docs/plans/0006-athena-duckdb-interop.md
```

All storage lives in one S3 bucket (emulated via Floci); AWS Glue is the **single catalog** for every layer — there is no separate metadata database. Every write path (bronze, silver, and gold) goes through `pyiceberg`'s `GlueCatalog`, not `dbt-duckdb`'s native Glue-Iceberg materialization — verified via a spike, see [ADR-0005](docs/adr/0005-bronze-pyiceberg-silver-gold-dbt-duckdb.md) and [ADR-0007](docs/adr/0007-iceberg-reads-via-glue-resolved-metadata-location.md). See [`docs/plans/0001-lakehouse-architecture-outline.md`](docs/plans/0001-lakehouse-architecture-outline.md) for the full design rationale, including why DuckLake was considered and dropped in favor of this Iceberg-on-Glue design.

**Note on Athena support**: Floci's Athena emulation couldn't read genuine Iceberg tables out of the box (ADR-0007). We found, fixed, and submitted the root cause upstream — [floci-io/floci#3738](https://github.com/floci-io/floci/pull/3738) — and `docker/docker-compose.yml` currently builds Floci from that fix's commit rather than the official image so this project actually benefits from it now, pending merge (ADR-0008, with a revert TODO in `docs/TODO.md`). With the gold layer built, this was verified for real, not just theoretically: an Athena query against `iceduck_gold.fct_encounters` and a fresh DuckDB `iceberg_scan` session against the same table return identical row counts and identical row content — see [`docs/plans/0006-athena-duckdb-interop.md`](docs/plans/0006-athena-duckdb-interop.md).

## Tech stack

| Concern | Tool |
|---|---|
| Query engine / transform compute | [DuckDB](https://duckdb.org/) |
| Transformation framework | [dbt](https://www.getdbt.com/) — the Fusion engine (`dbt` v2, a standalone binary, not the `dbt-core`/`dbt-duckdb` Python packages) |
| Table format | [Apache Iceberg](https://iceberg.apache.org/) |
| Catalog | AWS Glue Data Catalog |
| Local AWS emulation | [Floci](https://github.com/floci-io/floci) |
| Infrastructure as code | [OpenTofu](https://opentofu.org/) |
| Containerization | Docker / Docker Compose |
| Dataset | Synthetic EHR data via [Synthea™](https://synthetichealth.github.io/synthea/) ([Kaggle](https://www.kaggle.com/datasets/lucague/hospital-ehr-data-1171-patients-15-tables)) — patients, providers, organizations, medications, encounters, conditions |
| Package management | [uv](https://docs.astral.sh/uv/) |

## Status

The full medallion pipeline is built and verified end-to-end: infra, bronze ingestion (6 EHR entities), the silver staging layer, and the gold dimensional model (`dim_patient`, `dim_provider`, `dim_organization`, `dim_date`, `fct_encounters`, `fct_medications`, `fct_conditions`) — all real Iceberg tables in Glue, with row counts reconciled at every layer. The project's central multi-engine interoperability claim is also verified for real: Athena and a fresh DuckDB session reading the same gold table return identical results (Build Order step 8). Remaining build-order items are polish: a Makefile wrapper for the full pipeline and unit/integration tests. See [`docs/plans/`](docs/plans/) for the phased build order and design decisions as they're made.

## Repository structure

```
docker/          Docker Compose (Floci, the local AWS emulator)
infra/tofu/      OpenTofu IaC: S3 bucket, IAM, Glue databases, Athena workgroup
scripts/         Standalone spike/verification scripts (not part of the pipeline)
src/iceduck/     Python CLI + core logic (ingestion, Iceberg/Glue helpers, settings)
products/         Per-entity ingestion config (patients, providers, organizations, ...)
dbt/iceduck/      dbt project: staging → intermediate → marts
sample_data/      Dataset download + small committed fixtures for fast local runs
docs/             Architecture notes, ADRs, and phased design/build plans
tests/            Unit + integration tests
```

## Getting started

The infrastructure layer (S3 bucket, IAM role/policy, Glue databases, Athena workgroup), raw data landing, and the full bronze → silver → gold pipeline are all runnable today — see the build order in `docs/plans/0001-lakehouse-architecture-outline.md`.

Prerequisites: [Docker](https://www.docker.com/), [uv](https://docs.astral.sh/uv/), [OpenTofu](https://opentofu.org/) (`brew install opentofu`), AWS CLI (`brew install awscli`), and the dbt Fusion engine (`brew install dbt`) — see [ADR-0013](docs/adr/0013-dbt-fusion-engine.md).

**Quickest path** — the whole pipeline, unattended, on the small fixture dataset already committed to the repo (no Kaggle token needed):

```sh
cp .env.template .env   # adjust if needed; already gitignored
make demo                # floci up -> infra apply -> raw -> bronze -> silver -> gold
```

`make reset` tears it back down (stops Floci **and drops its data**, clears local `tofu`/`dbt` state) so `make demo` can be re-run from a clean slate. The steps below walk through what `demo` does, one at a time.

```sh
cp .env.template .env          # adjust if needed; already gitignored
make floci-up                  # start Floci (the local AWS emulator)
make infra-init                # tofu init
make infra-apply               # tofu apply — review the plan, confirm
```

Verify it worked:

```sh
export AWS_ACCESS_KEY_ID=floci AWS_SECRET_ACCESS_KEY=floci \
       AWS_DEFAULT_REGION=eu-west-1 AWS_ENDPOINT_URL=http://localhost:4566

aws s3 ls                                        # iceduck-lakehouse
aws glue get-database --name iceduck_bronze       # (and _silver, _gold)
aws athena get-work-group --work-group iceduck

# Optional: prove real Iceberg reads work through both engines
uv run python scripts/glue_iceberg_spike.py
```

See [`docs/plans/0002-opentofu-infra.md`](docs/plans/0002-opentofu-infra.md) for the infra design decisions and verification record.

Land the sample EHR data:

```sh
uv run python sample_data/health/download.py   # requires a Kaggle API token at ~/.kaggle/access_token
uv run iceduck s3-upload-raw                   # the committed 15-patient fixtures (default)
uv run iceduck s3-upload-raw --dataset full    # or the whole downloaded dataset

aws s3 ls s3://iceduck-lakehouse/raw/patients/   # (and providers, organizations, medications, encounters, conditions)
```

`download.py` writes the full dataset to `sample_data/health/full/` (gitignored) and regenerates the committed `fixtures/` subset from it:

| entity | fixtures | full |
|---|---:|---:|
| patients | 15 | 1,171 |
| encounters | 358 | 53,346 |
| medications | 124 | 42,989 |
| conditions | 73 | 8,376 |
| providers | 32 | 5,855 |
| organizations | 32 | 1,119 |

The full dataset is ~29 MB of CSV. Both land at the same `raw/<entity>/<entity>.csv` keys and every layer is drop-and-recreate, so switching is just a re-upload plus a rebuild. `make demo-full` (or `make demo DATASET=full`, or `make raw DATASET=full` on an already-running stack) runs the whole pipeline on it. `make test-integration` compares bronze against the fixture CSVs, so run `make raw ingest` (fixtures) before it if you loaded the full dataset.

See [ADR-0009](docs/adr/0009-switch-dataset-to-synthea-ehr.md) for why this dataset was chosen over the originally-planned Olist e-commerce data.

Build bronze, then silver, then gold:

```sh
uv run iceduck ingest-all     # raw/ CSVs -> real Iceberg tables in iceduck_bronze (pyiceberg)
uv run iceduck build-silver   # dbt staging models -> real Iceberg tables in iceduck_silver
uv run iceduck build-gold     # dbt marts (dims + facts) -> real Iceberg tables in iceduck_gold

aws glue get-tables --database-name iceduck_bronze --query 'TableList[].Name'
aws glue get-tables --database-name iceduck_silver --query 'TableList[].Name'
aws glue get-tables --database-name iceduck_gold --query 'TableList[].Name'
```

See [`docs/plans/0004-dbt-silver-layer.md`](docs/plans/0004-dbt-silver-layer.md) and [ADR-0010](docs/adr/0010-dbt-silver-write-and-read-mechanism.md) for how the silver (and, by the same mechanism, gold) read/write path works (DuckDB can't live-attach to Glue against Floci — see ADR-0007 — so dbt resolves each source table's metadata location via Glue and reads it with `iceberg_scan`; writes go out as external Parquet, then a `pyiceberg` publish step promotes that into a real Iceberg table, mirroring bronze). Gold's star schema (`dim_patient`, `dim_provider`, `dim_organization`, `dim_date` + `fct_encounters`, `fct_medications`, `fct_conditions`) is documented in [`docs/plans/0005-dbt-gold-layer.md`](docs/plans/0005-dbt-gold-layer.md).

Inspect any table directly with DuckDB (no catalog `ATTACH` — see ADR-0007 for why):

```sh
duckdb -ui   # or the duckdb CLI; either way:
```
```sql
INSTALL httpfs; LOAD httpfs; INSTALL iceberg; LOAD iceberg;
CREATE SECRET floci_s3 (TYPE s3, KEY_ID 'floci', SECRET 'floci', REGION 'eu-west-1',
                         ENDPOINT 'localhost:4566', URL_STYLE 'path', USE_SSL false);
-- metadata_location from: aws glue get-table --database-name iceduck_silver --name stg_patients \
--                          --query 'Table.Parameters.metadata_location' --output text
SELECT * FROM iceberg_scan('<metadata_location>') LIMIT 10;
```

## Browsing data with floci-dash

[floci-dash](https://github.com/ofsazib/floci-dash) is a third-party, AWS-console-style GUI for Floci — real Glue database/table browsing with schema drill-down, plus an Athena "Run Query" SQL editor.

```sh
docker pull ghcr.io/ofsazib/floci-dash:latest
docker run -d --name floci-dash -p 9877:3000 \
    -e FLOCI_URL=http://host.docker.internal:4566 -e AWS_REGION=eu-west-1 \
    ghcr.io/ofsazib/floci-dash:latest
```

Open `http://localhost:9877`. Two things to know before running a query, both genuine Floci quirks confirmed against this project's data, not floci-dash bugs:

1. **A semicolon is not needed in the query — and breaks it.** Floci wraps your query as `COPY (<your SQL>) TO 's3://...'` internally; a trailing `;` breaks that wrapper with a parser error. `select * from dim_organization limit 10` — no `;`.
2. **Set the "Database" field**, or fully-qualify table names (`iceduck_gold.dim_organization`) — a bare table name with no database set fails with a "table does not exist" error even though it exists.

See [`docs/TODO.md`](docs/TODO.md) for the full finding (the semicolon issue is a real Floci bug, same category as ADR-0007/0008).

## Testing

```sh
make test              # unit tests — fast, no Floci needed
make test-integration  # integration tests — needs `make demo` first (real Floci reads/writes)
```

Integration tests are skipped by default (`ICEDUCK_IT` unset); `make test-integration` sets it. See [`docs/plans/0008-tests.md`](docs/plans/0008-tests.md).

## Code quality

```sh
make lint        # ruff check — style, imports, NumPy-convention docstrings, type-hint coverage
make format       # ruff format — 120-char line length
make typecheck    # mypy
```

See [ADR-0012](docs/adr/0012-code-style-and-typing-standards.md) for the standards (120-char lines, NumPy docstrings, full type hints on core source, `tests/` exempted from docstring/annotation rules).

## dbt docs

```sh
make dbt-docs   # generates and serves the model DAG + schema/test docs site
```

Needs no live Floci — the DAG and all model/column descriptions come from pure static compilation, not a live warehouse query. Browse the full lineage: bronze sources → 6 staging models → 7 mart models. See [`docs/plans/0009-dbt-docs.md`](docs/plans/0009-dbt-docs.md).

## Dashboard

```sh
make dashboard   # analyst-facing dashboard over the gold layer
```

Streamlit + Plotly, reading `iceduck_gold` directly via DuckDB (the same resolve-then-`iceberg_scan` mechanism as everywhere else in this project — no Athena). KPIs, encounters over time/by class, cost by organization, top conditions/medications, and a raw-table browser. See [ADR-0011](docs/adr/0011-streamlit-dashboard-duckdb-not-athena.md) for why Streamlit was chosen over Apache Superset, and [`docs/plans/0010-streamlit-dashboard.md`](docs/plans/0010-streamlit-dashboard.md) for the build record.

## Learning notes

This project intentionally documents *why* each non-trivial decision was made (see `docs/plans/`), including places where an initial idea (e.g. using DuckLake, or forcing Glue to be DuckLake's catalog) turned out to be wrong and was revised. That history is kept on purpose — it's as much a part of the portfolio as the working pipeline.

# References

- https://blog-ocampoge.medium.com/floci-the-lightweight-local-aws-emulator-360d0030f504