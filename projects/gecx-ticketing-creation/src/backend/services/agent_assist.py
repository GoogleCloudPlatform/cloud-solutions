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


# pylint: disable=line-too-long, broad-exception-caught
"""Module containing GECX agent assist logic."""

import datetime
import os
import re

from google.cloud import dialogflow_v2beta1 as dialogflow
from google.protobuf.timestamp_pb2 import Timestamp


class AgentAssistService:
    """Service class for Dialogflow CX Agent Assist operations."""

    def __init__(self):
        # Default to 'us-central1' regional endpoint to support us-central1 Dialogflow CX agents
        client_options = {
            "api_endpoint": "us-central1-dialogflow.googleapis.com:443"
        }
        self.conv_client = dialogflow.ConversationsClient(
            client_options=client_options
        )
        self.part_client = dialogflow.ParticipantsClient(
            client_options=client_options
        )

    def get_or_create_conversation_profile(self, project_id: str = None) -> str:
        """
        Dynamically finds or provisions the conversation profile in the target project.
        """
        if not project_id:
            project_id = os.getenv("GCP_PROJECT_ID")
        if not project_id:
            raise ValueError(
                "GCP_PROJECT_ID environment variable or project_id parameter"
                " is required."
            )

        # Use us-central1 regional endpoint
        client_options = {
            "api_endpoint": "us-central1-dialogflow.googleapis.com:443"
        }
        profile_client = dialogflow.ConversationProfilesClient(
            client_options=client_options
        )
        parent = f"projects/{project_id}/locations/us-central1"
        display_name = "cymbal_coaching_profile_uc"

        try:
            # 1. Search for existing profile with the same display name
            for p in profile_client.list_conversation_profiles(parent=parent):
                if p.display_name == display_name:
                    print(
                        f"[AgentAssistService] Found existing profile: {p.name}"
                    )
                    return p.name
        except Exception as e:
            print(
                f"[AgentAssistService] Listing conversation profiles failed: {e}"
            )

        # 2. Provision new conversation profile pointing to our cymbal-support-agent ID in us-central1
        agent_id = os.getenv("DF_AGENT_ID")
        if not agent_id:
            raise ValueError(
                "DF_AGENT_ID environment variable is required to provision"
                " conversation profile."
            )
        if "projects/" in agent_id:
            agent_path = agent_id
        else:
            agent_path = (
                f"projects/{project_id}/locations/us-central1/agents/{agent_id}"
            )

        profile = dialogflow.ConversationProfile(
            display_name=display_name,
            automated_agent_config=dialogflow.AutomatedAgentConfig(
                agent=agent_path
            ),
        )
        try:
            created = profile_client.create_conversation_profile(
                parent=parent, conversation_profile=profile
            )
            print(
                f"[AgentAssistService] Programmatically created new conversation profile: {created.name}"
            )
            return created.name
        except Exception as e:
            print(
                f"[AgentAssistService] Failed to create conversation profile: {e}"
            )
            raise e

    def create_conversation(self, conversation_profile_id: str) -> dict:
        """
        Creates a Dialogflow conversation and registers END_USER, AUTOMATED_AGENT, and HUMAN_AGENT participants.
        Returns a dict containing participant resource names and the conversation name.
        """
        # Traverse project resolution
        match = re.match(r"projects/([^/]+)", conversation_profile_id)
        project_id = (
            match.group(1)
            if match
            else os.getenv("GCP_PROJECT_ID")
        )
        if not project_id:
            raise ValueError(
                "Could not determine GCP_PROJECT_ID from conversation profile"
                " or environment."
            )

        try:
            # Dual-Strategy Fallback: Attempt regional Conversation parent in us-central1 first (matching virtual agent)
            try:
                print(
                    f"[AgentAssistService] Attempting create_conversation in us-central1 for Profile '{conversation_profile_id}'"
                )
                parent = f"projects/{project_id}/locations/us-central1"
                conv_client = self.conv_client  # us-central1 client
                part_client = self.part_client
                conversation = dialogflow.Conversation(
                    conversation_profile=conversation_profile_id
                )
                created_conv = conv_client.create_conversation(
                    parent=parent, conversation=conversation
                )
            except Exception as e_reg:
                print(
                    f"[AgentAssistService] Regional create_conversation dropped ({e_reg}). Escaling to true global client and global parent."
                )
                # Force true global parent and global client
                parent = (
                    f"projects/{project_id}/locations/global"
                    if "/locations/global/" in conversation_profile_id
                    else f"projects/{project_id}"
                )
                client_options = {
                    "api_endpoint": "dialogflow.googleapis.com:443"
                }
                conv_client = dialogflow.ConversationsClient(
                    client_options=client_options
                )
                part_client = dialogflow.ParticipantsClient(
                    client_options=client_options
                )
                conversation = dialogflow.Conversation(
                    conversation_profile=conversation_profile_id
                )
                created_conv = conv_client.create_conversation(
                    parent=parent, conversation=conversation
                )

            conversation_name = created_conv.name

            # Create END_USER participant
            p_user = dialogflow.Participant(
                role=dialogflow.Participant.Role.END_USER
            )
            created_user = part_client.create_participant(
                parent=conversation_name, participant=p_user
            )

            # Create AUTOMATED_AGENT participant
            p_bot = dialogflow.Participant(
                role=dialogflow.Participant.Role.AUTOMATED_AGENT
            )
            created_bot = part_client.create_participant(
                parent=conversation_name, participant=p_bot
            )

            # Create HUMAN_AGENT participant
            p_agent = dialogflow.Participant(
                role=dialogflow.Participant.Role.HUMAN_AGENT
            )
            created_agent = part_client.create_participant(
                parent=conversation_name, participant=p_agent
            )

            return {
                "conversation_name": conversation_name,
                "end_user": created_user.name,
                "automated_agent": created_bot.name,
                "human_agent": created_agent.name,
            }
        except Exception as e:
            print(
                f"[AgentAssistService] create_conversation completely failed: {e}"
            )
            raise e

    def batch_create_messages(
        self,
        conversation_name: str,
        messages: list[dict],
        end_user_path: str,
        automated_agent_path: str,
    ) -> None:
        """
        Backfills pre-escalation chat history into the conversation.
        """
        try:
            requests = []
            base_time = datetime.datetime.now(
                datetime.timezone.utc
            ) - datetime.timedelta(minutes=len(messages))

            for idx, msg in enumerate(messages):
                # Associate the message with the correct participant path
                role = msg.get("sender")
                p_path = (
                    end_user_path
                    if role in ["user", "customer"]
                    else automated_agent_path
                )

                # Calculate relative send_time
                msg_time = base_time + datetime.timedelta(seconds=idx * 10)
                ts = Timestamp()
                ts.FromDatetime(msg_time)

                create_req = dialogflow.CreateMessageRequest(
                    parent=conversation_name,
                    message=dialogflow.Message(
                        content=msg.get("text", ""),
                        participant=p_path,
                        send_time=ts,
                    ),
                )
                requests.append(create_req)

            if not requests:
                return

            batch_req = dialogflow.BatchCreateMessagesRequest(
                parent=conversation_name, requests=requests
            )

            # Determine location client
            location = "global"
            match = re.search(
                r"projects/[^/]+/locations/([^/]+)/", conversation_name
            )
            if match:
                location = match.group(1)
                client_options = {
                    "api_endpoint": f"{location}-dialogflow.googleapis.com:443"
                }
                conv_client = dialogflow.ConversationsClient(
                    client_options=client_options
                )
            else:
                conv_client = self.conv_client

            conv_client.batch_create_messages(request=batch_req)
            print(
                f"[AgentAssistService] Successfully backfilled {len(requests)} messages."
            )
        except Exception as e:
            print(f"[AgentAssistService] batch_create_messages failed: {e}")
            raise e

    def list_conversation_messages(self, conversation_name: str) -> list[dict]:
        """
        Retrieves the complete message history from the conversation.
        """
        try:
            location = "global"
            match = re.search(
                r"projects/[^/]+/locations/([^/]+)/", conversation_name
            )
            if match:
                location = match.group(1)
                client_options = {
                    "api_endpoint": f"{location}-dialogflow.googleapis.com:443"
                }
                conv_client = dialogflow.ConversationsClient(
                    client_options=client_options
                )
            else:
                conv_client = self.conv_client

            request = dialogflow.ListMessagesRequest(parent=conversation_name)
            page_result = conv_client.list_messages(request=request)

            messages = []
            # ListMessages returns messages ordered by create_time in descending order.
            # We iterate and reverse them to display in chronological order.
            for msg in page_result:
                # Deduce role from participant path
                role = "user"
                if "participants/" in msg.participant:
                    if (
                        msg.participant.endswith("2")
                        or "automated_agent" in msg.participant
                    ):
                        role = "bot"
                    elif (
                        msg.participant.endswith("1")
                        or "human_agent" in msg.participant
                    ):
                        role = "agent"

                messages.append(
                    {
                        "sender": role,
                        "text": msg.content,
                        "send_time": (
                            msg.send_time.ToJsonString()
                            if msg.send_time
                            else ""
                        ),
                    }
                )

            messages.reverse()
            return messages
        except Exception as e:
            print(f"[AgentAssistService] list_messages failed: {e}")
            raise e

    def streaming_analyze_content(self, participant_name: str, audio_generator):
        """
        Pipes binary Int16 PCM audio chunks to Dialogflow, yielding suggestions parsed from responses.
        """
        # Regional endpoint deduction
        location = "global"
        match = re.search(
            r"projects/[^/]+/locations/([^/]+)/", participant_name
        )
        if match:
            location = match.group(1)
            client_options = {
                "api_endpoint": f"{location}-dialogflow.googleapis.com:443"
            }
            part_client = dialogflow.ParticipantsClient(
                client_options=client_options
            )
        else:
            part_client = self.part_client

        def request_generator():
            print("[Debug Service] request_generator started")
            # First request must configure input audio settings
            config = dialogflow.InputAudioConfig(
                audio_encoding=dialogflow.AudioEncoding.AUDIO_ENCODING_LINEAR_16,
                sample_rate_hertz=16000,
                language_code="en-US",
            )
            print("[Debug Service] request_generator yielding InputAudioConfig")
            yield dialogflow.StreamingAnalyzeContentRequest(
                participant=participant_name, audio_config=config
            )

            # Subsequent requests pipe binary audio chunks
            chunk_count = 0
            for chunk in audio_generator:
                chunk_count += 1
                if chunk_count % 50 == 0:
                    print(
                        f"[Debug Service] request_generator yielding audio chunk #{chunk_count}, size={len(chunk)}"
                    )
                yield dialogflow.StreamingAnalyzeContentRequest(
                    participant=participant_name, input_audio=chunk
                )
            print(
                f"[Debug Service] request_generator finished. Yielded total chunks: {chunk_count}"
            )

        try:
            print(
                f"[Debug Service] Calling part_client.streaming_analyze_content for {participant_name}"
            )
            responses = part_client.streaming_analyze_content(
                requests=request_generator()
            )
            print(
                "[Debug Service] Obtained responses iterator from streaming_analyze_content"
            )

            resp_count = 0
            for response in responses:
                resp_count += 1
                print(
                    f"[Debug Service] Received response #{resp_count} from Dialogflow streaming_analyze_content"
                )

                # Check for and yield live audio transcription result
                if (
                    response.recognition_result
                    and response.recognition_result.transcript
                ):
                    rec = response.recognition_result
                    print(
                        f"[Debug Service] Found Recognition Result: {rec.transcript} (final={rec.is_final})"
                    )
                    yield {
                        "type": "transcription",
                        "transcript": rec.transcript,
                        "is_final": rec.is_final,
                    }

                suggestions = []
                for result in response.human_agent_suggestion_results:
                    # Parse Smart Replies
                    if result.suggest_smart_replies_response:
                        for (
                            sr
                        ) in (
                            result.suggest_smart_replies_response.smart_replies
                        ):
                            print(
                                f"[Debug Service] Found Smart Reply: {sr.reply}"
                            )
                            suggestions.append(
                                {
                                    "type": "smart_reply",
                                    "reply": sr.reply,
                                    "confidence": getattr(
                                        sr, "confidence", 0.0
                                    ),
                                }
                            )
                    # Parse FAQ Answers
                    if result.suggest_faq_answers_response:
                        for (
                            faq
                        ) in result.suggest_faq_answers_response.faq_answers:
                            print(
                                f"[Debug Service] Found FAQ: {faq.question} -> {faq.answer}"
                            )
                            suggestions.append(
                                {
                                    "type": "faq",
                                    "question": faq.question,
                                    "answer": faq.answer,
                                    "confidence": getattr(
                                        faq, "confidence", 0.0
                                    ),
                                }
                            )
                    # Parse Knowledge Assist Suggestions
                    if result.suggest_knowledge_assist_response:
                        ka_resp = result.suggest_knowledge_assist_response
                        if ka_resp.suggested_query:
                            print(
                                f"[Debug Service] Found Knowledge Assist Query: {ka_resp.suggested_query.query_text}"
                            )
                            suggestions.append(
                                {
                                    "type": "knowledge_assist",
                                    "query": ka_resp.suggested_query.query_text,
                                }
                            )
                    # Parse Dialogflow Assist (AI Coach / Playbook / Coaching) Suggestions
                    if result.suggest_dialogflow_assists_response:
                        for (
                            da
                        ) in (
                            result.suggest_dialogflow_assists_response.dialogflow_assist_answers
                        ):
                            print(
                                f"[Debug Service] Found Dialogflow Assist suggestion: {da}"
                            )
                            text = ""
                            if da.query_result:
                                text = da.query_result.fulfillment_text
                                if (
                                    not text
                                    and da.query_result.response_messages
                                ):
                                    msg_texts = []
                                    for (
                                        msg
                                    ) in da.query_result.response_messages:
                                        if msg.text and msg.text.text:
                                            msg_texts.append(
                                                " ".join(msg.text.text)
                                            )
                                    text = "\n".join(msg_texts)
                            if text:
                                suggestions.append(
                                    {
                                        "type": "coaching",
                                        "reply": text,
                                        "confidence": 1.0,
                                    }
                                )
                    # Parse Generative suggestions
                    if result.generate_suggestions_response:
                        for (
                            gs
                        ) in (
                            result.generate_suggestions_response.generator_suggestion_answers
                        ):
                            print(
                                f"[Debug Service] Found Generator suggestion: {gs}"
                            )
                            sug = gs.generator_suggestion
                            if sug:
                                text = ""
                                if (
                                    sug.free_form_suggestion
                                    and sug.free_form_suggestion.response
                                ):
                                    text = sug.free_form_suggestion.response
                                elif sug.agent_coaching_suggestion:
                                    coaching_texts = []
                                    # 1. Parse applicable instructions
                                    for (
                                        inst
                                    ) in (
                                        sug.agent_coaching_suggestion.applicable_instructions
                                    ):
                                        desc = (
                                            inst.agent_action
                                            or inst.display_details
                                            or inst.display_name
                                        )
                                        if desc:
                                            coaching_texts.append(
                                                f"Instruction: {desc}"
                                            )
                                    # 2. Parse suggested actions
                                    for (
                                        action
                                    ) in (
                                        sug.agent_coaching_suggestion.agent_action_suggestions
                                    ):
                                        if action.agent_action:
                                            coaching_texts.append(
                                                f"Action: {action.agent_action}"
                                            )
                                    # 3. Parse sample responses
                                    for (
                                        sample
                                    ) in (
                                        sug.agent_coaching_suggestion.sample_responses
                                    ):
                                        if sample.response_text:
                                            coaching_texts.append(
                                                f"Suggested: {sample.response_text}"
                                            )
                                    text = "\n".join(coaching_texts)
                                if text:
                                    suggestions.append(
                                        {
                                            "type": "generator",
                                            "reply": text,
                                            "confidence": 1.0,
                                        }
                                    )

                if suggestions:
                    print(
                        f"[Debug Service] Yielding suggestions to caller: {suggestions}"
                    )
                    yield {"type": "suggestions", "suggestions": suggestions}
            print("[Debug Service] Finished iterating responses")
        except Exception as e:
            print(
                f"[Debug Service] Exception in streaming_analyze_content: {e}"
            )
            raise e

    def complete_conversation(self, conversation_name: str) -> None:
        """
        Completes the Dialogflow conversation.
        """
        try:
            location = "global"
            match = re.search(
                r"projects/[^/]+/locations/([^/]+)/", conversation_name
            )
            if match:
                location = match.group(1)
                client_options = {
                    "api_endpoint": f"{location}-dialogflow.googleapis.com:443"
                }
                conv_client = dialogflow.ConversationsClient(
                    client_options=client_options
                )
            else:
                conv_client = self.conv_client

            request = dialogflow.CompleteConversationRequest(
                name=conversation_name
            )
            conv_client.complete_conversation(request=request)
            print(
                f"[AgentAssistService] Successfully completed conversation {conversation_name}."
            )
        except Exception as e:
            print(f"[AgentAssistService] complete_conversation failed: {e}")
