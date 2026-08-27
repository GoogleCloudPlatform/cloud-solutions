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

"""Specialized evaluation subagents for rubric dimension validation."""

from abc import ABC, abstractmethod
from typing import Any, Dict

from ge_video_agent_eval.models import RubricDimensionScore, RubricScorecard


class BaseEvaluationSubagent(ABC):
    """Abstract base class for modular evaluation subagents."""

    def __init__(self, dimension_name: str, max_points: float):
        self.dimension_name = dimension_name
        self.max_points = max_points

    @abstractmethod
    def validate_dimension(
        self,
        dimension_data: Dict[str, Any],
    ) -> RubricDimensionScore:
        """Validates and standardizes a single dimension evaluation."""


# ── Clip Evaluation Subagents ────────────────────────────────


class SubjectRealismSubagent(BaseEvaluationSubagent):
    """Subagent for Primary Subject & Product / Food Realism (25 pts)."""

    def __init__(self):
        super().__init__(
            dimension_name="Primary Subject & Product/Food Realism & Appeal",
            max_points=25.0,
        )

    def validate_dimension(
        self,
        dimension_data: Dict[str, Any],
    ) -> RubricDimensionScore:
        raw_score = float(dimension_data.get("score", 0.0))
        clamped_score = max(0.0, min(self.max_points, raw_score))
        feedback = dimension_data.get("feedback", "")
        threshold = self.max_points * 0.95
        verdict = "Pass" if clamped_score >= threshold else "Fail"
        return RubricDimensionScore(
            dimension_name=self.dimension_name,
            score=clamped_score,
            max_score=self.max_points,
            verdict=verdict,
            feedback=feedback,
        )


class ConsistencySubagent(BaseEvaluationSubagent):
    """Subagent for Reference Image & Storyboard Consistency (25 pts)."""

    def __init__(self):
        super().__init__(
            dimension_name="Reference Image & Storyboard Consistency",
            max_points=25.0,
        )

    def validate_dimension(
        self,
        dimension_data: Dict[str, Any],
    ) -> RubricDimensionScore:
        raw_score = float(dimension_data.get("score", 0.0))
        clamped_score = max(0.0, min(self.max_points, raw_score))
        feedback = dimension_data.get("feedback", "")
        threshold = self.max_points * 0.95
        verdict = "Pass" if clamped_score >= threshold else "Fail"
        return RubricDimensionScore(
            dimension_name=self.dimension_name,
            score=clamped_score,
            max_score=self.max_points,
            verdict=verdict,
            feedback=feedback,
        )


class PromptAdherenceSubagent(BaseEvaluationSubagent):
    """Subagent for Prompt Adherence & Action Execution (20 pts)."""

    def __init__(self):
        super().__init__(
            dimension_name="Prompt Adherence & Action Execution",
            max_points=20.0,
        )

    def validate_dimension(
        self,
        dimension_data: Dict[str, Any],
    ) -> RubricDimensionScore:
        raw_score = float(dimension_data.get("score", 0.0))
        clamped_score = max(0.0, min(self.max_points, raw_score))
        feedback = dimension_data.get("feedback", "")
        threshold = self.max_points * 0.95
        verdict = "Pass" if clamped_score >= threshold else "Fail"
        return RubricDimensionScore(
            dimension_name=self.dimension_name,
            score=clamped_score,
            max_score=self.max_points,
            verdict=verdict,
            feedback=feedback,
        )


class MotionQualitySubagent(BaseEvaluationSubagent):
    """Subagent for Temporal Consistency & Motion Fluidity (20 pts)."""

    def __init__(self):
        super().__init__(
            dimension_name="Temporal Consistency & Motion Fluidity",
            max_points=20.0,
        )

    def validate_dimension(
        self,
        dimension_data: Dict[str, Any],
    ) -> RubricDimensionScore:
        raw_score = float(dimension_data.get("score", 0.0))
        clamped_score = max(0.0, min(self.max_points, raw_score))
        feedback = dimension_data.get("feedback", "")
        threshold = self.max_points * 0.95
        verdict = "Pass" if clamped_score >= threshold else "Fail"
        return RubricDimensionScore(
            dimension_name=self.dimension_name,
            score=clamped_score,
            max_score=self.max_points,
            verdict=verdict,
            feedback=feedback,
        )


class VisualPolishSubagent(BaseEvaluationSubagent):
    """Subagent for Commercial Production Quality & Polish (10 pts)."""

    def __init__(self):
        super().__init__(
            dimension_name="Commercial Production Quality & Visual Polish",
            max_points=10.0,
        )

    def validate_dimension(
        self,
        dimension_data: Dict[str, Any],
    ) -> RubricDimensionScore:
        raw_score = float(dimension_data.get("score", 0.0))
        clamped_score = max(0.0, min(self.max_points, raw_score))
        feedback = dimension_data.get("feedback", "")
        threshold = self.max_points * 0.95
        verdict = "Pass" if clamped_score >= threshold else "Fail"
        return RubricDimensionScore(
            dimension_name=self.dimension_name,
            score=clamped_score,
            max_score=self.max_points,
            verdict=verdict,
            feedback=feedback,
        )


# ── Full-Ad Assembly Evaluation Subagents ────────────────────


class VoiceoverAudioSubagent(BaseEvaluationSubagent):
    """Subagent for Voiceover Clarity, Pacing & Non-Truncation (25 pts)."""

    def __init__(self):
        super().__init__(
            dimension_name="Voiceover Audio Clarity, Pacing & Non-Truncation",
            max_points=25.0,
        )

    def validate_dimension(
        self,
        dimension_data: Dict[str, Any],
    ) -> RubricDimensionScore:
        raw_score = float(dimension_data.get("score", 0.0))
        clamped_score = max(0.0, min(self.max_points, raw_score))
        feedback = dimension_data.get("feedback", "")
        threshold = self.max_points * 0.95
        verdict = "Pass" if clamped_score >= threshold else "Fail"
        return RubricDimensionScore(
            dimension_name=self.dimension_name,
            score=clamped_score,
            max_score=self.max_points,
            verdict=verdict,
            feedback=feedback,
        )


