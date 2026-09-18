#!/usr/bin/env bash
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

# Container entrypoint executing uvicorn microservices for Oracle EBS Agentic AI.
set -euo pipefail

APP="${SERVICE_ENTRYPOINT:-${APP_MODULE:-src.a2a.a2a_server:app}}"
PORT_NUM="${PORT:-8080}"

exec uvicorn "${APP}" --host 0.0.0.0 --port "${PORT_NUM}"
