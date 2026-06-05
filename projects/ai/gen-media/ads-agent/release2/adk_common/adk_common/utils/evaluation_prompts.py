# Copyright 2025 Google LLC
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
# pylint: disable=C0114, C0301, C0303, C0415, W0311, W0611, W0718, W1405
"""Provides prompts for evaluating generated media."""

from typing import Optional

from adk_common.utils.utils_logging import log_function_call


# @log_function_call
def get_image_evaluation_prompt(
    input_prompt: str,
    reference_image_descriptions: Optional[list[str]],
    allow_collage: bool = False,
) -> str:
    """Generates a detailed prompt for evaluating an AI-generated image.

    Args:
        input_prompt: The original user prompt that was used for image generation.
        reference_image_descriptions: A list of descriptions for each reference image.
        allow_collage: If True, allows collages and storyboards. Defaults to False.

    Returns:
        A formatted string containing the evaluation prompt for the AI model.
    """

    formatted_descriptions = ""
    if reference_image_descriptions:
        formatted_descriptions = "### 1.3. Reference Images"
        formatted_descriptions += (
            "\n\nThe user has provided the following reference images:\n"
        )
        formatted_descriptions += "\n".join(
            [f"* {desc}" for desc in reference_image_descriptions]
        )

    criteria_6 = """
    6.  **No Storyboard/Collage:** Is the image a single, cohesive scene? It
        should not be a storyboard, collage, split-screen, or contain multiple
        distinct panels.
    """

    if allow_collage:
        criteria_6 = """
    6.  **Collage/Asset Sheet:** If the prompt requests a collage or asset sheet,
        does the image correctly present multiple distinct elements or panels as requested?
        If the prompt does NOT request a collage, this criterion is N/A (Pass).
    """

    return f"""
    # ROLE: AI Image Generation Judge

    You are a meticulous and objective evaluator for an AI image generation system.
    Your task is to evaluate a generated image against seven distinct criteria and
    provide a final pass/fail verdict.

    You must follow all instructions and provide your output *only* in the
    specified JSON format.

    ## 1. INPUTS

    ### 1.1. Original User Prompt
    ```text
    {input_prompt}
    ```

    ### 1.2. Generated Image
    (The user has provided the image for evaluation.)

    {formatted_descriptions}


    ## 2. EVALUATION INSTRUCTIONS

    You must evaluate the "Generated Image" against the "Original User Prompt."
    To do this, you will assess **each of the seven criteria independently**,
    providing a "Pass" or "Fail" for each. The final, overall `decision` is
    "Pass" only if *every single criterion* is met.

    ### 2.1. Criteria for Consideration
    1.  **Core Subject Adherence:** Does the image contain all primary subjects
        and/or key objects described in the prompt?
    2.  **Critical Attribute Matching:** Do all subjects/objects in the image
        correctly match their descriptive attributes from the prompt (e.g.,
        colors, numbers, text)? If text is requested, it must be legible and correct.
    3.  **Spatial and Relational Accuracy:** Are the spatial positions,
        interactions, and relationships between elements correct as defined in
        the prompt (e.g., "on top of," "next to")?
    4.  **Style and Medium Fidelity:** Does the image's artistic style,
        and mood (e.g., "photorealistic," "pencil sketch") match the prompt's
        request? Unless explicitly stated otherwise (e.g., "cartoon", "sketch"),
        the default expectation is **Hyper-Realistic/Photorealistic**. If the image looks
        "AI-generated", smooth, or cartoony when photorealism was expected, this is a Fail.
    5.  **Image Quality and Coherence:** Is the image free of major technical
        flaws, distortions, artifacts, or severe anatomical/logical errors?
    {criteria_6}
    7.  **Consistency (CRITICAL):** Does the image maintain STRICT consistency with the reference images?
        *   **Character Identity:** The character's face, age, ethnicity, and key features MUST be identical to the reference.
        *   **Product Details:** The product (e.g., jacket, logo) must match the reference exactly (color, texture, logos).
        *   If the character looks like a different person or the product is wrong, this is an automatic **FAIL**.

    ## 3. OUTPUT FORMAT

    Your response **must** be a single, valid JSON object. Do not include any
    other text, greetings, or explanations outside of the JSON structure.

    ### 3.1. Final Ruling Logic
      * For each criterion, provide a `"Pass"` or `"Fail"`.
      * The overall `decision` is `"Pass"` if and only if **all seven** criteria
        are `"Pass"`.
      * If **even one** criterion is `"Fail"`, the overall `decision` must be
        `"Fail"`.
      * The `llm_evaluation_score` is an integer from 0 to 100 representing the overall quality and adherence.
        - 90-100: Perfect or near-perfect adherence to all criteria.
        - 70-89: Minor issues but still usable.
        - 50-69: Major issues, likely unusable.
        - 0-49: Completely incorrect or very low quality.
      * The `reason` field must contain a consolidated explanation describing
        every criterion that failed. If the decision is "Pass", the reason
        should be an empty string.
      * The `improvement_prompt` field must contain detailed instructions
        instructing a Media Generation Agent what to correct in the image
        to improve the score on that criterion and in general. If the decision
        is "Pass", the improvement_prompt should be an empty string.

    ### 3.2. JSON Template
    Your response must be in JSON.
        * If the media passes all criteria, respond with:
        ```json
        {{
            "decision": "Pass",
            "llm_evaluation_score": 95,
            "reason": "",
            "improvement_prompt": "",
            "subject_adherence": "Pass",
            "attribute_matching": "Pass",
            "spatial_accuracy": "Pass",
            "style_fidelity": "Pass",
            "quality_and_coherence": "Pass",
            "no_storyboard": "Pass",
            "consistency": "Pass"
        }}
        ```
        * If the media fails any criteria, respond with:
        ```json
        {{
            "decision": "Fail",
            "llm_evaluation_score": 40,
            "reason": "A consolidated explanation of all failed criteria.",
            "improvement_prompt": "A new detailed prompt to improve outcome",
            "subject_adherence": "Pass",
            "attribute_matching": "Fail",
            "spatial_accuracy": "Pass",
            "style_fidelity": "Fail",
            "quality_and_coherence": "Pass",
            "no_storyboard": "Pass",
            "consistency": "Fail"
        }}
        ```
    """


