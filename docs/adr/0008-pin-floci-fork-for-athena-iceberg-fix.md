# ADR-0008: Build Floci from our fork's commit, not the official image, pending upstream merge

Status: Accepted
Date: 2026-09-16

## Context

ADR-0007 documented that Floci's Athena emulation cannot read genuine Iceberg tables — a real limitation, not an IceDuck bug. We implemented and verified a fix upstream (see `docs/plans/0003-iceberg-glue-spike.md`'s follow-up work): [floci-io/floci#3738](https://github.com/floci-io/floci/pull/3738), fixing [floci-io/floci#3737](https://github.com/floci-io/floci/issues/3737), built and independently verified against a live instance (two separate verification passes, including reproducing the exact orphaned-file scenario from ADR-0007 and confirming correct single-snapshot resolution). The PR is open but not yet merged or released.

Rather than wait for the merge to actually benefit from the fix day-to-day, `docker/docker-compose.yml` now builds Floci from our fork's commit instead of pulling `floci/floci:latest`.

## Decision

`docker/docker-compose.yml`'s `floci` service builds from `https://github.com/maurice1979/floci.git#9e2d89e723aa40fa7a5fdee2c419795947ba76cf` (the exact commit independently verified, not a floating branch name — a branch can gain more commits during PR review, and pinning to a SHA keeps this reproducible). This is temporary: **once floci-io/floci#3738 merges and ships in an official release, switch back to `image: floci/floci:latest`** (or a pinned official version tag) — tracked in `docs/TODO.md`.

Two consequences of building from source instead of pulling the pre-built image:

1. **Data directory changed**: this build's `docker/Dockerfile` defaults to `FLOCI_STORAGE_PERSISTENT_PATH=/app/data` (named Docker volumes are the current upstream convention), not the official image's `/var/lib/floci`. The compose volume mount was updated to match (`floci-data:/app/data`); `FLOCI_DATA_DIR` was dropped (not referenced by this build — superseded).
2. **A separate, unrelated upstream gap had to be worked around**: `docker/Dockerfile` as committed on `main` only `COPY`s `src/`, but `pom.xml`'s `build-helper-maven-plugin` adds `sidecars/cedar/src/main/java` as an extra test-compile source root — so a genuinely from-scratch `docker build .` of `docker/Dockerfile` fails Maven's test-compilation phase (even with `-DskipTests`, which only skips *running* tests, not compiling them) on `main` too, not just our branch. Confirmed by diffing our branch against `main` (`git diff main...feat/athena-iceberg-table-reads --stat` touches only the 3 files our fix actually changed) and by testing a minimal reproduction that adding `COPY sidecars/ sidecars/` fixes it cleanly. `docker-compose.yml` uses `dockerfile_inline` (not `dockerfile: docker/Dockerfile`) with that one line added, keeping the actual fix's PR branch minimal and unrelated to this separate bug — not reported upstream as part of this task (out of scope for what was asked), but worth filing separately later if it keeps biting local/from-source builds.

## Consequences

- IceDuck's local environment actually gets the working Athena-Iceberg behavior now, rather than waiting an indeterminate amount of time for upstream review/release — meaningful for a project whose central pitch is proving multi-engine interoperability.
- Anyone cloning this repo needs network access to GitHub to build the image (a git URL build context, not a registry pull) — acceptable for a local learning project, same trust model as pulling any other unofficial/unreleased image.
- This is deliberately not portable/durable: it references a personal fork (`maurice1979/floci`) that could be deleted or rebased. The whole point is that it's temporary — see the TODO to revert.
- Verified end-to-end against IceDuck's own real setup (not a side instance): reset and reran `tofu apply` against the freshly built container (a new image means a fresh, empty data volume — Floci's own state doesn't carry over across an image swap, expected and harmless for local dev infra), then reran `scripts/glue_iceberg_spike.py` and the exact Athena query from `docs/plans/0003-iceberg-glue-spike.md` that originally failed. Result: 3/3 correct rows via Athena — the fix works through IceDuck's actual committed configuration, not just the fork's own isolated test instance.

## Reverting once merged

1. Confirm `floci-io/floci#3738` is merged and included in a released `floci/floci` image tag.
2. In `docker/docker-compose.yml`: replace the `build:` block with `image: floci/floci:<released tag>` (or `latest`), revert the volume path if the official image still uses `/var/lib/floci` (check the released Dockerfile — it may have picked up the same `/app/data` convention by then).
3. `docker compose down -v && docker compose up -d`, then `rm infra/tofu/terraform.tfstate* && tofu apply` to reprovision against the official image.
4. Remove this ADR's TODO entry in `docs/TODO.md` and update this ADR's Status to `Superseded` with a pointer to whatever follow-up (if any) records the switch-back.
