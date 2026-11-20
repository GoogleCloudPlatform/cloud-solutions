#!/usr/bin/env bash
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

# ==============================================================================
# First-time environment bootstrap (Pattern A: Pooled Multi-Tenancy).
#
#   ./scripts/bootstrap_customer_env.sh <env>
#
# Prerequisite: config/environments/<env>.yaml (copy customer.example.yaml) and tenant files in
# config/tenants/<env>/. This script only runs prerequisite checks and then the SAME deploy path as
# every other deployment (scripts/deploy.sh). It no longer writes .env or deploys Cloud Run with a
# different service account than Terraform (deployment audit finding F3).
# ==============================================================================
set -euo pipefail

ENV_NAME="${1:-}"
if [[ -z "$ENV_NAME" ]]; then
  echo "Usage: $0 <env> [deploy.sh flags...]   (config/environments/<env>.yaml must exist)"
  exit 1
fi
shift
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "==> Prerequisites"
# CYMBAL_ENV makes the prerequisite report name THIS environment's project, not the sandbox default.
CYMBAL_ENV="$ENV_NAME" uv run --frozen python scripts/check_prerequisites.py || true
uv run --frozen python scripts/config_check.py --env "$ENV_NAME" --for-deploy

echo "==> Deploying through the single path (scripts/deploy.sh)"
exec "$REPO_DIR/scripts/deploy.sh" "$ENV_NAME" "$@"