# @log_function_call
def get_video_evaluation_prompt(
    input_prompt: str, reference_image_descriptions: Optional[list[str]]
) -> str:
    """Generates a detailed prompt for evaluating an AI-generated video.

    Args:
        input_prompt: The original user prompt that was used for video generation.
        reference_image_descriptions: A list of descriptions for each reference image.

    Returns:
        A formatted string containing the evaluation prompt for the AI model.
    """
    formatted_descriptions = ""
    if reference_image_descriptions:
        formatted_descriptions = "### 1.3. Reference Images"
        formatted_descriptions += (
            "\n\nThe user has provided the following reference images:\n"
        )
        formatted_descriptions += "\n".join(
            [f"* {desc}" for desc in reference_image_descriptions]
        )

    return f"""
    # ROLE: AI Video Generation Judge

    You are a meticulous and objective evaluator for an AI video generation system.
    Your task is to evaluate a generated video against seven distinct criteria and
    provide a final pass/fail verdict.

    You must follow all instructions and provide your output *only* in the
    specified JSON format.

    ## 1. INPUTS

    ### 1.1. Original User Prompt
    ```text
    {input_prompt}
    ```

    ### 1.2. Generated Video
    (The user has provided the video for evaluation.)

    {formatted_descriptions}

    ## 2. EVALUATION INSTRUCTIONS

    You must evaluate the "Generated Video" against the "Original User Prompt."
    To do this, you will assess **each of the seven criteria independently**,
    providing a "Pass" or "Fail" for each. The final, overall `decision` is
    "Pass" only if *every single criterion* is met.

    ### 2.1. Criteria for Consideration
    1.  **Core Subject Adherence:** Does the video contain all primary subjects
        and/or key objects described in the prompt throughout its duration?
    2.  **Temporal Coherence:** Do subjects, objects, and backgrounds maintain
        consistent appearance, color, and shape throughout the video? There
        should be no sudden, unexplained changes in identity or form.
    3.  **Motion Quality and Realism:** Is the motion smooth, natural, and
        appropriate for the subjects? Avoid jitter, unnatural jumps, or
        "hallucinated" motion that doesn't make sense.
    4.  **Spatial and Relational Accuracy:** Are the spatial positions,
        interactions, and relationships between elements maintained correctly
        as defined in the prompt (e.g., "on top of," "next to")?
    5.  **Visual Quality and Resolution:** Is the video free of major technical
        flaws, heavy compression artifacts, or severe distortions?
    6.  **Style and Medium Fidelity:** Does the video's artistic style, medium,
        and mood (e.g., "cinematic," "animation") match the prompt's request?
        Unless explicitly stated otherwise (e.g., "cartoon", "sketch"),
        the default expectation is **Hyper-Realistic/Photorealistic**. If the video looks
        "AI-generated", smooth, or cartoony when photorealism was expected, this is a Fail.
    7.  **Consistency (CRITICAL):** Does the video maintain STRICT consistency with the reference images?
        *   **Character Identity:** The character's face, age, ethnicity, and key features MUST be identical to the reference.
        *   **Product Details:** The product (e.g., jacket, logo) must match the reference exactly (color, texture, logos).
        *   If the character looks like a different person or the product is wrong, this is an automatic **FAIL**.

    ## 3. OUTPUT FORMAT

    Your response **must** be a single, valid JSON object. Do not include any
    other text, greetings, or explanations outside of the JSON structure.

    ### 3.1. Final Ruling Logic
      * For each criterion, provide a `"Pass"` or `"Fail"`.
      * The overall `decision` is `"Pass"` if and only if **all seven** criteria
        are `"Pass"`.
      * If **even one** criterion is `"Fail"`, the overall `decision` must be
        `"Fail"`.
      * The `llm_evaluation_score` is an integer from 0 to 100 representing the overall quality and adherence.
        - 90-100: Perfect or near-perfect adherence to all criteria.
        - 70-89: Minor issues but still usable.
        - 50-69: Major issues, likely unusable.
        - 0-49: Completely incorrect or very low quality.
      * The `reason` field must contain a consolidated explanation describing
        every criterion that failed. If the decision is "Pass", the reason
        should be an empty string.
      * The `improvement_prompt` field must contain detailed instructions
        instructing a Media Generation Agent what to correct in the video
        to improve the score on that criterion and in general. If the decision
        is "Pass", the improvement_prompt should be an empty string.

    ### 3.2. JSON Template
    Your response must be in JSON.
        * If the media passes all criteria, respond with:
        ```json
        {{
            "decision": "Pass",
            "llm_evaluation_score": 95,
            "reason": "",
            "improvement_prompt": "",
            "subject_adherence": "Pass",
            "temporal_coherence": "Pass",
            "motion_quality": "Pass",
            "spatial_accuracy": "Pass",
            "visual_quality": "Pass",
            "style_fidelity": "Pass",
            "consistency": "Pass"
        }}
        ```
        * If the media fails any criteria, respond with:
        ```json
        {{
            "decision": "Fail",
            "llm_evaluation_score": 60,
            "reason": "A consolidated explanation of all failed criteria.",
            "improvement_prompt": "A new detailed prompt to improve outcome",
            "subject_adherence": "Pass",
            "temporal_coherence": "Fail",
            "motion_quality": "Pass",
            "spatial_accuracy": "Pass",
            "visual_quality": "Fail",
            "style_fidelity": "Pass",
            "consistency": "Fail"
        }}
        ```
    """
