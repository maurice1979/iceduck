.PHONY: floci-up floci-down infra-init infra-validate infra-plan infra-apply infra-destroy

floci-up:
	docker compose -f docker/docker-compose.yml up -d

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
