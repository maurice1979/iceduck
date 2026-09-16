# ADR-0004: No orchestrator — Makefile + CLI drive pipeline steps

Status: Accepted
Date: 2026-09-15

## Context

The pipeline is a small, mostly linear medallion flow (raw → bronze → silver → gold) with no genuine scheduling requirement, cross-pipeline dependencies, or need for a metadata/lineage UI at this project's current scale. Full orchestrators (Dagster, Airflow) bring substantial operational surface — a scheduler process, a web UI, often their own metadata database — disproportionate to that scope.

## Decision

Drive pipeline steps with a Makefile plus a small `click`-based CLI (`iceduck`), run in order (e.g. `make demo`), rather than adopting an orchestrator.

## Consequences

- Much lower operational overhead: nothing to run besides Floci and the pipeline steps themselves; no orchestrator infrastructure to learn, configure, or keep healthy.
- Faster to build and simpler to demo end-to-end (`make demo`).
- No DAG visualization, automatic retries, scheduling, alerting, or lineage tooling — acceptable because pipeline runs are manual/on-demand, not a production schedule with SLAs.
- If the project's scope grows to genuinely need scheduling or complex dependency graphs, this decision should be revisited (and superseded by a new ADR) rather than organically growing the Makefile past the point it can express that well.
