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

"""Adaptive clip generation and evaluation self-correction loop."""

import asyncio
from typing import Any, Callable, Coroutine, List, Optional

from ge_video_agent_eval.evaluator import EvaluationAgent
from ge_video_agent_eval.models import ClipCandidate, ClipEvaluationLoopResult


async def run_clip_generation_and_eval_loop(
    generator_func: Callable[
        [bytes, str, int, str], Coroutine[Any, Any, Optional[bytes]]
    ],
    reference_image_bytes: bytes,
    base_prompt: str,
    scene_number: int = 1,
    video_model: str = "omni",
    max_attempts: int = 3,
    pass_threshold: float = 92.0,
    evaluator: Optional[EvaluationAgent] = None,
) -> ClipEvaluationLoopResult:
    """Executes adaptive clip generation & multimodal evaluation loop (max 3).

    Args:
        generator_func: Async callable `(image, prompt, attempt, feedback)`
            generating video bytes using Omni or Veo.
        reference_image_bytes: Reference storyboard image bytes.
        base_prompt: Initial prompt describing scene and motion.
        scene_number: Index of current scene.
        video_model: Generation model name ("omni" or "veo").
        max_attempts: Maximum retry loops allowed (default: 3).
        pass_threshold: Passing score threshold out of 100 (default: 92.0).
        evaluator: Optional custom EvaluationAgent instance.

    Returns:
        ClipEvaluationLoopResult with winning candidate and attempt history.
    """
    eval_agent = evaluator or EvaluationAgent(pass_threshold=pass_threshold)
    candidates: List[ClipCandidate] = []

    current_prompt = base_prompt
    previous_feedback = ""
    all_refinements: List[str] = []
    winning_candidate: Optional[ClipCandidate] = None
    passed_on_attempt: Optional[int] = None

    while len(candidates) < max_attempts:
        attempt_num = len(candidates) + 1
        clip_bytes = None
        scorecard = None

        # 1. Generate video candidate with per-attempt auto-retry
        for sub_retry in range(3):
            try:
                clip_bytes = await generator_func(
                    reference_image_bytes,
                    current_prompt,
                    attempt_num,
                    previous_feedback,
                )
                if clip_bytes:
                    break
                print(
                    f"[Loop] Scene {scene_number} attempt {attempt_num} "
                    f"(retry {sub_retry + 1}/3): API glitch / empty content, "
                    "retrying generation..."
                )
                await asyncio.sleep(2)
            except (
                ValueError,
                RuntimeError,
                KeyError,
                TypeError,
                OSError,
                IOError,
            ) as gen_err:
                print(
                    f"[Loop] Scene {scene_number} attempt {attempt_num} "
                    f"(retry {sub_retry + 1}/3): Generator error "
                    f"({gen_err}), retrying generation..."
                )
                await asyncio.sleep(3)

        if not clip_bytes:
            print(
                f"[Loop] Scene {scene_number} attempt {attempt_num}: "
                "Unable to obtain video after 3 retries. Proceeding..."
            )
            continue

        # 2. Multimodal Evaluation with Gemini Flash (with retry)
        for ev_retry in range(3):
            try:
                scorecard = await eval_agent.evaluate_clip(
                    video_bytes=clip_bytes,
                    reference_image_bytes=reference_image_bytes,
                    prompt_text=current_prompt,
                    scene_number=scene_number,
                    attempt_number=attempt_num,
                    previous_feedback=previous_feedback,
                )
                if scorecard:
                    break
            except (
                ValueError,
                RuntimeError,
                KeyError,
                TypeError,
                OSError,
                IOError,
            ) as ev_err:
                print(
                    f"[Loop] Scene {scene_number} eval retry "
                    f"{ev_retry + 1}/3: {ev_err}"
                )
                await asyncio.sleep(2)

        if not scorecard:
            continue

        candidate = ClipCandidate(
            attempt_number=attempt_num,
            video_bytes=clip_bytes,
            video_model=video_model,
            prompt_used=current_prompt,
            scorecard=scorecard,
        )
        candidates.append(candidate)

        # 3. Check if pass threshold is met
        print(
            f"[Loop] Scene {scene_number} attempt {attempt_num}: "
            f"Score {scorecard.total_score:.1f}/100 "
            f"(Target Threshold: {pass_threshold:.1f})"
        )
        if scorecard.total_score >= pass_threshold:
            winning_candidate = candidate
            passed_on_attempt = attempt_num
            print(
                f"[Loop] Scene {scene_number} PASSED on attempt {attempt_num}!"
            )
            break

        # 4. If not met, incorporate cumulative feedback for next attempt
        print(
            f"[Loop] Scene {scene_number} attempt {attempt_num} score "
            f"({scorecard.total_score:.1f}) < target threshold "
            f"({pass_threshold:.1f}). Compounding feedback for "
            f"attempt {attempt_num + 1}..."
        )
        clean_fb = (
            scorecard.improvement_prompt
            or scorecard.overall_feedback
            or "Enhance structural rigidity and eliminate surface warping."
        ).strip()
        all_refinements.append(clean_fb)
        refinements_block = "\n".join([f"• {r}" for r in all_refinements[-2:]])

        is_outdoor = any(
            w in base_prompt.lower()
            for w in [
                "pool",
                "water",
                "ocean",
                "aerial",
                "garden",
                "outdoor",
                "flight",
                "sunrise",
                "beach",
                "fountain",
            ]
        )
        if is_outdoor:
            motion_refinement = (
                "\n• SMOOTH CONTINUOUS GLIDE: Maintain steady front-moving "
                "forward pan-in glide. Calm glassy water reflections with "
                "gentle sparkling caustics. Zero geometric warping. Zero cuts."
            )
        else:
            motion_refinement = (
                "\n• RIGID INDOOR STABILITY: Strict indoor room containment — "
                "camera remains 100% inside suite (ZERO flying out window, "
                "ZERO diving to ground level). Static walls, paintings, and "
                "furniture must remain 100% rigid and completely still."
            )

        current_prompt = (
            f"{base_prompt}\n\n"
            f"[CRITICAL REFINEMENT DIRECTIVES FOR ATTEMPT "
            f"{attempt_num + 1}]:\n"
            f"{refinements_block}{motion_refinement}"
        )

    # 5. Selection Strategy: Pick winning candidate
    if winning_candidate is None:
        valid_candidates = [c for c in candidates if c.video_bytes is not None]
        if valid_candidates:
            winning_candidate = max(
                valid_candidates,
                key=lambda c: (
                    c.scorecard.total_score,
                    c.scorecard.subject_realism.score,
                ),
            )
            subj_score = winning_candidate.scorecard.subject_realism.score
            tot_score = winning_candidate.scorecard.total_score
            selection_reason = (
                f"Selected attempt {winning_candidate.attempt_number} with "
                f"highest Subject score ({subj_score:.1f}/25) and composite "
                f"score ({tot_score:.1f}/100) after {len(candidates)} attempts."
            )
        elif candidates:
            winning_candidate = candidates[-1]
            selection_reason = "Fallback to last candidate."
        else:
            raise RuntimeError(
                f"Scene {scene_number}: All {max_attempts} attempts failed "
                "to generate video bytes."
            )
    else:
        tot_score = winning_candidate.scorecard.total_score
        selection_reason = (
            f"Attempt {passed_on_attempt} met pass threshold (Score: "
            f"{tot_score:.1f}/100 >= {pass_threshold:.1f})."
        )

    return ClipEvaluationLoopResult(
        scene_number=scene_number,
        total_attempts=len(candidates),
        passed_on_attempt=passed_on_attempt,
        selected_attempt=winning_candidate.attempt_number,
        winning_candidate=winning_candidate,
        all_candidates=candidates,
        selection_reason=selection_reason,
    )
