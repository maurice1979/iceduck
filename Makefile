.PHONY: floci-up floci-down infra-init infra-validate infra-plan infra-apply infra-destroy raw ingest dbt demo reset test test-integration dbt-docs

floci-up:
	docker compose -f docker/docker-compose.yml up -d --wait

floci-down:
	docker compose -f docker/docker-compose.yml down

infra-init:
	tofu -chdir=infra/tofu init

infra-validate:
	tofu -chdir=infra/tofu validate

infra-plan:
	tofu -chdir=infra/tofu plan

infra-apply:
	tofu -chdir=infra/tofu apply

infra-destroy:
	tofu -chdir=infra/tofu destroy

raw:
	uv run iceduck s3-upload-raw

ingest:
	uv run iceduck ingest-all

dbt:
	uv run iceduck build-silver
	uv run iceduck build-gold

# Unattended end-to-end run on the committed fixture data (no Kaggle token
# needed) — floci up, infra applied non-interactively, then the full
# raw -> bronze -> silver -> gold pipeline.
demo:
	$(MAKE) floci-up
	tofu -chdir=infra/tofu init -input=false
	tofu -chdir=infra/tofu apply -auto-approve
	$(MAKE) raw
	$(MAKE) ingest
	$(MAKE) dbt
	@echo "Demo complete: raw CSVs -> bronze -> silver -> gold, all real Iceberg tables in Glue (iceduck_bronze/iceduck_silver/iceduck_gold)."

# Stops Floci and wipes its persistent volume (FLOCI_STORAGE_MODE=persistent
# survives a plain floci-down), plus local tofu/dbt state, so `make demo` can
# run again from a genuinely clean slate.
reset:
	docker compose -f docker/docker-compose.yml down -v
	rm -rf infra/tofu/.terraform infra/tofu/terraform.tfstate infra/tofu/terraform.tfstate.backup
	rm -rf dbt/iceduck/target dbt/iceduck/logs
	@echo "Reset complete: Floci stopped and wiped, infra state and dbt build artifacts cleared."

test:
	uv run pytest tests/unit

# Requires a running Floci with infra applied (`make demo` first) — writes
# and drops real Iceberg tables, and rebuilds bronze/silver/gold.
test-integration:
	ICEDUCK_IT=1 uv run pytest tests/integration

# Generates and serves dbt's model DAG + docs site. Needs no live Floci —
# the manifest (DAG, descriptions, tests) is pure static compilation; the
# iceberg_source() macro defaults to an empty location when vars aren't
# supplied, specifically so this works standalone.
dbt-docs:
	cd dbt/iceduck && uv run dbt docs generate --profiles-dir . && uv run dbt docs serve --profiles-dir .
