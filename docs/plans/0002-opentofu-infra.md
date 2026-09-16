# 0002 — OpenTofu Infrastructure

Status: applied
Date: 2026-09-16

See [`docs/adr/`](../adr/) for the atomic decisions implemented in this phase: [ADR-0003](../adr/0003-opentofu-for-iac.md) (OpenTofu, local state) and [ADR-0006](../adr/0006-iam-role-for-practice-not-enforcement.md) (IAM role provisioned for practice, not enforcement).

## Context

This is Build Order step 2 from [`0001-lakehouse-architecture-outline.md`](0001-lakehouse-architecture-outline.md): provision the AWS-shaped infrastructure (S3 bucket, IAM role/policy, three Glue databases, Athena workgroup) against Floci using OpenTofu, before any ingestion or dbt code exists. Beyond unblocking later steps, hands-on OpenTofu/Terraform-style IaC practice is one of this project's explicit goals, so the infra was built deliberately (a real IAM role/policy, real outputs) rather than to the bare minimum.

## Decisions

- **Local Terraform state, not remote.** Floci supports an S3-backed remote state backend (confirmed via its own `compat-opentofu` compatibility-test fixtures on GitHub), but using it here would mean the state bucket needs to exist before it can be created — a bootstrapping problem not worth solving for a single-developer learning project. State lives in `infra/tofu/terraform.tfstate`, gitignored.
- **Region: `eu-west-1`, not the placeholder `eu-east-1`.** `.env.template` (and the live `.env`) originally had `AWS_DEFAULT_REGION=eu-east-1`, which is not a real AWS region — it would have worked against Floci (which doesn't validate region strings) but broken the project's "runs against real AWS with minimal changes" goal the moment it pointed at real AWS. Fixed to `eu-west-1` in both `.env`/`.env.template` and `variables.tf`'s `aws_region` default. These two are intentionally kept in sync by hand — there's no single shared config file between the Python/dbt side (`.env`) and the OpenTofu side (`.tf` vars) yet.
- **Static credentials: `floci`/`floci`, not Floci's own `test`/`test`.** Floci's official compat-test fixtures use literal `test`/`test` credentials, but this project already had `AWS_ACCESS_KEY_ID=floci` / `AWS_SECRET_ACCESS_KEY=floci` in `.env.template`. `variables.tf` defaults to the same values for consistency across the whole stack rather than matching Floci's own example verbatim.
- **The IAM role/policy is IaC practice, not enforcement.** Floci does not require the CLI/dbt/pyiceberg clients to assume `aws_iam_role.lakehouse_access` — they authenticate directly with the static `floci`/`floci` credentials configured on the AWS provider. The role and policy exist to practice writing real IAM IaC and to keep the project closer to what a real-AWS deployment would need (where an actual assume-role or instance-profile wiring would have to be added for the role to do anything). This is called out in a comment at the top of `iam.tf` so it doesn't look like dead/unused code later.
- **Provider config pattern taken from Floci's own compat-test fixtures.** `providers.tf`'s `endpoints{}` block plus `skip_credentials_validation`/`skip_metadata_api_check`/`skip_requesting_account_id`/`s3_use_path_style` mirrors `compat-opentofu/provider.tf` in [floci-io/floci-compatibility-tests](https://github.com/floci-io/floci-compatibility-tests) — a known-working configuration rather than a guess.

## Risk flagged and resolved

Floci's own official `compat-opentofu`/`compat-terraform` test fixtures do **not** exercise the `glue` or `athena` service endpoints at all — only s3/sqs/sns/dynamodb/lambda/iam/sts/ssm/secretsmanager are covered by their compatibility suite. Adding `glue` and `athena` entries to the `endpoints{}` block was therefore inference from the same pattern, not verified precedent, going into this change.

**Resolved:** `tofu apply` created all 8 resources (S3 bucket, 3× Glue database, Athena workgroup, IAM role + policy + attachment) cleanly on the first attempt with no errors on the Glue or Athena resources. Verified independently via the AWS CLI pointed at Floci (`aws glue get-database --name iceduck_bronze/_silver/_gold`, `aws athena get-work-group --work-group iceduck`) — all returned the expected data, including `LocationUri`/`OutputLocation` matching the S3 paths OpenTofu set. No further action needed; the gap in Floci's own test coverage did not manifest as a real problem here.

## Also fixed as part of this change

`docker/docker-compose.yml` was missing `FLOCI_STORAGE_MODE=persistent`, called for in doc 0001 but never actually set — Floci's default storage mode is in-memory, so every container restart would have silently wiped everything OpenTofu had just provisioned. Verified the fix directly: applied the infra, restarted the `floci` container, and confirmed `aws s3 ls` and `aws glue get-database --name iceduck_bronze` still returned the bucket and database afterward.

`.gitignore` didn't cover `.env` or any Terraform/OpenTofu artifacts (`.terraform/`, `*.tfstate`, `terraform.tfvars`, plan files) — added, since nothing had been committed yet and both were live gaps.

## Verification

Ran end-to-end against a live Floci container:

```
tofu init          # provider installed, lock file created
tofu validate       # Success! The configuration is valid.
tofu plan           # Plan: 8 to add, 0 to change, 0 to destroy
tofu apply          # Apply complete! Resources: 8 added, 0 changed, 0 destroyed.
```

Matches doc 0001's Phase 2 gate exactly: `tofu apply` clean; `aws s3 ls`, `aws glue get-database` (×3), `aws athena get-work-group` all succeeded. Plus the added persistence check (container restart) passing.
