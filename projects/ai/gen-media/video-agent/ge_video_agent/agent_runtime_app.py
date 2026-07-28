# Copyright 2026 Google LLC
# Author: Layolin Jesudhass
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

import os
import sys

from dotenv import load_dotenv

load_dotenv()

gemini_location = os.environ.get("GOOGLE_CLOUD_LOCATION")

from ge_video.agent import root_agent as adk_app

import vertexai
from google.adk.artifacts import GcsArtifactService, InMemoryArtifactService
from vertexai.agent_engines.templates.adk import AdkApp


class AgentEngineApp(AdkApp):
    def set_up(self) -> None:
        vertexai.init()
        super().set_up()
        if gemini_location:
            os.environ["GOOGLE_CLOUD_LOCATION"] = gemini_location


bucket_name = os.environ.get("GOOGLE_CLOUD_BUCKET_ARTIFACTS")
agent_runtime = AgentEngineApp(
    app=adk_app,
    artifact_service_builder=lambda: (
        GcsArtifactService(bucket_name=bucket_name)
        if bucket_name
        else InMemoryArtifactService()
    ),
)
