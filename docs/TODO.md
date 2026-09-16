# TODO

Items explicitly deferred or considered out of scope for now, per `CLAUDE.md` and [`docs/plans/0001-lakehouse-architecture-outline.md`](plans/0001-lakehouse-architecture-outline.md).

## Out of scope for now

- **CI/CD.** No pipeline exists yet (no GitHub Actions, etc.). Revisit once the core pipeline (ingestion → dbt → marts) is built and there's something meaningful to run on every push.
- **Orchestration.** No Dagster/Airflow. A Makefile + the `iceduck` CLI drive steps in order; revisit only if the pipeline grows enough dependencies/scheduling needs to justify the added complexity.

## Future exploration

### AWS Lake Formation

Floci added Lake Formation support (~Sept 2026): full CRUD for data lake settings, resource registration, permissions, and LF-Tags (`services/lakeformation`), enough for the corresponding Terraform/OpenTofu resources (`aws_lakeformation_data_lake_settings`, `aws_lakeformation_resource`, `aws_lakeformation_permissions`, `aws_lakeformation_lf_tag`) to apply and converge. See [floci's Lake Formation docs](https://github.com/floci-io/floci/blob/main/docs/services/lakeformation.md) and [tracking issue #2310](https://github.com/floci-io/floci/issues/2310).

Caveat: it's CRUD-only, no enforcement — grants are creatable/listable/revocable, but Floci doesn't actually gate Glue catalog reads based on them. `ListPermissions` also returns all granted permissions without caller-based filtering. Useful for practicing the IaC side, not for testing real access-control behavior.

Today, `infra/tofu/iam.tf` grants direct Glue/S3/Athena IAM policy actions to a single role — there's no per-database or per-table governance layer. As a future exploration (extra IaC practice, not required for the pipeline to work):

- Register the lakehouse S3 bucket as a Lake Formation resource.
- Express access to `iceduck_bronze`/`iceduck_silver`/`iceduck_gold` as Lake Formation database/table grants instead of (or alongside) the current IAM policy actions — closer to how a real governed lakehouse is set up on AWS.
- Since enforcement isn't emulated, this would be a modeling/IaC exercise rather than something with observable runtime effect against Floci — worth calling out explicitly if pursued, so it isn't mistaken for an access-control feature that's actually being tested.

Record the decision (pursue or skip, and why) in a new `docs/plans/000X-*.md` if this is ever picked up, per the project's convention of documenting *why* non-trivial decisions were made.
