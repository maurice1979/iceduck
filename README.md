# IceDuck

A modern, from-scratch lakehouse built entirely on open-source tooling — a Data Engineering portfolio project focused on learning and practicing real lakehouse architecture, not just wiring up a demo.

The name reflects the core of the stack: **Ice**berg (the table format) on **Duck**DB (the query engine).

## Why this project

Most "lakehouse" portfolio projects stop at DuckDB + Parquet + dbt. This one goes further: it builds a genuine open **table format** (Apache Iceberg) on a real **catalog** (AWS Glue Data Catalog), provisioned as actual infrastructure (OpenTofu) against a local AWS emulator (Floci) — so the same code and IaC should, with minimal changes, work against real AWS. The explicit goals are to:

- Build a real medallion (bronze/silver/gold) lakehouse on Iceberg, not just files
- Get hands-on practice with OpenTofu/Terraform-style infrastructure-as-code
- Demonstrate genuine multi-engine interoperability: the same physical tables are real Iceberg tables in a real catalog, not an engine-specific format, and are readable from both a fresh **DuckDB** session and **AWS Athena** (emulated) — see the note in the Architecture section on how the latter currently depends on a not-yet-merged upstream fix
- Keep everything reproducible in Docker, with no cloud account or cost required to run it

## Architecture

```
raw CSV (S3 landing)
   │
   ▼
bronze (Iceberg, Glue DB: iceduck_bronze)     ← written via pyiceberg
   │
   ▼   dbt (dbt-duckdb) + a pyiceberg publish step
silver (Iceberg, Glue DB: iceduck_silver)     ← staging / intermediate models
   │
   ▼
gold (Iceberg, Glue DB: iceduck_gold)         ← dimensional marts (facts + dims)
   │
   ├── queryable from a fresh DuckDB session (via iceberg_scan on the metadata
   │   location Glue resolves — not a live catalog ATTACH; Floci doesn't
   │   implement Glue's Iceberg REST Catalog endpoint, see ADR-0007)
   └── queryable from Athena (emulated) — works today via a pinned fork build
       with an unmerged upstream fix, see ADR-0008
```

All storage lives in one S3 bucket (emulated via Floci); AWS Glue is the **single catalog** for every layer — there is no separate metadata database. Every write path (bronze, and silver/gold once built) goes through `pyiceberg`'s `GlueCatalog`, not `dbt-duckdb`'s native Glue-Iceberg materialization — verified via a spike, see [ADR-0005](docs/adr/0005-bronze-pyiceberg-silver-gold-dbt-duckdb.md) and [ADR-0007](docs/adr/0007-iceberg-reads-via-glue-resolved-metadata-location.md). See [`docs/plans/0001-lakehouse-architecture-outline.md`](docs/plans/0001-lakehouse-architecture-outline.md) for the full design rationale, including why DuckLake was considered and dropped in favor of this Iceberg-on-Glue design.

**Note on Athena support**: Floci's Athena emulation couldn't read genuine Iceberg tables out of the box (ADR-0007). We found, fixed, and submitted the root cause upstream — [floci-io/floci#3738](https://github.com/floci-io/floci/pull/3738) — and `docker/docker-compose.yml` currently builds Floci from that fix's commit rather than the official image so this project actually benefits from it now, pending merge (ADR-0008, with a revert TODO in `docs/TODO.md`).

## Tech stack

| Concern | Tool |
|---|---|
| Query engine / transform compute | [DuckDB](https://duckdb.org/) |
| Transformation framework | [dbt](https://www.getdbt.com/) (`dbt-duckdb`) |
| Table format | [Apache Iceberg](https://iceberg.apache.org/) |
| Catalog | AWS Glue Data Catalog |
| Local AWS emulation | [Floci](https://github.com/floci-io/floci) |
| Infrastructure as code | [OpenTofu](https://opentofu.org/) |
| Containerization | Docker / Docker Compose |
| Dataset | [Olist Brazilian E-Commerce](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) |
| Package management | [uv](https://docs.astral.sh/uv/) |

## Status

Early stage — architecture and build plan are defined, implementation is starting. See [`docs/plans/`](docs/plans/) for the phased build order and design decisions as they're made.

## Repository structure

```
docker/          Docker Compose (Floci, the local AWS emulator)
infra/tofu/      OpenTofu IaC: S3 bucket, IAM, Glue databases, Athena workgroup
scripts/         Standalone spike/verification scripts (not part of the pipeline)
src/iceduck/     Python CLI + core logic (ingestion, Iceberg/Glue helpers, settings)
products/         Per-entity ingestion config (Olist tables)
dbt/iceduck/      dbt project: staging → intermediate → marts
sample_data/      Dataset download + small committed fixtures for fast local runs
docs/             Architecture notes, ADRs, and phased design/build plans
tests/            Unit + integration tests
```

## Getting started

The infrastructure layer (S3 bucket, IAM role/policy, Glue databases, Athena workgroup) is runnable today. The rest of the pipeline (ingestion, dbt models) isn't built yet — see the build order in `docs/plans/0001-lakehouse-architecture-outline.md`.

Prerequisites: [Docker](https://www.docker.com/), [uv](https://docs.astral.sh/uv/), [OpenTofu](https://opentofu.org/) (`brew install opentofu`), AWS CLI (`brew install awscli`).

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

## Learning notes

This project intentionally documents *why* each non-trivial decision was made (see `docs/plans/`), including places where an initial idea (e.g. using DuckLake, or forcing Glue to be DuckLake's catalog) turned out to be wrong and was revised. That history is kept on purpose — it's as much a part of the portfolio as the working pipeline.

# References

- https://blog-ocampoge.medium.com/floci-the-lightweight-local-aws-emulator-360d0030f504