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

"""Router for stream processing pipeline status and controls."""

import asyncio
import os
from typing import Any

from fastapi import APIRouter
from pipeline_clients import get_pipeline_client

router = APIRouter(tags=["Pipeline"])


def _get_project_and_region() -> tuple[str, str]:
    """Return the configured Google Cloud project ID and deployment region."""
    project_id = os.getenv("GCP_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", ""))
    region = os.getenv("GCP_REGION", "us-central1")
    return project_id, region


@router.get("/api/pipeline/status")
async def pipeline_status() -> dict[str, Any]:
    """Returns the current stream processing pipeline status."""
    project_id, region = _get_project_and_region()
    client = get_pipeline_client()
    return client.get_status(project_id, region)


@router.post("/api/pipeline/start")
async def start_pipeline() -> dict[str, Any]:
    """Starts the active stack's stream processing pipeline."""
    project_id, region = _get_project_and_region()
    client = get_pipeline_client()
    return await asyncio.to_thread(client.start_pipeline, project_id, region)


@router.post("/api/pipeline/stop")
async def stop_pipeline() -> dict[str, Any]:
    """Stops the active stack's stream processing pipeline."""
    project_id, region = _get_project_and_region()
    client = get_pipeline_client()
    return await asyncio.to_thread(client.stop_pipeline, project_id, region)
