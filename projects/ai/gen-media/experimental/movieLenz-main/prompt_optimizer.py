# Copyright 2025 Google LLC
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

"""A module for optimizing prompts for video generation."""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import llm_interaction_vertex
import prompts
from google.api_core import exceptions


class PromptOptimizer:
    """Optimizes text prompts for video generation using DSG/CMK questions.

    It uses DSG/CMK questions derived from the prompt and optional start/end
    frames.
    """

    def __init__(
        self, gemini_caller: llm_interaction_vertex.GeminiVertexCaller
    ):
        """Initializes the PromptOptimizer.

        Args:
          gemini_caller: An instance of GeminiCaller for interacting with
            the LLM.
        """
        self.gemini_caller = gemini_caller
        self.common_mistake_questions = ""
        self.dsg_questions = ""
        self.evaluation_score = []
        self.evaluation_feedback = []
        self.refined_prompt = []
        logging.info("PromptOptimizer initialized.")

    def _extract_all_nodes_and_parent_map(
        self, graph_data_list: List[List[Dict[str, Any]]]
    ) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
        """Extracts all nodes and a child-to-parent ID map from graph data.

        Args:
            graph_data_list: A list of graph structures (e.g., from parsed
                DSG or Common Mistake JSONs, where each structure like
                "scene_graph" or "common_mistakes_graph" is a list of root
                node dictionaries).

        Returns:
            A tuple containing:
                - all_nodes_map: A dictionary mapping node ID to the node's
                  data.
                - parent_map: A dictionary mapping a child node ID to its
                  parent node ID.
        """
        all_nodes: Dict[str, Dict[str, Any]] = {}
        parent_map: Dict[str, str] = {}

        def recurse_graph(
            nodes: List[Dict[str, Any]], parent_id: Optional[str] = None
        ):
            for node in nodes:
                node_id = node.get("id")
                if not node_id:
                    logging.warning(
                        "Node missing ID: %s", node.get("description", "N/A")
                    )
                    continue

                all_nodes[node_id] = node
                if parent_id:
                    parent_map[node_id] = parent_id

                children = node.get("children", [])
                if children:
                    recurse_graph(children, node_id)

        for graph_root_list in graph_data_list:  # e.g. scene_graph list
            recurse_graph(graph_root_list)
        return all_nodes, parent_map

    def _is_node_evaluation_valid_in_graph(
        self,
        node_id: str,
        llm_evaluations_map: Dict[str, str],
        parent_map: Dict[str, str],
    ) -> bool:
        """Checks if a node's 'Yes' evaluation is valid.

        A node's 'Yes' is valid if the node itself is 'Yes' and all its
        ancestors up to the root are also 'Yes'.

        Args:
            node_id: The ID of the node to check.
            llm_evaluations_map: Map of node ID to LLM's answer
                ("yes"/"no").
            parent_map: Map of child node ID to parent node ID.

        Returns:
            True if the node's 'Yes' evaluation is valid in the graph
            context, False otherwise.
        """
        current_id: Optional[str] = node_id
        while current_id:
            if llm_evaluations_map.get(current_id) != "yes":
                return (
                    False  # This node or an ancestor is 'No' or not evaluated
                )
            current_id = parent_map.get(current_id)  # Move to parent
        return True  # All ancestors (and node itself) are 'Yes'

    def _generate_dsg_questions(
        self,
        initial_prompt: str,
        start_frame_bytes: bytes | None = None,
        end_frame_bytes: bytes | None = None,
        start_frame_mime_type: str = "image/png",
        end_frame_mime_type: str = "image/png",
    ) -> str:
        """Generates DSG-style questions based on the prompt and optional
        frames.

        Args:
          initial_prompt: The initial text prompt.
          start_frame_bytes: Optional bytes for the start frame image.
          end_frame_bytes: Optional bytes for the end frame image.
          start_frame_mime_type: MIME type of the start frame image.
          end_frame_mime_type: MIME type of the end frame image.

        Returns:
          A string containing DSG-style questions generated by the LLM.
        """
        logging.info("Generating DSG questions based on prompt and frames...")
        dsg_prompt_parts = [
            "Analyze the provided text prompt and optional start/end frame "
            "images.",
            "Based on this information, generate a hierarchical (tree-like) "
            "set",
            (
                "of questions following the principles of Davidsonian Scene "
                "Graphs (DSG)."
            ),
            "Identify key scene components (e.g., agents, actions, patients,",
            "locations, attributes, manners).",
            (
                "For each component, formulate a specific yes/no question "
                'where a "yes"'
            ),
            "answer indicates correct depiction.",
            "Organize these components and their questions into a JSON object.",
            'The JSON structure should have a main key as "scene_graph",',
            "which is a list of root elements.",
            "Each element should have at least",
            '"id" (a unique identifier for the question node),',
            '"element_type" (e.g., "agent", "action", "object", "location",',
            '"attribute"), "description" (a brief description of the element),',
            '"question" (the yes/no question), and "children" (a list of',
            "sub-elements, which can be empty).",
            "Example of an element structure:",
            # Note: Escaping curly braces for f-string if they were dynamic,
            # but here they are literal.
            # For f-strings, double them: {{ and }}
            """
        {
          "id": "agent_red_bird_1",
          "element_type": "agent",
          "description": "A red bird",
          "question": "Is there a red bird present?",
          "children": [
            {
              "id": "action_bird_flying_1",
              "element_type": "action",
              "description": "The red bird is flying",
              "question": "Is the red bird flying?",
              "children": []
            }
          ]
        }
        """,
            (
                "Ensure the entire output is a single valid JSON object. Insure"
                " that there are no more than 20 total questions."
            ),
            f'\nInitial Prompt: "{initial_prompt}"\n',
        ]

        inputs_for_gemini: List[Any] = []

        if start_frame_bytes:
            dsg_prompt_parts.append(
                "Consider the first image provided as the potential start "
                "frame."
            )
            inputs_for_gemini.append((start_frame_bytes, start_frame_mime_type))
        if end_frame_bytes:
            dsg_prompt_parts.append(
                "Consider the second image provided (if applicable) as the "
                "potential end frame."
            )
            inputs_for_gemini.append((end_frame_bytes, end_frame_mime_type))
        dsg_prompt_parts.append(
            "\nGenerate the DSG questions based on all available information:"
        )
        dsg_prompt_text = "\n".join(dsg_prompt_parts)
        inputs_for_gemini.append(dsg_prompt_text)  # Add text prompt last
        try:
            # Use the underlying generate method which accepts a list
            dsg_questions = self.gemini_caller.call_with_list(
                inputs_for_gemini, response_mime_type="application/json"
            )
            logging.info("Successfully generated DSG questions.")
            logging.debug("Generated DSG Questions:\n%s", dsg_questions)
            return dsg_questions
        except (
            exceptions.GoogleAPIError,
            ValueError,
            RuntimeError,
        ) as model_err:
            logging.error(
                "Failed to generate DSG questions: %s", model_err, exc_info=True
            )
            return "Error generating DSG questions."

    def _build_rating_prompt(
        self,
        original_prompt: str,
        dsg_questions: str,
        common_mistake_questions: str,
    ) -> str:
        """Builds the prompt for the video rating LLM call."""
        rating_prompt_parts = [
            "You are a video generation quality evaluator.",
            (
                "Analyze the provided video based on the original text prompt "
                "and evaluate how well it addresses *each* of the derived DSG "
                "questions and common mistake questions."
            ),
            f'Original Prompt: "{original_prompt}"',
            "\nDSG Questions to Evaluate Against (JSON format):",
            f"{dsg_questions}",
            "\nCommon Mistake Questions to Evaluate Against (JSON format):",
            f"{common_mistake_questions}",
            "\nInstructions:",
            (
                "1. For *each* question from the provided JSON structures "
                "above, determine if the video accurately depicts the aspect "
                "described."
            ),
            (
                '2. Assign a simple "Yes" or "No" answer for each question '
                "based on the video content."
            ),
            (
                '3. Extract the "id" and "element_type" associated with each '
                "question from the input JSONs."
            ),
            (
                "4. Provide brief textual feedback explaining the evaluation, "
                "highlighting which key aspects (based on question IDs) were "
                "successfully depicted (Yes) and which were missed or "
                "inaccurate (No)."
            ),
            (
                "5. Format your entire response as a single JSON object "
                'containing the per-question answers (linked by their "id"), '
                "their element types, and the overall feedback. Do not repeat "
                "the question text in your response."
            ),
            "\nOutput Format (Strict JSON):",
            "{",
            (
                '  "feedback": "[Your textual feedback explaining the '
                'evaluation based on the Yes/No answers]"'
            ),
            '  "question_evaluations": [',
            (
                '    {"id": "id_from_input1", "element_type":'
                ' "type_from_input_json1", "answer": "Yes/No"},'
            ),
            (
                '    {"id": "id_from_input2", "element_type":'
                ' "type_from_input_json2", "answer": "Yes/No"},'
            ),
            "    ...",
            (
                '    {"id": "id_from_inputN", "element_type":'
                ' "type_from_input_jsonN", "answer": "Yes/No"}'
            ),
            "  ],",
            "}",
        ]
        return "\n".join(rating_prompt_parts)

    def _rate_video_and_parse_feedback(
        self,
        video_bytes: bytes,
        video_mime_type: str,
        rating_meta_prompt: str,
        dsg_questions: str,  # Parameter to be used
        common_mistake_questions: str,  # Parameter to be used
    ) -> Tuple[Optional[Dict[str, Any]], float, str]:
        """Calls LLM to rate video, parses JSON, returns parsed data,
        graph-aware score, feedback."""
        rating_inputs: List[Any] = [
            (video_bytes, video_mime_type),
            rating_meta_prompt,
        ]
        evaluation_score = 0.0
        feedback_text = "Error during evaluation."
        graphs_to_process = []

        try:
            # Use the dsg_questions parameter
            if (
                dsg_questions
                and dsg_questions != "Error generating DSG questions."
            ):
                # Clean potential markdown
                cleaned_dsg_json_str = str(dsg_questions).strip()
                if cleaned_dsg_json_str.startswith("```json\n"):
                    cleaned_dsg_json_str = cleaned_dsg_json_str.removeprefix(
                        "```json\n"
                    )
                if cleaned_dsg_json_str.endswith("\n```"):
                    cleaned_dsg_json_str = cleaned_dsg_json_str.removesuffix(
                        "\n```"
                    )
                parsed_dsg_graph = json.loads(cleaned_dsg_json_str)
                if "scene_graph" in parsed_dsg_graph:
                    graphs_to_process.append(parsed_dsg_graph["scene_graph"])
            if (
                common_mistake_questions
                and common_mistake_questions
                != "Error generating common mistake questions."
            ):
                cleaned_cm_json_str = str(common_mistake_questions).strip()
                if cleaned_cm_json_str.startswith("```json\n"):
                    cleaned_cm_json_str = cleaned_cm_json_str.removeprefix(
                        "```json\n"
                    )
                if cleaned_cm_json_str.endswith("\n```"):
                    cleaned_cm_json_str = cleaned_cm_json_str.removesuffix(
                        "\n```"
                    )
                parsed_cm_graph = json.loads(cleaned_cm_json_str)
                if "common_mistakes_graph" in parsed_cm_graph:
                    graphs_to_process.append(
                        parsed_cm_graph["common_mistakes_graph"]
                    )
        except json.JSONDecodeError as graph_json_err:
            logging.error(
                "Error parsing stored graph JSON: %s",
                graph_json_err,
                exc_info=True,
            )
            # Potentially return error or try to proceed without full graph
            # context. For now, we'll let it try to score based on LLM
            # output only, but graph-aware scoring will be compromised.
            # A more robust approach might be to return an error score
            # here.

        all_graph_nodes_map, parent_map = (
            self._extract_all_nodes_and_parent_map(graphs_to_process)
        )

        try:
            logging.info("Calling LLM for video rating and feedback...")
            rating_and_feedback_json_str = self.gemini_caller.call_with_list(
                rating_inputs, response_mime_type="application/json"
            )
            logging.info(
                "Successfully received video rating and feedback (JSON)."
            )
            logging.debug(
                "Raw Rating/Feedback JSON:\n%s", rating_and_feedback_json_str
            )

            try:
                cleaned_json_str = str(rating_and_feedback_json_str).strip()
                if cleaned_json_str.startswith("```json\n"):
                    cleaned_json_str = cleaned_json_str.removeprefix(
                        "```json\n"
                    )
                if cleaned_json_str.endswith("\n```"):
                    cleaned_json_str = cleaned_json_str.removesuffix("\n```")
                parsed_feedback_json = json.loads(cleaned_json_str)

                llm_evaluations = parsed_feedback_json.get(
                    "question_evaluations", []
                )
                feedback_text = parsed_feedback_json.get(
                    "feedback", "No feedback provided."
                )

                # Create a map of LLM answers for quick lookup
                llm_answers_map: Dict[str, str] = {
                    str(item.get("id")): str(item.get("answer", ""))
                    .strip()
                    .lower()
                    for item in llm_evaluations
                    if item.get("id")  # Ensure ID exists
                }

                valid_yes_count = 0
                # Score based on all nodes defined in the original graphs
                total_nodes_in_graphs = len(all_graph_nodes_map)

                if total_nodes_in_graphs > 0:
                    for node_id in all_graph_nodes_map:
                        # Check if this node's 'yes' is valid in the graph
                        # context
                        if self._is_node_evaluation_valid_in_graph(
                            node_id, llm_answers_map, parent_map
                        ):
                            valid_yes_count += 1
                    evaluation_score = valid_yes_count / total_nodes_in_graphs
                    logging.info(
                        "Graph-aware evaluation: %d Valid Yes / %d Total "
                        "Graph Nodes. Score: %.2f",
                        valid_yes_count,
                        total_nodes_in_graphs,
                        evaluation_score,
                    )
                elif llm_evaluations:
                    # LLM provided evals, but no original graphs found/parsed
                    logging.warning(
                        "LLM provided evaluations, but no original graph "
                        "nodes found/parsed for graph-aware scoring. Score "
                        "will be 0.0 or based on simple count if implemented "
                        "as fallback."
                    )
                    # Fallback to simple count if desired, or keep score 0.0
                    # For now, if total_nodes_in_graphs is 0, score remains 0.0
                else:
                    logging.warning(
                        "No questions found in LLM evaluation response or no "
                        "graph nodes to score against."
                    )
                    feedback_text = (
                        "Evaluation response did not contain questions or no "
                        "graph context."
                    )
                    evaluation_score = 0.0

            except json.JSONDecodeError as json_err:
                logging.error(
                    "Failed to parse LLM feedback JSON: %s\n"
                    "Raw response was: %s",
                    json_err,
                    rating_and_feedback_json_str,
                    exc_info=True,
                )
                feedback_text = f"Error parsing evaluation JSON: {json_err}"
                parsed_feedback_json = None
                evaluation_score = 0.0

        except (exceptions.GoogleAPIError, RuntimeError) as model_err:
            logging.error(
                "Failed to get video rating and feedback from LLM: %s",
                model_err,
                exc_info=True,
            )
            parsed_feedback_json = None
            evaluation_score = 0.0
            # feedback_text is already 'Error during evaluation.'

        return parsed_feedback_json, evaluation_score, feedback_text

    def _build_refinement_prompt(
        self,
        original_prompt: str,
        dsg_questions: str,
        common_mistake_questions: str,
        evaluation_score: float,
        feedback_text: str,
    ) -> str:
        """Builds the prompt for the refinement LLM call."""
        refinement_prompt_parts = [
            prompts.system_prompt_guidelines_sphere_woz,
            "\n---",
            (
                "\nTask: Refine the original video prompt based on the "
                "provided evaluation feedback."
            ),
            f'Original Prompt: "{original_prompt}"',
            f"\nVideo Evaluation Feedback:\n{feedback_text}",
            f"\nEvaluation Score (Yes/Total): {evaluation_score:.2f}",
            "\nDSG Questions (for context):",
            f"{dsg_questions}",
            "\nCommon Mistake Questions (for context):",
            f"{common_mistake_questions}",
            "\nInstructions:",
            (
                "1. Analyze the feedback text and score, which summarize how "
                "well the previous video addressed the DSG and common mistake "
                "questions."
            ),
            (
                "2. Revise the original prompt to address the identified "
                "issues and better guide the video generation model towards "
                "fulfilling all aspects implied by the DSG questions."
            ),
            (
                "3. Ensure the revised prompt remains concise (ideally under 80"
                " words) and adheres to the general video prompt guidelines."
            ),
            "---",
            "Output *only* the revised prompt text as a JSON object.",
            'The only key in the JSON should be "prompt".',
            "---",
        ]
        return "\n".join(refinement_prompt_parts)

    def _refine_prompt_with_llm(
        self, refinement_meta_prompt: str
    ) -> str | None:
        """Calls the LLM to refine the prompt based on feedback."""
        try:
            logging.info(
                "Calling LLM for prompt refinement based on feedback..."
            )
            refined_prompt = self.gemini_caller.call_with_text(
                refinement_meta_prompt, response_mime_type="application/json"
            )
            logging.info("Successfully refined prompt based on video feedback.")
            logging.debug("Raw Refined Prompt:\n%s", refined_prompt)

            # Simple cleaning
            cleaned_refined_json_str = str(refined_prompt).strip()
            if cleaned_refined_json_str.startswith("```json\n"):
                cleaned_refined_json_str = (
                    cleaned_refined_json_str.removeprefix("```json\n")
                )
            if cleaned_refined_json_str.endswith("\n```"):
                cleaned_refined_json_str = (
                    cleaned_refined_json_str.removesuffix("\n```")
                )
            optimized_prompt_json = json.loads(cleaned_refined_json_str)
            optimized_refined_prompt = optimized_prompt_json.get("prompt", "")
            # Optional: Add length check
            if len(optimized_refined_prompt.split()) > 80:
                logging.warning("Refined prompt exceeds 80 words.")

            return optimized_refined_prompt
        except (exceptions.GoogleAPIError, json.JSONDecodeError) as model_err:
            logging.error(
                "Failed to refine prompt based on feedback: %s",
                model_err,
                exc_info=True,
            )
            return None  # Indicate failure

    def rate_and_refine_prompt(
        self,
        video_bytes: bytes | None = None,
        video_mime_type: str = "video/mp4",
        original_prompt: str = "",
        dsg_questions: str = "",
        common_mistake_questions: str = "",
    ) -> Tuple[str, float, str]:
        """Rates a video and refines the prompt based on feedback.

        Args:
            video_bytes: Bytes of the generated video.
            video_mime_type: MIME type of the video (e.g., "video/mp4").
            original_prompt: The prompt used to generate the video.
            dsg_questions: DSG-style questions generated from the prompt.
            common_mistake_questions: Questions about common video generation
                flaws.

        Returns:
            A refined prompt string based on the video feedback, or the
            original prompt if an error occurs during the process.
        """
        logging.info(
            'Starting video rating and prompt refinement for: "%s"',
            original_prompt,
        )
        # 1. Build rating prompt
        rating_meta_prompt = self._build_rating_prompt(
            original_prompt, dsg_questions, common_mistake_questions
        )
        logging.debug("Video rating meta-prompt text:\n%s", rating_meta_prompt)

        # 2. Rate video, parse feedback, and calculate score
        parsed_feedback, evaluation_score, feedback_text = (
            self._rate_video_and_parse_feedback(
                video_bytes,
                video_mime_type,
                rating_meta_prompt,
                dsg_questions,
                common_mistake_questions,
            )
        )
        self.evaluation_score.append(evaluation_score)
        self.evaluation_feedback.append(feedback_text)
        # If rating or parsing failed, return original prompt
        if parsed_feedback is None:
            logging.warning(
                'Rating/parsing failed. Returning original prompt: "%s"',
                original_prompt,
            )
            return original_prompt, 0.0, feedback_text
        # 3. Build refinement prompt
        refinement_meta_prompt = self._build_refinement_prompt(
            original_prompt,
            dsg_questions,
            common_mistake_questions,
            evaluation_score,
            feedback_text,
        )
        logging.debug(
            "Prompt refinement meta-prompt text:\n%s", refinement_meta_prompt
        )
        # 4. Refine prompt using LLM
        refined_prompt = self._refine_prompt_with_llm(refinement_meta_prompt)

        # If refinement failed, return original prompt
        if refined_prompt is None:
            logging.warning(
                'Refinement failed. Returning original prompt: "%s"',
                original_prompt,
            )
            return original_prompt, 0.0, feedback_text

        return refined_prompt, evaluation_score, feedback_text

    def _generate_common_mistake_questions(
        self,
        initial_prompt: str,
        start_frame_bytes: bytes | None = None,
        end_frame_bytes: bytes | None = None,
        start_frame_mime_type: str = "image/png",
        end_frame_mime_type: str = "image/png",
    ) -> str:
        """Generates questions about potential common video flaws based on
        the prompt."""
        logging.info(
            "Generating common mistake questions based on prompt and "
            "frames..."
        )
        mistake_prompt_parts = [
            "Analyze the provided text prompt and optional start/end frame "
            "images.",
            (
                "Based on this information, generate a hierarchical "
                "(tree-like) set of questions targeting potential common "
                "video generation mistakes that might occur when trying to "
                "generate a video for this prompt."
            ),
            "Consider only the issues such as:",
            "- Unnatural Transitions",
            (
                "- Anatomical Inconsistencies (missing/extra limbs/digits,"
                " distorted parts)"
            ),
            "- Environmental Inconsistencies (objects appearing/disappearing)",
            "- Illogical Changes within shots",
            "- Static Elements that should move",
            "- extra characters and objects",
            "- human characters speaking (they should never speak)",
            "- Inconsistent Detail/Texture",
            "\nOrganize these components and their questions into a JSON "
            "object.",
            (
                "The JSON structure should have a main key as "
                '"common_mistakes_graph", which is a list of root elements.'
            ),
            (
                'Each element should have at least "id" (a unique identifier '
                'for the question node),  "element_type" (e.g., '
                '"mistake_category", "specific_mistake"), "description" (a '
                'brief description of the mistake/category), "question" (the '
                'yes/no question where "yes" indicates no mistake), and '
                '"children" (a list of sub-elements, which can be empty).'
            ),
            "Example of an element structure:",
            """
        {
          "id": "mistake_cat_transitions_1",
          "element_type": "mistake_category",
          "description": "Unnatural Transitions",
          "question": "Are all transitions between shots smooth and logical?",
          "children": [
            {
              "id": "specific_mistake_jump_cut_1",
              "element_type": "specific_mistake",
              "description": "Potential jump cut between scene A and B",
              "question": "Is the transition from scene A to B free of "
                          "jarring jump cuts?",
              "children": []
            }
          ]
        }
        """,
            (
                "Ensure the entire output is a single, complete, and valid "
                "JSON object, starting with { and ending with }. Make sure all "
                "brackets and braces are correctly matched and closed. Insure "
                "that there are no more than 20 questions in the entire tree."
            ),
            f'\nInitial Prompt: "{initial_prompt}"\n',
            (
                "All questions should be framed as a yes or no question such "
                'that "yes" is the correct answer (i.e., the mistake is '
                'avoided) and a "no" answer indicates a common mistake might '
                "be present."
            ),
        ]

        inputs_for_gemini: List[Any] = []

        if start_frame_bytes:
            mistake_prompt_parts.append(
                "Consider the first image provided as the potential start "
                "frame."
            )
            inputs_for_gemini.append((start_frame_bytes, start_frame_mime_type))
        if end_frame_bytes:
            mistake_prompt_parts.append(
                "Consider the second image provided (if applicable) as the "
                "potential end frame."
            )
            inputs_for_gemini.append((end_frame_bytes, end_frame_mime_type))

        mistake_prompt_parts.append(
            "\nGenerate the common mistake questions based on all available "
            "information:"
        )
        mistake_prompt_text = "\n".join(mistake_prompt_parts)
        inputs_for_gemini.append(mistake_prompt_text)  # Add text prompt last

        try:
            common_mistake_questions = self.gemini_caller.call_with_list(
                inputs_for_gemini, response_mime_type="application/json"
            )
            logging.info("Successfully generated common mistake questions.")
            logging.debug(
                "Generated Common Mistake Questions:\n%s",
                common_mistake_questions,
            )
            return common_mistake_questions
        except (
            exceptions.GoogleAPIError,
            ValueError,
            RuntimeError,
        ) as model_err:
            logging.error(
                "Failed to generate common mistake questions: %s",
                model_err,
                exc_info=True,
            )
            return "Error generating common mistake questions."

    def rate_video(
        self,
        video_bytes: bytes | None = None,
        video_mime_type: str = "video/mp4",
        original_prompt: str = "",
        dsg_questions: str = "",
        common_mistake_questions: str = "",
    ) -> Tuple[Optional[Dict[str, Any]], float, str]:
        """Rates a generated video against its prompt/DSG questions.

        Args:
            video_bytes: Bytes of the generated video.
            video_mime_type: MIME type of the video (e.g., "video/mp4").
            original_prompt: The prompt used to generate the video.
            dsg_questions: DSG-style questions generated from the prompt.
            common_mistake_questions: Questions about common video generation
                flaws.

        Returns:
            The evaluation score, feedback text, and parsed feedback.
        """
        logging.info('Starting video rating for: "%s"', original_prompt)
        # 1. Build rating prompt
        rating_meta_prompt = self._build_rating_prompt(
            original_prompt, dsg_questions, common_mistake_questions
        )
        logging.debug("Video rating meta-prompt text:\n%s", rating_meta_prompt)

        try:
            parsed_feedback, evaluation_score, feedback_text = (
                self._rate_video_and_parse_feedback(
                    video_bytes,
                    video_mime_type,
                    rating_meta_prompt,
                    dsg_questions,
                    common_mistake_questions,
                )
            )
            return parsed_feedback, evaluation_score, feedback_text
        except (exceptions.GoogleAPIError, RuntimeError) as model_err:
            logging.error(
                "Failed to rate video: %s",
                model_err,
                exc_info=True,
            )
            return None, 0.0, "Error rating video."

    def optimize_prompt(
        self,
        initial_prompt: str,
        start_frame_bytes: bytes | None = None,
        end_frame_bytes: bytes | None = None,
        video_duration: int | None = None,
        technical_notes: str | None = None,
    ) -> str:
        """Optimizes an initial prompt for video generation.

        Uses DSG and common mistake questions to improve the prompt.
        """
        # 1a. Generate DSG questions based on prompt and frames
        dsg_questions = self._generate_dsg_questions(
            initial_prompt, start_frame_bytes, end_frame_bytes
        )
        if "Error generating" in dsg_questions:
            logging.warning(
                "Could not generate DSG questions, proceeding without them."
            )
            dsg_questions = (
                ""  # Continue without DSG questions if generation fails
            )

        # 1b. Generate Common Mistake questions based on prompt and frames
        common_mistake_questions = self._generate_common_mistake_questions(
            initial_prompt, start_frame_bytes, end_frame_bytes
        )
        if "Error generating" in common_mistake_questions:
            logging.warning(
                "Could not generate common mistake questions, proceeding "
                "without them."
            )
            common_mistake_questions = (
                ""  # Continue without them if generation fails
            )
        self.dsg_questions = dsg_questions
        self.common_mistake_questions = common_mistake_questions
        # Combine generated questions
        all_generated_questions = ""
        if dsg_questions:
            all_generated_questions += "--- DSG Questions ---\n" + dsg_questions
        if common_mistake_questions:
            if all_generated_questions:  # Add newline if DSG questions exist
                all_generated_questions += "\n\n"
            all_generated_questions += (
                "--- Potential Common Mistakes Questions ---\n"
                + common_mistake_questions
            )

        if not all_generated_questions:
            logging.warning("No questions generated, returning initial prompt.")
            return initial_prompt

        # 2. Construct the meta-prompt for final optimization using guidelines
        optimization_meta_prompt_parts = [
            prompts.system_prompt_guidelines_sphere_woz,
            "\n---",
            "\nInputs for this specific task:",
            f'starter_text_prompt: "{initial_prompt}"',
        ]
        # ... add optional inputs (duration, notes, frames indication) ...
        if video_duration:
            optimization_meta_prompt_parts.append(
                f"video_duration: {video_duration}"
            )
        if technical_notes:
            optimization_meta_prompt_parts.append(
                f'technical_notes: "{technical_notes}"'
            )
        if start_frame_bytes:
            optimization_meta_prompt_parts.append(
                "start_image_frame: [Provided]"
            )
        if end_frame_bytes:
            optimization_meta_prompt_parts.append("end_image_frame: [Provided]")

        optimization_meta_prompt_parts.extend(
            [
                "\nAdditional Context (Generated Questions):",
                f"{all_generated_questions}\n",  # Use combined questions
                "---",
                (
                    "\nBased on all the above inputs and directives "
                    "(especially the generated questions which highlight key "
                    "aspects and potential pitfalls), generate the final "
                    "optimized prompt."
                ),
                (
                    "Remember to adhere strictly to all Key Directives, "
                    "especially conciseness (under 80 words) and continuity."
                ),
                (
                    "Output *only* the revised prompt text in a json object. "
                    'Do not include "Director" or any other text.'
                ),
                'The json object should only have a key named "prompt".',
            ]
        )

        optimization_meta_prompt = "\n".join(optimization_meta_prompt_parts)
        # ... rest of the method (_call_with_text, logging, cleaning,
        # return) ...
        logging.debug(
            "Optimization meta-prompt text:\n%s", optimization_meta_prompt
        )

        # 3. Call Gemini with the text-based optimization prompt
        logging.info("Calling LLM for final prompt optimization...")
        try:
            optimized_prompt = self.gemini_caller.call_with_text(
                optimization_meta_prompt, response_mime_type="application/json"
            )

            logging.info("Successfully optimized prompt.")
            logging.debug("Raw Optimized Prompt:\n%s", optimized_prompt)

            # Simple cleaning
            cleaned_optimized_json_str = str(optimized_prompt).strip()
            if cleaned_optimized_json_str.startswith("```json\n"):
                cleaned_optimized_json_str = (
                    cleaned_optimized_json_str.removeprefix("```json\n")
                )
            if cleaned_optimized_json_str.endswith("\n```"):
                cleaned_optimized_json_str = (
                    cleaned_optimized_json_str.removesuffix("\n```")
                )
            optimized_prompt_json = json.loads(cleaned_optimized_json_str)
            optimized_prompt = optimized_prompt_json.get("prompt", "")
            # Optional: Add length check based on guidelines
            if len(optimized_prompt.split()) > 80:
                logging.warning("Optimized prompt exceeds 80 words.")
                # Decide how to handle this - truncate, log, or return as is
            self.refined_prompt.append(optimized_prompt)
            return optimized_prompt
        except (exceptions.GoogleAPIError, json.JSONDecodeError) as model_err:
            logging.error(
                "Failed to optimize prompt: %s", model_err, exc_info=True
            )
            # Fallback to initial prompt on error
            return initial_prompt
