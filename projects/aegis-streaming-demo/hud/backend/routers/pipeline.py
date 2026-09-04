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

"""Router for Dataproc Serverless streaming pipeline status and controls."""

import asyncio
import os

from dataproc_client import (
    get_dataproc_status,
    start_dataproc_pipeline,
    stop_dataproc_pipeline,
)
from fastapi import APIRouter

router = APIRouter(tags=["Pipeline"])


@router.get("/api/pipeline/status")
async def pipeline_status():
    project_id = os.getenv("GCP_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", ""))
    region = os.getenv("GCP_REGION", "")
    return get_dataproc_status(project_id, region)


@router.post("/api/pipeline/start")
async def start_pipeline():
    project_id = os.getenv("GCP_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", ""))
    region = os.getenv("GCP_REGION", "")
    return await asyncio.to_thread(start_dataproc_pipeline, project_id, region)


@router.post("/api/pipeline/stop")
async def stop_pipeline():
    project_id = os.getenv("GCP_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", ""))
    region = os.getenv("GCP_REGION", "")
    return await asyncio.to_thread(stop_dataproc_pipeline, project_id, region)
