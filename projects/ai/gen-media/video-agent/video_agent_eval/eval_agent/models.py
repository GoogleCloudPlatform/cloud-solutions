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

"""Data models for multimodal evaluation agent and rubric scorecards."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, model_validator


class RubricDimensionScore(BaseModel):
    """Evaluation score and qualitative critique for a single dimension."""

    dimension_name: str = ""
    score: float = 0.0
    max_score: float = 25.0
    verdict: str = "Pass"
    feedback: str = ""


class RubricScorecard(BaseModel):
    """Rubric evaluation scorecard for a single generated video clip (0-100)."""

    subject_realism: RubricDimensionScore
    storyboard_consistency: RubricDimensionScore
    prompt_adherence: RubricDimensionScore
    temporal_motion: RubricDimensionScore
    visual_polish: RubricDimensionScore
    total_score: float = 0.0
    passed_threshold: bool = False
    overall_feedback: str = ""
    improvement_prompt: str = ""

    @model_validator(mode="after")
    def compute_composite_metrics(self) -> "RubricScorecard":
        """Calculates total score from dimensions and evaluates threshold."""
        computed_total = (
            self.subject_realism.score
            + self.storyboard_consistency.score
            + self.prompt_adherence.score
            + self.temporal_motion.score
            + self.visual_polish.score
        )
        self.total_score = round(min(100.0, max(0.0, computed_total)), 2)
        self.passed_threshold = self.total_score >= 95.0
        return self


class ClipCandidate(BaseModel):
    """A generated clip attempt with its prompt and evaluation scorecard."""

    attempt_number: int = 1
    video_bytes: Optional[bytes] = None
    video_model: str = "omni"
    prompt_used: str = ""
    scorecard: RubricScorecard
    timestamp: str = ""


class ClipEvaluationLoopResult(BaseModel):
    """Outcome of multi-attempt generation and evaluation loop."""

    scene_number: int = 1
    total_attempts: int = 1
    passed_on_attempt: Optional[int] = None
    selected_attempt: int = 1
    winning_candidate: ClipCandidate
    all_candidates: List[ClipCandidate] = []
    selection_reason: str = ""


class FinalAdRubricScorecard(BaseModel):
    """Evaluation scorecard for fully assembled commercial video ad (0-100)."""

    voiceover_audio_clarity: RubricDimensionScore
    brand_logo_outro: RubricDimensionScore
    typography_tagline_font: RubricDimensionScore
    scene_transitions_cohesion: RubricDimensionScore
    commercial_polish_sound: RubricDimensionScore
    total_score: float = 0.0
    passed_threshold: bool = False
    overall_feedback: str = ""
    improvement_prompt: str = ""
    recommended_music_volume: float = 0.35
    recommended_vo_padding: float = 0.5
    recommended_logo_scale: float = 0.12
    recommended_dissolve_duration: float = 0.5

    @model_validator(mode="after")
    def compute_composite_metrics(self) -> "FinalAdRubricScorecard":
        """Calculates total score and checks 95% threshold."""
        computed_total = (
            self.voiceover_audio_clarity.score
            + self.brand_logo_outro.score
            + self.typography_tagline_font.score
            + self.scene_transitions_cohesion.score
            + self.commercial_polish_sound.score
        )
        self.total_score = round(min(100.0, max(0.0, computed_total)), 2)
        self.passed_threshold = self.total_score >= 95.0
        return self


class FinalAdCandidate(BaseModel):
    """A fully assembled video ad candidate and its evaluation scorecard."""

    attempt_number: int = 1
    video_bytes: Optional[bytes] = None
    assembly_params: Dict[str, Any] = {}
    scorecard: FinalAdRubricScorecard


class FinalAdLoopResult(BaseModel):
    """Outcome of multi-attempt assembly evaluation self-correction loop."""

    total_attempts: int = 1
    passed_on_attempt: Optional[int] = None
    selected_attempt: int = 1
    winning_candidate: FinalAdCandidate
    all_candidates: List[FinalAdCandidate] = []
    selection_reason: str = ""


class PhysionMetricScore(BaseModel):
    """Evaluation score for a single metric in the Physion ARC-16 suite."""

    metric_id: str
    label: str
    dimension_id: str
    family: str = "objective"
    score: float = 0.0
    feedback: str = ""


class PhysionDimensionScore(BaseModel):
    """Aggregated score for a quality dimension in Physion ARC-1.0."""

    dimension_id: str
    label: str
    code: str
    score: float = 0.0
    metrics: List[PhysionMetricScore] = []


class PhysionArcScorecard(BaseModel):
    """Official Physion ARC-1.0 benchmark scorecard across 16 metrics."""

    overall_score: float = 0.0
    narrative_coherence: PhysionDimensionScore
    cinematic_language: PhysionDimensionScore
    production_quality: PhysionDimensionScore
    all_metrics: List[PhysionMetricScore] = []
    industry_rank: str = "#1 Rank"
    key_strengths: List[str] = []
    areas_for_growth: List[str] = []

    @model_validator(mode="after")
    def compute_overall_score(self) -> "PhysionArcScorecard":
        """Calculates overall score across metrics and determines rank."""
        if self.all_metrics:
            self.overall_score = round(
                sum(m.score for m in self.all_metrics) / len(self.all_metrics),
                1,
            )
        elif self.narrative_coherence and self.cinematic_language:
            self.overall_score = round(
                (
                    self.narrative_coherence.score
                    + self.cinematic_language.score
                    + self.production_quality.score
                )
                / 3.0,
                1,
            )
        if self.overall_score > 72.4:
            self.industry_rank = (
                f"🏆 #1 Rank ({self.overall_score:.1f} vs Invideo 72.4 & "
                "Runway 69.6)"
            )
        elif self.overall_score > 69.6:
            self.industry_rank = (
                f"🥈 #2 Rank ({self.overall_score:.1f} vs Runway 69.6)"
            )
        else:
            self.industry_rank = f"Score: {self.overall_score:.1f}/100"
        return self
