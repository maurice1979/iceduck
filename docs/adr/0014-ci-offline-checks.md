# ADR-0014: CI runs offline checks only — no Floci in GitHub Actions (yet)

Status: Proposed
Date: 2026-09-25

## Context

`docs/TODO.md` deferred CI/CD "until the core pipeline is built and there's something meaningful to run on every push". Both conditions now hold: the full raw → bronze → silver → gold pipeline exists, and the project has lint/format/type checks, Python unit tests, dbt data tests, dbt unit tests, and a seed with its own tests.

Not all of it can run cheaply in CI. The integration tests and anything that reads or writes Iceberg need a running Floci, the OpenTofu infra applied, and raw data uploaded — effectively `make demo`, several minutes and a Docker service per run. Most checks, however, need none of that:

- ruff, mypy and the `tests/unit` suite are pure Python.
- `dbt parse` is static compilation — it catches broken YAML/Jinja and bad `ref()`s.
- dbt **unit tests** whose inputs use `format: sql` fixtures touch no real relation, so they run against the in-memory DuckDB profile with nothing built (verified on dbt Fusion 2.0.6, from a clean copy with no `target/`).
- Seeds load from CSV, so a seed and its own tests run without Floci too.

The alternative — a CI job that starts Floci in Docker and runs the whole pipeline — gives end-to-end coverage but is slow, the Floci image is a pinned fork build (ADR-0008), and it adds a second moving part to debug on every red build.

## Decision

Add a GitHub Actions workflow (`.github/workflows/ci.yml`) on every pull request and on pushes to `main`, with two parallel jobs that need no Floci:

- **python**: `uv sync --locked --extra dashboard`, then `make lint`, `ruff format --check`, `make typecheck`, `make test`.
- **dbt**: install the dbt Fusion binary with the official install script, pinned via `--version` to the version used locally (2.0.6), then `make dbt-check` — `dbt parse`, `dbt test --select test_type:unit`, and `dbt build --select resource_type:seed --indirect-selection cautious`.

Both jobs copy `.env.template` to `.env`: settings and `profiles.yml` read the `AWS_*` variables even though nothing connects.

`make dbt-check` is the same command CI runs, so a red CI build reproduces locally with one command.

## Consequences

- Every PR gets fast feedback (lint, types, Python and dbt unit tests, dbt project validity, seed integrity) with no infrastructure.
- **Not covered by CI**: dbt data tests on real models (`not_null`, `relationships`, singular tests in `tests/`), the integration tests, and the Iceberg publish path. A PR can be green and still break `make demo`; those still need a local run before merging.
- `--indirect-selection cautious` is required in `dbt-check`: without it, building a seed also selects tests that depend on unbuilt marts (e.g. the `relationships` test from `fct_conditions.code` to `condition_categories`), which fail with "table does not exist" under the `:memory:` profile.
- The dbt version is pinned in two places — the local Homebrew install and `DBT_VERSION` in the workflow. Upgrading Fusion means bumping both; the `dbt --version` step makes the CI side visible in logs.
- New dbt unit tests are only CI-safe if their ephemeral inputs use `format: sql`, and non-ephemeral inputs will need the upstream relation's column types, i.e. a built model — worth keeping in mind when adding unit tests for models with non-ephemeral parents.
- A follow-up job running Floci in Docker for the integration tests remains possible; this ADR would then be superseded or extended.
