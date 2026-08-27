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

"""Core multimodal evaluation agent using Gemini Flash."""

import json
import os
import subprocess
from typing import List, Optional

from google import genai
from google.genai import types

from .models import (
    FinalAdRubricScorecard,
    PhysionArcScorecard,
    RubricScorecard,
)
from .prompts import (
    build_final_ad_evaluation_prompt,
    build_physion_arc_evaluation_prompt,
    build_video_clip_evaluation_prompt,
)
from .subagents import EvaluationCoordinator

DEFAULT_EVALUATION_MODEL = os.environ.get(
    "EVALUATION_MODEL", "gemini-2.5-flash"
)
GOOGLE_CLOUD_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
if not GOOGLE_CLOUD_PROJECT:
    try:
        GOOGLE_CLOUD_PROJECT = subprocess.check_output(
            ["gcloud", "config", "get-value", "project"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (ValueError, RuntimeError, KeyError, TypeError):
        GOOGLE_CLOUD_PROJECT = ""


class EvaluationAgent:
    """Multimodal evaluation agent for validating video clips & final ads."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        project_id: Optional[str] = None,
        location: str = "global",
        pass_threshold: float = 92.0,
    ):
        self.model_name = model_name or DEFAULT_EVALUATION_MODEL
        self.project_id = project_id or GOOGLE_CLOUD_PROJECT
        self.location = location
        self.pass_threshold = pass_threshold
        self.coordinator = EvaluationCoordinator()
        self._client: Optional[genai.Client] = None

    def _get_client(self) -> genai.Client:
        """Initializes or returns cached Google GenAI client."""
        if self._client is None:
            if self.project_id:
                self._client = genai.Client(
                    vertexai=True,
                    project=self.project_id,
                    location=self.location,
                    http_options=types.HttpOptions(
                        headers={"Api-Revision": "2026-05-20"}
                    ),
                )
            else:
                self._client = genai.Client()
        return self._client

    async def evaluate_clip(
        self,
        video_bytes: bytes,
        reference_image_bytes: bytes,
        prompt_text: str,
        scene_number: int = 1,
        attempt_number: int = 1,
        previous_feedback: str = "",
        video_mime_type: str = "video/mp4",
        image_mime_type: str = "image/png",
    ) -> RubricScorecard:
        """Evaluates a video clip candidate using Gemini Flash."""
        eval_prompt = build_video_clip_evaluation_prompt(
            prompt_text=prompt_text,
            scene_number=scene_number,
            attempt_number=attempt_number,
            previous_feedback=previous_feedback,
        )

        contents = [
            eval_prompt,
            types.Part.from_bytes(
                data=reference_image_bytes, mime_type=image_mime_type
            ),
            types.Part.from_bytes(data=video_bytes, mime_type=video_mime_type),
        ]

        client = self._get_client()

        response = await client.aio.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=RubricScorecard,
                temperature=0.1,
            ),
        )

        if response.parsed and isinstance(response.parsed, RubricScorecard):
            scorecard = response.parsed
            scorecard.passed_threshold = (
                scorecard.total_score >= self.pass_threshold
            )
            return scorecard

        if response.text:
            data = json.loads(response.text)
            return self.coordinator.assemble_scorecard(
                data, pass_threshold=self.pass_threshold
            )

        raise RuntimeError("Evaluation model returned empty response for clip.")

    async def evaluate_final_ad(
        self,
        final_video_bytes: bytes,
        company_name: str,
        tagline: str,
        scene_scripts: List[str],
        outro_script: str = "",
        reference_logo_bytes: Optional[bytes] = None,
        attempt_number: int = 1,
        previous_feedback: str = "",
        video_mime_type: str = "video/mp4",
        logo_mime_type: str = "image/png",
    ) -> FinalAdRubricScorecard:
        """Evaluates fully assembled video advertisement using Gemini Flash."""
        eval_prompt = build_final_ad_evaluation_prompt(
            company_name=company_name,
            tagline=tagline,
            scene_scripts=scene_scripts,
            outro_script=outro_script,
            attempt_number=attempt_number,
            previous_feedback=previous_feedback,
        )

        contents = [
            eval_prompt,
            types.Part.from_bytes(
                data=final_video_bytes, mime_type=video_mime_type
            ),
        ]
        if reference_logo_bytes:
            contents.append(
                types.Part.from_bytes(
                    data=reference_logo_bytes, mime_type=logo_mime_type
                )
            )

        client = self._get_client()

        response = await client.aio.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=FinalAdRubricScorecard,
                temperature=0.1,
            ),
        )

        if response.parsed and isinstance(
            response.parsed, FinalAdRubricScorecard
        ):
            scorecard = response.parsed
            scorecard.passed_threshold = (
                scorecard.total_score >= self.pass_threshold
            )
            return scorecard

        if response.text:
            data = json.loads(response.text)
            return FinalAdRubricScorecard(**data)

        raise RuntimeError(
            "Evaluation model returned empty response for final ad."
        )

    async def evaluate_physion_arc(
        self,
        final_video_bytes: bytes,
        company_name: str,
        tagline: str,
        scene_scripts: List[str],
        outro_script: str = "",
        video_mime_type: str = "video/mp4",
    ) -> PhysionArcScorecard:
        """Evaluates campaign ad against official Physion ARC-16 metrics."""
        eval_prompt = build_physion_arc_evaluation_prompt(
            company_name=company_name,
            tagline=tagline,
            scene_scripts=scene_scripts,
            outro_script=outro_script,
        )

        contents = [
            eval_prompt,
            types.Part.from_bytes(
                data=final_video_bytes, mime_type=video_mime_type
            ),
        ]

        client = self._get_client()

        response = await client.aio.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=PhysionArcScorecard,
                temperature=0.1,
            ),
        )

        if response.parsed and isinstance(response.parsed, PhysionArcScorecard):
            return response.parsed

        if response.text:
            data = json.loads(response.text)
            return PhysionArcScorecard(**data)

        raise RuntimeError(
            "Evaluation model returned empty response for Physion ARC."
        )
