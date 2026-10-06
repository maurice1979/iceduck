# ADR-0015: Use the official Floci image, pinned to a release tag

Status: Accepted
Date: 2026-10-06

## Context

[ADR-0008](0008-pin-floci-fork-for-athena-iceberg-fix.md) built Floci from our fork's commit (`maurice1979/floci@9e2d89e7`) so Athena could read Iceberg tables before our upstream fix was released. That build also needed a `dockerfile_inline` workaround for an unrelated upstream `sidecars/` build gap.

The fix, [floci-io/floci#3738](https://github.com/floci-io/floci/pull/3738), merged on 2026-09-17 and shipped in Floci **2.2.0** (released 2026-10-06), published on Docker Hub as `floci/floci:2.2.0`. The official image stores its data under `/app/data`, the same path the fork build used.

There were two options for the image reference: `floci/floci:latest`, or a pinned release tag.

## Decision

`docker/docker-compose.yml` uses `image: floci/floci:2.2.0`, the official image pinned to the first release that contains #3738.

We pin the tag rather than use `latest` because IceDuck's interop check ([`0006-athena-duckdb-interop.md`](../plans/0006-athena-duckdb-interop.md)) depends on how Floci's Athena and Glue emulation behaves. Floci releases often, and releases are large: 2.1 → 2.2 is about 880 commits with several Athena changes. With a floating tag, a `docker compose pull` could silently change that behaviour. With a pinned tag, every upgrade is a deliberate, reviewable one-line change, followed by re-running `make demo` and the interop check.

## Consequences

- No more source build. `make floci-up` pulls a prebuilt image: it is faster, needs no Maven/JDK build step and no GitHub build context, and no longer depends on a personal fork that could be deleted or rebased.
- The `dockerfile_inline` workaround for the upstream `sidecars/` build gap is no longer needed, because we don't build Floci at all.
- Switching images starts Floci with fresh state, so infra has to be reprovisioned (`make reset && make demo`).
- Verified against IceDuck's real setup: `make demo`, the integration tests, and the Athena ↔ DuckDB check on `iceduck_gold.fct_encounters` (358 = 358, identical rows) — see [`0011-official-floci-image.md`](../plans/0011-official-floci-image.md).
- Floci fixes after 2.2.0 don't arrive automatically; upgrades are a manual tag bump.
