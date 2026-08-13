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
"""Module containing GECX chat logic."""

import asyncio
import os
import queue

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from src.backend.services.agent_assist import AgentAssistService

router = APIRouter()
agent_assist_service = AgentAssistService()

# In-memory mapping of ticket_id to GCP Dialogflow Conversation metadata
ACTIVE_CONVERSATIONS: dict[str, dict] = {}


class ChatRoom:
    def __init__(self):
        self.customer_ws: WebSocket = None
        self.agent_ws: WebSocket = None
        self.history: list[dict] = []
        self.gecx_conversation_id: str = None


CHAT_ROOMS: dict[str, ChatRoom] = {}


@router.websocket("/ws/loopback/chat/{ticket_id}")
async def loopback_chat_websocket(
    websocket: WebSocket, ticket_id: str, role: str = Query(...)
):
    await websocket.accept()

    # Initialize chat room for this ticket
    if ticket_id not in CHAT_ROOMS:
        CHAT_ROOMS[ticket_id] = ChatRoom()

    room = CHAT_ROOMS[ticket_id]

    if role == "customer":
        room.customer_ws = websocket
        print(f"[WebSocket Chat] Customer connected for ticket {ticket_id}")
    elif role == "agent":
        room.agent_ws = websocket
        print(f"[WebSocket Chat] Agent connected for ticket {ticket_id}")
        # If history already exists, push it immediately to the newly connected agent
        if room.history:
            await websocket.send_json(
                {"type": "history", "messages": room.history}
            )

    try:
        while True:
            # Expect JSON messages for structural communication (history, text chat)
            data = await websocket.receive_json()
            print(
                f"[WebSocket Chat] Received from {role} ({ticket_id}): {data}"
            )

            if data.get("type") == "sync_gecx_id":
                gecx_id = data.get("gecx_conversation_id")
                room.gecx_conversation_id = gecx_id
                print(
                    f"[WebSocket Chat] Synced GECX Conversation ID for {ticket_id}: {gecx_id}"
                )

            elif data.get("type") == "history":
                room.history = data.get("messages", [])
                # Relay history to agent if connected
                if room.agent_ws:
                    await room.agent_ws.send_json(
                        {"type": "history", "messages": room.history}
                    )

            elif data.get("type") == "chat":
                # Append to history for late-joining agent retrieval
                room.history.append(
                    {
                        "sender": data.get("sender", role),
                        "text": data.get("text"),
                    }
                )
                # Relay chat message to the other participant
                target_ws = (
                    room.agent_ws if role == "customer" else room.customer_ws
                )
                if target_ws:
                    await target_ws.send_json(
                        {
                            "type": "chat",
                            "sender": data.get("sender", role),
                            "text": data.get("text"),
                        }
                    )

    except WebSocketDisconnect:
        print(f"[WebSocket Chat] {role} disconnected for ticket {ticket_id}")
        if role == "customer":
            room.customer_ws = None
        elif role == "agent":
            room.agent_ws = None


# In-memory mapping of ticket_id -> { "agent": WebSocket, "customer": WebSocket }
AGENT_ASSIST_PEERS: dict[str, dict[str, WebSocket]] = {}