class BrandLogoOutroSubagent(BaseEvaluationSubagent):
    """Subagent for Brand Identity, Logo & Outro Aesthetics (20 pts)."""

    def __init__(self):
        super().__init__(
            dimension_name="Brand Identity, Logo Placement & Outro Aesthetics",
            max_points=20.0,
        )

    def validate_dimension(
        self,
        dimension_data: Dict[str, Any],
    ) -> RubricDimensionScore:
        raw_score = float(dimension_data.get("score", 0.0))
        clamped_score = max(0.0, min(self.max_points, raw_score))
        feedback = dimension_data.get("feedback", "")
        threshold = self.max_points * 0.95
        verdict = "Pass" if clamped_score >= threshold else "Fail"
        return RubricDimensionScore(
            dimension_name=self.dimension_name,
            score=clamped_score,
            max_score=self.max_points,
            verdict=verdict,
            feedback=feedback,
        )


class TypographyTaglineSubagent(BaseEvaluationSubagent):
    """Subagent for Typography, Tagline & Font Appearance (15 pts)."""

    def __init__(self):
        super().__init__(
            dimension_name="Typography, Tagline & Font Appearance",
            max_points=15.0,
        )

    def validate_dimension(
        self,
        dimension_data: Dict[str, Any],
    ) -> RubricDimensionScore:
        raw_score = float(dimension_data.get("score", 0.0))
        clamped_score = max(0.0, min(self.max_points, raw_score))
        feedback = dimension_data.get("feedback", "")
        threshold = self.max_points * 0.95
        verdict = "Pass" if clamped_score >= threshold else "Fail"
        return RubricDimensionScore(
            dimension_name=self.dimension_name,
            score=clamped_score,
            max_score=self.max_points,
            verdict=verdict,
            feedback=feedback,
        )


class SceneTransitionsSubagent(BaseEvaluationSubagent):
    """Subagent for Multi-Scene Transitions & Narrative Cohesion (20 pts)."""

    def __init__(self):
        super().__init__(
            dimension_name="Multi-Scene Transitions & Narrative Cohesion",
            max_points=20.0,
        )

    def validate_dimension(
        self,
        dimension_data: Dict[str, Any],
    ) -> RubricDimensionScore:
        raw_score = float(dimension_data.get("score", 0.0))
        clamped_score = max(0.0, min(self.max_points, raw_score))
        feedback = dimension_data.get("feedback", "")
        threshold = self.max_points * 0.95
        verdict = "Pass" if clamped_score >= threshold else "Fail"
        return RubricDimensionScore(
            dimension_name=self.dimension_name,
            score=clamped_score,
            max_score=self.max_points,
            verdict=verdict,
            feedback=feedback,
        )


class CommercialPolishSoundSubagent(BaseEvaluationSubagent):
    """Subagent for Commercial Broadcast Polish & Sound Balance (20 pts)."""

    def __init__(self):
        super().__init__(
            dimension_name="Commercial Broadcast Polish & Sound Balance",
            max_points=20.0,
        )

    def validate_dimension(
        self,
        dimension_data: Dict[str, Any],
    ) -> RubricDimensionScore:
        raw_score = float(dimension_data.get("score", 0.0))
        clamped_score = max(0.0, min(self.max_points, raw_score))
        feedback = dimension_data.get("feedback", "")
        threshold = self.max_points * 0.95
        verdict = "Pass" if clamped_score >= threshold else "Fail"
        return RubricDimensionScore(
            dimension_name=self.dimension_name,
            score=clamped_score,
            max_score=self.max_points,
            verdict=verdict,
            feedback=feedback,
        )


# ── Coordinators ─────────────────────────────────────────────


class EvaluationCoordinator:
    """Orchestrates clip subagents and validates holistic scorecards."""

    def __init__(self):
        self.subject_subagent = SubjectRealismSubagent()
        self.consistency_subagent = ConsistencySubagent()
        self.prompt_subagent = PromptAdherenceSubagent()
        self.motion_subagent = MotionQualitySubagent()
        self.polish_subagent = VisualPolishSubagent()

    def assemble_scorecard(
        self,
        raw_data: Dict[str, Any],
        pass_threshold: float = 95.0,
    ) -> RubricScorecard:
        """Validates all subagent dimensions into a unified scorecard."""
        s_real = self.subject_subagent.validate_dimension(
            raw_data.get("subject_realism", {})
        )
        s_cons = self.consistency_subagent.validate_dimension(
            raw_data.get("storyboard_consistency", {})
        )
        s_prom = self.prompt_subagent.validate_dimension(
            raw_data.get("prompt_adherence", {})
        )
        s_moti = self.motion_subagent.validate_dimension(
            raw_data.get("temporal_motion", {})
        )
        s_poli = self.polish_subagent.validate_dimension(
            raw_data.get("visual_polish", {})
        )

        overall_fb = str(raw_data.get("overall_feedback", ""))
        improve_pr = str(raw_data.get("improvement_prompt", ""))

        card = RubricScorecard(
            subject_realism=s_real,
            storyboard_consistency=s_cons,
            prompt_adherence=s_prom,
            temporal_motion=s_moti,
            visual_polish=s_poli,
            overall_feedback=overall_fb,
            improvement_prompt=improve_pr,
        )
        card.passed_threshold = card.total_score >= pass_threshold
        return card
