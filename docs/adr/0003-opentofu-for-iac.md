# ADR-0003: OpenTofu for infrastructure as code, with local state

Status: Accepted
Date: 2026-09-16

## Context

Hands-on OpenTofu/Terraform-style IaC practice is one of this project's explicit goals, not just a means to provision resources. OpenTofu's AWS provider works against Floci using the standard `endpoints{}`/`skip_*` configuration pattern, confirmed against Floci's own official `compat-opentofu` compatibility-test fixtures.

Floci does support an S3-backed remote state backend (also present in those same fixtures), which is the standard production pattern for shared Terraform state. Using it here, however, means the state bucket would need to exist before OpenTofu could create it — a bootstrapping problem with no clean solution for a project where the bucket itself is one of the managed resources.

## Decision

Provision all AWS-shaped infrastructure (S3 bucket, IAM role/policy, three Glue databases, Athena workgroup) via OpenTofu, under `infra/tofu/`, using local Terraform state (`infra/tofu/terraform.tfstate`, gitignored) rather than a remote S3 backend.

## Consequences

- Simple, dependency-free workflow appropriate for a single developer: `tofu init && tofu apply` just works, no separate bootstrap step for a state backend.
- Not representative of team/production Terraform usage, where remote state plus locking (e.g. S3 + DynamoDB, as Floci's own compat fixtures demonstrate) is standard practice specifically to avoid state conflicts across multiple people/machines — acceptable trade-off for a solo learning project, but worth calling out explicitly so it isn't mistaken for a production-ready pattern.
- State lives only on the machine that ran `tofu apply`; there's no shared source of truth if the project were ever run from a second machine without also copying or migrating the state file.
