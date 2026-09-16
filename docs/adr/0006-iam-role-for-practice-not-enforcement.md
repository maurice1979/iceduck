# ADR-0006: Provision an IAM role/policy for IaC practice, not for runtime enforcement

Status: Accepted
Date: 2026-09-16

## Context

Floci emulates IAM (roles, policies, attachments), but does not enforce IAM authorization on its other emulated services. This project's own CLI, dbt, and pyiceberg clients authenticate against Floci with static credentials (`floci`/`floci`) configured directly on the AWS provider/SDK — regardless of what any IAM policy says. An infrastructure setup with no IAM resources at all would behave identically against Floci today.

## Decision

Provision a real `aws_iam_role` + `aws_iam_policy` + `aws_iam_role_policy_attachment` in `infra/tofu/iam.tf` anyway, scoped to the S3/Glue/Athena actions the pipeline actually needs (`s3:GetObject`/`PutObject`/`DeleteObject`/`ListBucket` on the lakehouse bucket; `glue:Get/Create/Update/DeleteTable` etc.; `athena:StartQueryExecution`/`GetQueryExecution`/`GetQueryResults`/`GetWorkGroup`) — purely as OpenTofu/IAM IaC practice and to keep the infra closer to what a real-AWS deployment would actually require.

## Consequences

- Real, portfolio-visible IAM IaC — a recognizable pattern (assume-role policy, least-privilege-scoped permission policy, attachment) rather than skipping IAM entirely because the emulator doesn't need it.
- The role is currently unused in practice: nothing assumes it, and no request is gated by it. This is documented explicitly, both in `iam.tf` itself and here, so a future reader doesn't mistake it for an active access-control mechanism or wonder why it appears dead.
- If this stack is ever pointed at real AWS, actual assume-role wiring (e.g. an instance profile, or an explicit `sts:AssumeRole` call in the CLI/dbt config) would need to be added for the role to have any effect — this ADR's scope stops at provisioning the role, not wiring runtime auth to use it.
