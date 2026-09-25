.PHONY: floci-up floci-down infra-init infra-validate infra-plan infra-apply infra-destroy raw ingest dbt dbt-check demo demo-full reset test test-integration dbt-docs dashboard lint format typecheck

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

# Which local dataset `raw` uploads: fixtures (committed, default) or full
# (the whole Kaggle dataset, gitignored — run sample_data/health/download.py first).
DATASET ?= fixtures

raw:
	uv run iceduck s3-upload-raw --dataset $(DATASET)

ingest:
	uv run iceduck ingest-all

dbt:
	uv run iceduck build-silver
	uv run iceduck build-gold

# dbt checks that need no Floci (also what CI runs): parse the project, run the
# unit tests (format: sql fixtures touch no real table), and load the seeds with
# their own tests. `cautious` skips tests that also depend on unbuilt marts
# (e.g. fct_conditions.code -> condition_categories), which need the full pipeline.
dbt-check:
	set -a && . ./.env && set +a && cd dbt/iceduck && \
		dbt parse --profiles-dir . && \
		dbt test --select test_type:unit --profiles-dir . && \
		dbt build --select resource_type:seed --indirect-selection cautious --profiles-dir .

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
	@echo "Demo complete ($(DATASET) dataset): raw CSVs -> bronze -> silver -> gold, all real Iceberg tables in Glue (iceduck_bronze/iceduck_silver/iceduck_gold)."

# Same as demo, on the full Kaggle dataset (~1.2k patients, ~29 MB of CSV)
# instead of the 15-patient fixtures. Needs sample_data/health/full/ populated.
demo-full:
	$(MAKE) demo DATASET=full

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

# Analyst-facing dashboard over the gold layer — reads via DuckDB directly
# (resolve-then-iceberg_scan, ADR-0007), not Athena. See ADR-0011.
dashboard:
	uv run --extra dashboard streamlit run dashboard/app.py

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy src/iceduck dashboard scripts sample_data
