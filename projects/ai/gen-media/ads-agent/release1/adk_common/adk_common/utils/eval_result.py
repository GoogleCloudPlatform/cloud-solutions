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


# pylint: disable=C0114, C0301
from typing import Literal

from pydantic import BaseModel, model_validator


class EvalResult(BaseModel):
    """Represents the structured result of a media evaluation."""

    decision: Literal["Pass", "Fail"]
    reason: str
    improvement_prompt: str
    subject_adherence: Literal["Pass", "Fail"]
    attribute_matching: Literal["Pass", "Fail"]
    spatial_accuracy: Literal["Pass", "Fail"]
    style_fidelity: Literal["Pass", "Fail"]
    quality_and_coherence: Literal["Pass", "Fail"]
    no_storyboard: Literal["Pass", "Fail"]
    consistency: Literal["Pass", "Fail"]
    llm_evaluation_score: int
    calculated_evaluation_score: int = 0
    averaged_evaluation_score: int = 0



    @model_validator(mode="after")
    def calculate_score(self) -> "EvalResult":
        score = 0
        score_mapping = {
            "decision": 10,
            "subject_adherence": 2,
            "attribute_matching": 2,
            "spatial_accuracy": 2,
            "style_fidelity": 2,
            "quality_and_coherence": 2,
            "no_storyboard": 2,
            "consistency": 3
        }

        # Max score is dynamically calculated
        total_possible_score = sum(score_mapping.values())
        for field, value in score_mapping.items():
            if getattr(self, field) == "Pass":
                score += value

        self.calculated_evaluation_score = score

        # Averages the normalized manual score and the LLM evaluation score
        normalized_binary_score = int((score / total_possible_score) * 100)
        self.averaged_evaluation_score = int((normalized_binary_score + self.llm_evaluation_score) / 2)
        return self
