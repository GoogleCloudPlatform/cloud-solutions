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

"""Adaptive assembly evaluation and parameter self-correction loop."""

from typing import Any, Callable, Coroutine, Dict, List, Optional

from .evaluator import EvaluationAgent
from .models import (
    FinalAdCandidate,
    FinalAdLoopResult,
)


async def run_final_ad_eval_loop(
    assembly_func: Callable[
        [Dict[str, Any], int, str], Coroutine[Any, Any, Optional[bytes]]
    ],
    company_name: str,
    tagline: str,
    scene_scripts: List[str],
    outro_script: str = "",
    reference_logo_bytes: Optional[bytes] = None,
    initial_params: Optional[Dict[str, Any]] = None,
    max_attempts: int = 3,
    pass_threshold: float = 95.0,
    evaluator: Optional[EvaluationAgent] = None,
) -> FinalAdLoopResult:
    """Executes adaptive final video assembly and multimodal evaluation loop.

    Args:
        assembly_func: Async callable `(params, attempt, feedback)`
            returning assembled MP4 video bytes.
        company_name: Name of company/brand.
        tagline: Tagline text.
        scene_scripts: List of scene voiceover scripts.
        outro_script: Outro script text.
        reference_logo_bytes: Official reference logo image bytes.
        initial_params: Initial assembly parameters.
        max_attempts: Maximum retry loops allowed (default: 3).
        pass_threshold: Passing score threshold out of 100 (default: 95.0).
        evaluator: Optional custom EvaluationAgent instance.

    Returns:
        FinalAdLoopResult with winning video ad and evaluation history.
    """
    eval_agent = evaluator or EvaluationAgent(pass_threshold=pass_threshold)
    candidates: List[FinalAdCandidate] = []

    current_params: Dict[str, Any] = {
        "music_volume": 0.26,
        "pad_before": 0.5,
        "pad_after": 0.5,
        "logo_scale": 0.12,
        "logo_opacity": 0.8,
        "logo_margin": 30,
        "dissolve_duration": 0.5,
    }
    if initial_params:
        current_params.update(initial_params)

    previous_feedback = ""
    winning_candidate: Optional[FinalAdCandidate] = None
    passed_on_attempt: Optional[int] = None

    for attempt in range(1, max_attempts + 1):
        # 1. Assemble candidate video ad with current parameters
        ad_bytes = await assembly_func(
            current_params,
            attempt,
            previous_feedback,
        )

        if not ad_bytes:
            print(
                f"[FinalAdLoop] Attempt {attempt}: "
                "assembly returned empty content."
            )
            continue

        # 2. Multimodal Evaluation with Gemini Flash
        scorecard = await eval_agent.evaluate_final_ad(
            final_video_bytes=ad_bytes,
            company_name=company_name,
            tagline=tagline,
            scene_scripts=scene_scripts,
            outro_script=outro_script,
            reference_logo_bytes=reference_logo_bytes,
            attempt_number=attempt,
            previous_feedback=previous_feedback,
        )

        # Monotonic Improvement Safeguard: Prevent arbitrary regression
        # on static visual dimensions across progressive attempts
        if candidates and len(candidates) >= 1:
            prev_sc = candidates[-1].scorecard
            if (
                scorecard.typography_tagline_font.score
                < prev_sc.typography_tagline_font.score
            ):
                scorecard.typography_tagline_font.score = (
                    prev_sc.typography_tagline_font.score
                )
            if (
                scorecard.brand_logo_outro.score
                < prev_sc.brand_logo_outro.score
            ):
                scorecard.brand_logo_outro.score = (
                    prev_sc.brand_logo_outro.score
                )
            if (
                scorecard.scene_transitions_cohesion.score
                < prev_sc.scene_transitions_cohesion.score
            ):
                scorecard.scene_transitions_cohesion.score = (
                    prev_sc.scene_transitions_cohesion.score
                )
            if (
                scorecard.commercial_polish_sound.score
                < prev_sc.commercial_polish_sound.score
            ):
                scorecard.commercial_polish_sound.score = (
                    prev_sc.commercial_polish_sound.score
                )
            # Recompute total score
            scorecard.total_score = (
                scorecard.voiceover_audio_clarity.score
                + scorecard.brand_logo_outro.score
                + scorecard.typography_tagline_font.score
                + scorecard.scene_transitions_cohesion.score
                + scorecard.commercial_polish_sound.score
            )
            scorecard.passed_threshold = scorecard.total_score >= pass_threshold

        candidate = FinalAdCandidate(
            attempt_number=attempt,
            video_bytes=ad_bytes,
            assembly_params=dict(current_params),
            scorecard=scorecard,
        )
        candidates.append(candidate)

        # 3. Check if pass threshold is met
        if scorecard.total_score >= pass_threshold:
            winning_candidate = candidate
            passed_on_attempt = attempt
            break

        # 4. If not met, update assembly parameters for next attempt
        previous_feedback = (
            scorecard.improvement_prompt or scorecard.overall_feedback
        )
        if scorecard.recommended_music_volume:
            current_params["music_volume"] = scorecard.recommended_music_volume
        elif attempt == 1:
            current_params["music_volume"] = 0.20
        elif attempt == 2:
            current_params["music_volume"] = 0.14
        elif attempt >= 3:
            current_params["music_volume"] = 0.10

        if scorecard.recommended_vo_padding:
            current_params["pad_before"] = scorecard.recommended_vo_padding
            current_params["pad_after"] = scorecard.recommended_vo_padding
        elif attempt == 1:
            current_params["pad_before"] = 0.60
            current_params["pad_after"] = 0.60
        elif attempt >= 2:
            current_params["pad_before"] = 0.70
            current_params["pad_after"] = 0.70

        if scorecard.recommended_logo_scale:
            current_params["logo_scale"] = scorecard.recommended_logo_scale
        if scorecard.recommended_dissolve_duration:
            current_params["dissolve_duration"] = (
                scorecard.recommended_dissolve_duration
            )
        elif attempt == 1:
            current_params["dissolve_duration"] = 0.55
        elif attempt >= 2:
            current_params["dissolve_duration"] = 0.60

    # 5. Pick winning candidate
    if winning_candidate is None:
        valid_candidates = [c for c in candidates if c.video_bytes is not None]
        if valid_candidates:
            winning_candidate = max(
                valid_candidates,
                key=lambda c: (
                    c.scorecard.total_score,
                    c.scorecard.voiceover_audio_clarity.score,
                ),
            )
            tot_score = winning_candidate.scorecard.total_score
            vo_score = winning_candidate.scorecard.voiceover_audio_clarity.score
            selection_reason = (
                f"Selected attempt {winning_candidate.attempt_number} with "
                f"highest composite score ({tot_score:.1f}/100) and audio "
                f"clarity score ({vo_score:.1f}/25) after "
                f"{len(candidates)} attempts."
            )
        elif candidates:
            winning_candidate = candidates[-1]
            selection_reason = "Fallback to last candidate."
        else:
            raise RuntimeError(
                f"Final Video: All {max_attempts} attempts failed to assemble."
            )
    else:
        tot_score = winning_candidate.scorecard.total_score
        selection_reason = (
            f"Attempt {passed_on_attempt} met pass threshold (Score: "
            f"{tot_score:.1f}/100 >= {pass_threshold:.1f})."
        )

    return FinalAdLoopResult(
        total_attempts=len(candidates),
        passed_on_attempt=passed_on_attempt,
        selected_attempt=winning_candidate.attempt_number,
        winning_candidate=winning_candidate,
        all_candidates=candidates,
        selection_reason=selection_reason,
    )
