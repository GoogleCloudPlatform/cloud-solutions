# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

LINT_CONFIG_DIR := $(shell git rev-parse --show-toplevel)/config/lint

.PHONY: install test lint format run

install:
	uv sync --frozen --dev

test:
	uv run pytest tests/ -v --cov=oracle_ebs_scm_agentic_ai --cov-fail-under=90

# Pylint runs in Super-linter. Run tools/run_linters.sh from the repository
# root to run it locally with the same configuration.
lint:
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/
	uv run isort --settings-path $(LINT_CONFIG_DIR)/python-isort.toml --check-only src/ tests/
	uv run mypy

format:
	uv run ruff format src/ tests/
	uv run isort --settings-path $(LINT_CONFIG_DIR)/python-isort.toml src/ tests/

run:
	uv run uvicorn oracle_ebs_scm_agentic_ai.server:create_app --factory --host 0.0.0.0 --port 8080
