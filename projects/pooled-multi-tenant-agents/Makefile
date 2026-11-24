# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

.PHONY: help setup serve test test-live-gcp benchmark breach-sim lint format tf-init tf-validate clean config-check deploy deploy-infra deploy-image smoke validate

help: ## Show available Make targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup: ## Synchronize Python virtual environment with uv lockfile
	uv sync --frozen

serve: ## Run the gateway & UI locally on 127.0.0.1:8080 (local context signer; synthetic sandbox only)
	CYMBAL_LOCAL_SANDBOX=1 CYMBAL_LOCAL_CONTEXT_SIGNER=1 uv run uvicorn app.main:app --host 127.0.0.1 --port 8080

test: ## Run all unit, CISO edge-case, adversarial scrutiny, and volume tests
	uv run pytest -v

test-live-gcp: ## Run live integration tests against Cloud DLP, Firestore & BigQuery in cymbal-multitenancy-example
	RUN_LIVE_GCP_TESTS=1 uv run pytest tests/integration/test_live_gcp_integration.py -v -s

benchmark: ## Run 250-tenant / 2500-turn scale, QoS, and Pooled-vs-Siloed FinOps benchmark
	uv run python scripts/benchmark_pooling_at_scale.py

breach-sim: ## Run the 10-Point Breach Simulation CLI and automated pytest breach suite
	uv run python run_breach_simulations.py
	uv run pytest tests -v

lint: ## Run ruff linter and formatter check across all Python packages and tests
	uv run ruff check .
	uv run ruff format --check .

format: ## Format Python code with ruff
	uv run ruff format .

tf-init: ## Initialize Terraform in terraform/ (backend disabled for local validation)
	terraform -chdir=terraform init -backend=false

tf-validate: tf-init ## Validate Terraform HCL syntax, formatting, and example stamps
	terraform -chdir=terraform fmt -check -recursive -diff
	terraform -chdir=terraform validate
	@for env in terraform/envs/*/; do \
		terraform -chdir="$$env" init -backend=false >/dev/null; \
		terraform -chdir="$$env" validate; \
	done

clean: ## Remove local cache artifacts
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov

# ---------------------------------------------------------------------------
# Single deployment path (docs/customer_deployment.md). ENV = config/environments/<ENV>.yaml
# ---------------------------------------------------------------------------
ENV ?= sandbox

config-check: ## Validate layered platform config for ENV (schema, tenants, CMEK uniqueness)
	uv run python scripts/config_check.py --env $(ENV)

deploy: ## Full deploy of ENV: config-check -> terraform apply -> image -> smoke
	./scripts/deploy.sh $(ENV)

deploy-infra: ## Terraform only (infra, IAM, service identity and env) for ENV
	./scripts/deploy.sh $(ENV) --skip-image --skip-smoke

deploy-image: ## Roll a new gateway image only (no identity/env changes) for ENV
	./scripts/deploy.sh $(ENV) --skip-infra

smoke: ## Tier 3: read-only post-deploy checks against the deployed gateway for ENV
	CYMBAL_ENV=$(ENV) uv run python scripts/verify_cloud_run_deployment.py --env $(ENV)

validate: ## Tier 4: live isolation proofs (IAM denials, broker, BigQuery RLS, connectors) for ENV
	CYMBAL_ENV=$(ENV) RUN_LIVE_GCP_TESTS=1 uv run pytest tests/integration/test_live_tenant_blast_radius.py tests/integration/test_live_credential_broker.py tests/integration/test_live_gcp_integration.py -v
