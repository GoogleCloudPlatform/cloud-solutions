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

from fastapi import APIRouter
from pipeline_clients import get_pipeline_client

router = APIRouter(tags=["Pipeline"])


@router.get("/api/pipeline/status")
async def pipeline_status():
    project_id = os.getenv("GCP_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", ""))
    region = os.getenv("GCP_REGION", "us-central1")
    client = get_pipeline_client()
    return client.get_status(project_id, region)


@router.post("/api/pipeline/start")
async def start_pipeline():
    project_id = os.getenv("GCP_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", ""))
    region = os.getenv("GCP_REGION", "us-central1")
    client = get_pipeline_client()
    return await asyncio.to_thread(client.start_pipeline, project_id, region)


@router.post("/api/pipeline/stop")
async def stop_pipeline():
    project_id = os.getenv("GCP_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", ""))
    region = os.getenv("GCP_REGION", "us-central1")
    client = get_pipeline_client()
    return await asyncio.to_thread(client.stop_pipeline, project_id, region)
