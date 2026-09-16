# ADR-0002: Floci as the local AWS emulator

Status: Accepted
Date: 2026-09-15

## Context

The stack needs to run entirely locally, for free, without a cloud account — but should remain "AWS-compatible," runnable against real AWS with minimal changes. This requires an AWS emulator covering S3, Glue Data Catalog, IAM, and Athena, driven by the standard AWS SDK/CLI/Terraform tooling. LocalStack is the best-known option in this space; Floci (github.com/floci-io/floci) is a newer, MIT-licensed, lightweight, Docker-based alternative advertised as drop-in AWS SDK/CLI/IaC compatible.

## Decision

Use Floci as the local AWS emulator, run via `docker/docker-compose.yml`, exposed at `http://localhost:4566`. Set `FLOCI_STORAGE_MODE=persistent` explicitly (Floci's default storage mode is in-memory and would otherwise wipe all provisioned S3/Glue/IAM/Athena state on every container restart).

## Consequences

- Fully local, free, reproducible dev loop — no AWS account or cost required to build or demo the project.
- MIT license and drop-in AWS-tool compatibility mean the same OpenTofu/boto3/pyiceberg/dbt code should need only endpoint and credential changes to target real AWS.
- Floci is newer than LocalStack and less battle-tested for some services: its own official compatibility-test suite (`floci-compatibility-tests` on GitHub) does not exercise Glue or Athena via Terraform at all, only s3/sqs/sns/dynamodb/lambda/iam/sts/ssm/secretsmanager. Anything built against Glue/Athena on Floci needs to be verified manually rather than trusted by precedent (done for infra in `docs/plans/0002-opentofu-infra.md`).
- The `FLOCI_STORAGE_MODE=persistent` setting is easy to forget (it was in fact missing from the initial `docker-compose.yml` and had to be fixed — see `docs/plans/0002-opentofu-infra.md`); anyone resetting the container without it will silently lose all provisioned infrastructure and data.
