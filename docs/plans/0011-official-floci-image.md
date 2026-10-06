# 0011 — Switch back to the official Floci image

Status: proposed
Date: 2026-10-06

Closes the "Pending upstream merge" item in [`docs/TODO.md`](../TODO.md) and follows the revert steps in [ADR-0008](../adr/0008-pin-floci-fork-for-athena-iceberg-fix.md).

## Context

Since ADR-0008, `docker/docker-compose.yml` has built Floci from source at our fork's commit (`maurice1979/floci@9e2d89e7`), using a `dockerfile_inline` that also works around an unrelated upstream `sidecars/` build gap. We did this so Athena could read Iceberg tables before the fix was released.

The fix, [floci-io/floci#3738](https://github.com/floci-io/floci/pull/3738) (closes [#3737](https://github.com/floci-io/floci/issues/3737)), merged on 2026-09-17 and shipped in **Floci 2.2.0** (released 2026-10-06). The release notes list it as "athena: read Iceberg-format Glue tables via iceberg_scan (#3738)", and Docker Hub publishes `floci/floci:2.2.0`. The official 2.2.0 Dockerfile already uses `FLOCI_STORAGE_PERSISTENT_PATH=/app/data` / `VOLUME /app/data`, so the existing `floci-data:/app/data` mount does not change.

The fork build is no longer needed. Removing it also removes the dependency on a personal fork and on a GitHub build at `docker compose up` time, along with the inline Dockerfile workaround.

## What will change

### 1. `docker/docker-compose.yml`

Replace the whole `build:` block (the git context, `dockerfile_inline` and the comment above it) with:

```yaml
image: floci/floci:2.2.0   # official release containing floci-io/floci#3738 — ADR-0015
```

`container_name`, ports, the `floci-data:/app/data` volume, the docker socket mount, environment and `restart` stay as they are.

**Pin the release tag, not `latest`.** ADR-0008's revert note allowed either. A floating tag would let an unrelated Floci release change Athena/Glue behaviour without notice, and the interop check in [`0006-athena-duckdb-interop.md`](0006-athena-duckdb-interop.md) depends on that behaviour. 2.1 → 2.2 alone is about 880 commits and includes several Athena changes. With a pinned tag, every upgrade is a deliberate one-line change.

### 2. Decision records

- **New `docs/adr/0015-official-floci-release-image.md`** (from `template.md`; `Status: Proposed` until verified, then `Accepted`). It records two decisions: use the official image, and pin it to a release tag. It explains why we pin and notes that the fork build and the `dockerfile_inline` workaround are gone.
- **ADR-0008**: change only the Status, to `Superseded by ADR-0015`. Context and Decision stay as written, per `docs/adr/README.md`.
- **`docs/TODO.md`**: remove the "Pending upstream merge" item. Rename the section "Athena Iceberg-read support in Floci — fixed upstream, pending merge" to "…released in Floci 2.2.0" and shorten it. Keep the open question about the missing Iceberg REST Catalog endpoint.

### 3. Living docs

Wherever the docs say "pinned fork", "unmerged upstream fix" or "pending merge", change the text to say the fix was made upstream in #3738, released in Floci 2.2.0, and that compose pins `floci/floci:2.2.0`:

- `README.md`: the architecture-diagram text and the "Note on Athena support" paragraph.
- `docs/architecture.md`: the Athena/Iceberg paragraph.
- `docs/plans/0006-athena-duckdb-interop.md`: append a dated follow-up line under the note that the result depends on the pinned fork. Do not rewrite the original note.
- `docs/architecture-diagram.drawio`: change the label "patched Floci fork / ADR-0008" to "Floci 2.2.0 / ADR-0015".

`.claude/worktrees/makefile-pipeline/` is a stale worktree copy and stays as it is.

## Verification

A new image starts with an empty Floci volume, so every check runs from a fresh state:

1. `make reset`, then `docker compose -f docker/docker-compose.yml pull`. Confirm the container runs `floci/floci:2.2.0` and that nothing is built locally.
2. `make demo`: floci-up → infra apply → raw → bronze → silver → gold, including dbt tests.
3. `make test`, `make dbt-check` and `ICEDUCK_IT=1 make test-integration`. The integration run covers `test_iceberg_publish.py`, `test_ingest_and_lookup.py` and `test_cli_pipeline.py`.
4. **Interop check**: re-run the check from [`0006-athena-duckdb-interop.md`](0006-athena-duckdb-interop.md). Query `iceduck_gold.fct_encounters` through Athena and through a fresh DuckDB `iceberg_scan` session. Both must return the same row count and the same row content.
5. Opportunistic: re-test the trailing-semicolon Athena bug from the floci-dash section of `docs/TODO.md` against 2.2.0. If it is fixed, update the TODO; otherwise leave it.
6. `make dashboard` smoke check.

Record the results here, then set this plan to `applied` and ADR-0015 to `Accepted`.

## Risks

- Floci 2.1/2.2 is a large jump from the fork's base. An unrelated Glue, S3 or Athena regression could break `make demo` or the integration tests. If that happens, stop and report it upstream instead of patching around it. No earlier official tag contains #3738, so the fallback is to keep ADR-0008's fork build until a fixed release ships.
