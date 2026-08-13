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


# pylint: disable=line-too-long
"""Module containing GECX signaling logic."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class SignalingManager:
    """Manager for WebRTC signaling WebSockets."""

    def __init__(self):
        # Maps ticket_id -> { "customer": WebSocket, "agent": WebSocket }
        self.active_calls: dict[str, dict[str, WebSocket]] = {}
        # Store cached SDP offers for late-joining agents
        self.cached_offers: dict[str, dict] = {}

    async def connect(self, ticket_id: str, role: str, websocket: WebSocket):
        await websocket.accept()
        if ticket_id not in self.active_calls:
            self.active_calls[ticket_id] = {}

        # Store connection
        self.active_calls[ticket_id][role] = websocket

        # If agent connects and there is a cached offer, relay it immediately
        if role == "agent" and ticket_id in self.cached_offers:
            await websocket.send_json(self.cached_offers[ticket_id])

    def disconnect(self, ticket_id: str, role: str):
        if ticket_id in self.active_calls:
            if role in self.active_calls[ticket_id]:
                del self.active_calls[ticket_id][role]
            # Clean up empty tickets
            if not self.active_calls[ticket_id]:
                del self.active_calls[ticket_id]
                if ticket_id in self.cached_offers:
                    del self.cached_offers[ticket_id]

    async def send_to_peer(
        self, ticket_id: str, sender_role: str, message: dict
    ):
        # Cache customer offer if peer is not connected yet
        if message.get("type") == "offer" and sender_role == "customer":
            self.cached_offers[ticket_id] = message

        # Clear cached offer if call is disconnected
        if message.get("type") == "disconnect":
            if ticket_id in self.cached_offers:
                del self.cached_offers[ticket_id]

        if ticket_id in self.active_calls:
            peer_role = "agent" if sender_role == "customer" else "customer"
            peer_ws = self.active_calls[ticket_id].get(peer_role)
            if peer_ws:
                await peer_ws.send_json(message)


manager = SignalingManager()


@router.websocket("/ws/loopback/signaling/{ticket_id}")
async def websocket_signaling(
    websocket: WebSocket, ticket_id: str, role: str = "customer"
):
    await manager.connect(ticket_id, role, websocket)
    try:
        while True:
            # Receive json signal (SDP Offer/Answer or ICE Candidate)
            data = await websocket.receive_json()
            # Relay message directly to the peer
            await manager.send_to_peer(ticket_id, role, data)
    except WebSocketDisconnect:
        manager.disconnect(ticket_id, role)
