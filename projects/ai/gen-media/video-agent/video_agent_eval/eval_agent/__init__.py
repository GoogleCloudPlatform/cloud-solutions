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

"""Evaluation Agent package for multimodal video and commercial ad QA."""

from video_agent_eval.clip_eval_loop import run_clip_generation_and_eval_loop
from video_agent_eval.evaluator import EvaluationAgent
from video_agent_eval.final_ad_eval_loop import run_final_ad_eval_loop
from video_agent_eval.models import (
    ClipCandidate,
    ClipEvaluationLoopResult,
    FinalAdCandidate,
    FinalAdLoopResult,
    FinalAdRubricScorecard,
    PhysionArcScorecard,
    PhysionDimensionScore,
    PhysionMetricScore,
    RubricDimensionScore,
    RubricScorecard,
)
from video_agent_eval.prompts import (
    build_final_ad_evaluation_prompt,
    build_physion_arc_evaluation_prompt,
    build_video_clip_evaluation_prompt,
)
from video_agent_eval.subagents import (
    BaseEvaluationSubagent,
    BrandLogoOutroSubagent,
    CommercialPolishSoundSubagent,
    ConsistencySubagent,
    EvaluationCoordinator,
    MotionQualitySubagent,
    PromptAdherenceSubagent,
    SceneTransitionsSubagent,
    SubjectRealismSubagent,
    TypographyTaglineSubagent,
    VisualPolishSubagent,
    VoiceoverAudioSubagent,
)

__all__ = [
    "EvaluationAgent",
    "RubricScorecard",
    "RubricDimensionScore",
    "ClipCandidate",
    "ClipEvaluationLoopResult",
    "FinalAdRubricScorecard",
    "FinalAdCandidate",
    "FinalAdLoopResult",
    "PhysionArcScorecard",
    "PhysionDimensionScore",
    "PhysionMetricScore",
    "build_video_clip_evaluation_prompt",
    "build_final_ad_evaluation_prompt",
    "build_physion_arc_evaluation_prompt",
    "BaseEvaluationSubagent",
    "SubjectRealismSubagent",
    "ConsistencySubagent",
    "PromptAdherenceSubagent",
    "MotionQualitySubagent",
    "VisualPolishSubagent",
    "VoiceoverAudioSubagent",
    "BrandLogoOutroSubagent",
    "TypographyTaglineSubagent",
    "SceneTransitionsSubagent",
    "CommercialPolishSoundSubagent",
    "EvaluationCoordinator",
    "run_clip_generation_and_eval_loop",
    "run_final_ad_eval_loop",
]