@router.websocket("/ws/loopback/agent-assist/{ticket_id}")
async def loopback_agent_assist_websocket(
    websocket: WebSocket, ticket_id: str, role: str = Query("agent")
):
    await websocket.accept()
    print(
        f"[WebSocket AgentAssist] {role} voice stream connected for ticket {ticket_id}"
    )

    if ticket_id not in AGENT_ASSIST_PEERS:
        AGENT_ASSIST_PEERS[ticket_id] = {}
    AGENT_ASSIST_PEERS[ticket_id][role] = websocket

    if ticket_id not in ACTIVE_CONVERSATIONS:
        profile_id = os.environ.get("CONVERSATION_PROFILE_ID")
        if not profile_id:
            print(
                "[WebSocket AgentAssist] Error: CONVERSATION_PROFILE_ID is not set."
            )
            await websocket.send_json(
                {
                    "type": "error",
                    "message": "Configuration error: CONVERSATION_PROFILE_ID environment variable is missing.",
                }
            )
            await websocket.close()
            return
        try:
            metadata = agent_assist_service.create_conversation(profile_id)
            ACTIVE_CONVERSATIONS[ticket_id] = metadata
            c_name = metadata["conversation_name"]
            print(
                f"[WebSocket AgentAssist] Created Dialogflow Conversation: {c_name}"
            )
        except Exception as e:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": f"Failed to initialize Agent Assist: {str(e)}",
                }
            )
            await websocket.close()
            return

    metadata = ACTIVE_CONVERSATIONS[ticket_id]
    conv_name = metadata["conversation_name"]
    end_user = metadata["end_user"]
    automated_agent = metadata["automated_agent"]
    human_agent = metadata["human_agent"]

    # 2. Backfill pre-escalation chatbot transcript if available (only need to do it once when agent connects)
    if role == "agent":
        room = CHAT_ROOMS.get(ticket_id)
        if room and room.history:
            try:
                agent_assist_service.batch_create_messages(
                    conv_name, room.history, end_user, automated_agent
                )
            except Exception as e:
                print(f"[WebSocket AgentAssist] Backfill history failed: {e}")

    # Set up thread-safe variables to manage gRPC stream recreation cycles

    active_worker_task = None
    current_audio_queue = None

    def start_dialogflow_worker(q_queue):
        async def dialogflow_sender_worker():
            try:
                loop = asyncio.get_event_loop()
                print(
                    f"[Debug AA] Starting dialogflow_sender_worker for role: {role}"
                )

                # Synchronous audio generator consumed by the gRPC client thread
                def audio_chunk_generator():
                    print("[Debug AA] Starting audio_chunk_generator loop")
                    while True:
                        try:
                            chunk = q_queue.get(timeout=1.0)
                            if chunk is None:  # Sentinel to close generator
                                print(
                                    "[Debug AA] audio_chunk_generator received sentinel None"
                                )
                                break
                            yield chunk
                        except queue.Empty:
                            continue
                    print("[Debug AA] Exited audio_chunk_generator loop")

                # Run the synchronous gRPC iterator in the thread executor
                def run_stream():
                    print(
                        f"[Debug AA] Inside run_stream thread executor for role: {role}"
                    )
                    participant_path = (
                        human_agent if role == "agent" else end_user
                    )
                    try:
                        stream = agent_assist_service.streaming_analyze_content(
                            participant_path, audio_chunk_generator()
                        )
                        print(
                            "[Debug AA] Obtained stream from agent_assist_service"
                        )
                        for payload in stream:
                            if payload.get("type") == "transcription":
                                payload["role"] = role
                            print(
                                f"[Debug AA] Yielding payload to agent console: {payload}"
                            )

                            # Always relay transcription/suggestions to the agent's workstation console websocket
                            agent_ws = AGENT_ASSIST_PEERS.get(
                                ticket_id, {}
                            ).get("agent")
                            if agent_ws:
                                asyncio.run_coroutine_threadsafe(
                                    agent_ws.send_json(payload), loop
                                )

                            # Put None in queue when ASR gets final result (triggers turn end)
                            if (
                                payload.get("type") == "transcription"
                                and payload.get("is_final") is True
                            ):
                                print(
                                    "[Debug AA] Final transcription caught. Putting None into current queue to end turn."
                                )
                                q_queue.put(None)
                    except Exception as stream_ex:
                        if "Conversation has completed" in str(stream_ex):
                            print(
                                f"[Debug AA] Dialogflow Conversation completely finished for {role}. Closing live streaming loop gracefully."
                            )
                        elif "Quota exceeded" in str(stream_ex) or "429" in str(
                            stream_ex
                        ):
                            print(
                                f"[Debug AA] Dialogflow API Quota Exceeded (429) caught for {role}. Broadcasting alert to frontends."
                            )
                            agent_ws = AGENT_ASSIST_PEERS.get(
                                ticket_id, {}
                            ).get("agent")
                            if agent_ws:
                                asyncio.run_coroutine_threadsafe(
                                    agent_ws.send_json(
                                        {
                                            "type": "error",
                                            "message": "Dialogflow AI Quota Exceeded (429). Real-time AI coaching and transcription paused.",
                                        }
                                    ),
                                    loop,
                                )
                            customer_ws = AGENT_ASSIST_PEERS.get(
                                ticket_id, {}
                            ).get("customer")
                            if customer_ws:
                                asyncio.run_coroutine_threadsafe(
                                    customer_ws.send_json(
                                        {
                                            "type": "error",
                                            "message": "Dialogflow AI Quota Exceeded (429). Live audio transcription paused.",
                                        }
                                    ),
                                    loop,
                                )
                        else:
                            print(
                                f"[Debug AA] Exception in run_stream: {stream_ex}"
                            )
                            raise stream_ex
                    print("[Debug AA] Finished run_stream loop")

                await loop.run_in_executor(None, run_stream)
                print(
                    "[Debug AA] dialogflow_sender_worker run_in_executor completed"
                )
            except Exception as e:
                print(
                    f"[WebSocket AgentAssist] Dialogflow streaming worker error: {e}"
                )

        nonlocal active_worker_task
        active_worker_task = asyncio.create_task(dialogflow_sender_worker())

    recv_count = 0
    try:
        while True:
            # Receive raw binary PCM audio data from the browser microphone
            data = await websocket.receive_bytes()
            recv_count += 1
            if recv_count % 50 == 0:
                print(
                    f"[Debug AA] Received {recv_count} audio packets from websocket ({role}). Data size: {len(data)}"
                )

            # Start new gRPC streaming session if worker task is not running
            if active_worker_task is None or active_worker_task.done():
                print(
                    f"[Debug AA] Starting a new Dialogflow streaming session for role: {role}"
                )
                current_audio_queue = queue.Queue()
                start_dialogflow_worker(current_audio_queue)

            # Push chunk to the current thread-safe queue
            current_audio_queue.put(data)
    except WebSocketDisconnect:
        print(
            f"[WebSocket AgentAssist] {role} voice stream disconnected for ticket {ticket_id}"
        )
    finally:
        print(
            f"[Debug AA] Entering finally block of agent assist websocket ({role}). Total received: {recv_count}"
        )
        # Send sentinel to close the audio generator and wait for worker task to terminate
        if current_audio_queue:
            current_audio_queue.put(None)

        # Clean up this connection
        if (
            ticket_id in AGENT_ASSIST_PEERS
            and role in AGENT_ASSIST_PEERS[ticket_id]
        ):
            del AGENT_ASSIST_PEERS[ticket_id][role]
        if (
            ticket_id in AGENT_ASSIST_PEERS
            and not AGENT_ASSIST_PEERS[ticket_id]
        ):
            del AGENT_ASSIST_PEERS[ticket_id]

        if active_worker_task:
            try:
                await active_worker_task
                print(
                    "[Debug AA] active_worker_task awaited successfully in finally"
                )
            except asyncio.CancelledError:
                print("[Debug AA] worker_task was cancelled")
            except Exception as final_ex:
                print(
                    f"[Debug AA] Exception when awaiting worker_task: {final_ex}"
                )

        # Explicitly complete the Dialogflow conversation and purge in-memory cache when agent hangs up
        if role == "agent":
            # 1. Complete the voice Agent Assist conversation
            try:
                print(
                    f"[WebSocket AgentAssist] Agent disconnected. Completing voice conversation: {conv_name}"
                )
                agent_assist_service.complete_conversation(conv_name)
            except Exception as ce_ex:
                print(
                    f"[WebSocket AgentAssist] Failed to complete voice conversation: {ce_ex}"
                )

            # 2. Complete the GECX chat conversation if it was synced
            room = CHAT_ROOMS.get(ticket_id)
            if room and room.gecx_conversation_id:
                project_id = os.environ.get("GCP_PROJECT_ID")
                if project_id:
                    gecx_conv_name = f"projects/{project_id}/locations/global/conversations/{room.gecx_conversation_id}"
                    try:
                        print(
                            f"[WebSocket AgentAssist] Completing associated GECX Chat conversation: {gecx_conv_name}"
                        )
                        agent_assist_service.complete_conversation(
                            gecx_conv_name
                        )
                    except Exception as gecx_ex:
                        print(
                            f"[WebSocket AgentAssist] Failed to complete associated GECX conversation: {gecx_ex}"
                        )
                else:
                    print(
                        "[WebSocket AgentAssist] Warning: GCP_PROJECT_ID environment variable is missing. Cannot complete associated GECX conversation."
                    )

            ACTIVE_CONVERSATIONS.pop(ticket_id, None)
            CHAT_ROOMS.pop(ticket_id, None)
            print(
                f"[WebSocket AgentAssist] In-memory session cache entirely purged for ticket {ticket_id}"
            )
