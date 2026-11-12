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

"""Tests for the A2A server, its part filter, and session expiry."""

from collections.abc import Iterator

import pytest
from google.adk.artifacts import GcsArtifactService
from google.adk.platform import time as platform_time
from google.genai import types
from oracle_ebs_scm_agentic_ai import server
from oracle_ebs_scm_agentic_ai.config import Settings
from starlette.testclient import TestClient


def test_user_visible_part_hides_tool_traffic() -> None:
    hidden = [
        types.Part(text="thinking", thought=True),
        types.Part(
            function_call=types.FunctionCall(name="ebs_execute_sql", args={})
        ),
        types.Part(
            function_response=types.FunctionResponse(
                name="ebs_execute_sql", response={"rows": []}
            )
        ),
    ]
    assert all(server.user_visible_part(part) is None for part in hidden)
    assert server.user_visible_part(types.Part(text="### Miami DC")) is not None
    image = types.Part(
        inline_data=types.Blob(mime_type="image/png", data=b"\x89PNG")
    )
    assert server.user_visible_part(image) is not None


def test_agent_card_uses_public_url() -> None:
    card = server.build_agent_card("https://agent.example.run.app")
    assert card.name == "VoltGuard Supply Chain Resiliency Agent"
    assert card.supported_interfaces[0].url == "https://agent.example.run.app"
    assert "image/png" in card.default_output_modes


def test_a2a_server_answers_help_without_calling_gemini(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    services: list[GcsArtifactService] = []

    def tracked_gcs(bucket_name: str) -> GcsArtifactService:
        services.append(GcsArtifactService(bucket_name=bucket_name))
        return services[-1]

    # The emulator setting lets the real Cloud Storage client start without
    # credentials. The help reply saves no artifacts.
    monkeypatch.setenv("STORAGE_EMULATOR_HOST", "http://127.0.0.1:9")
    monkeypatch.setattr(server, "GcsArtifactService", tracked_gcs)
    app = server.create_app()
    assert [service.bucket.name for service in services] == [
        settings.artifact_bucket
    ]
    request = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "message/send",
        "params": {
            "message": {
                "kind": "message",
                "messageId": "m-1",
                "role": "user",
                "parts": [{"kind": "text", "text": "hi"}],
            }
        },
    }
    with TestClient(app) as client:
        card = client.get("/.well-known/agent-card.json")
        response = client.post("/", json=request)
    assert card.status_code == 200
    assert response.status_code == 200
    body = response.json()
    assert "error" not in body
    texts = [
        part.get("text", "")
        for artifact in body["result"].get("artifacts", [])
        for part in artifact["parts"]
    ]
    assert any(text.startswith("# ") and "VoltGuard" in text for text in texts)


@pytest.fixture(name="clock")
def fixture_clock() -> Iterator[list[float]]:
    """Drive ADK session timestamps and session expiry from one clock."""
    now = [1_000.0]
    platform_time.set_time_provider(lambda: now[0])
    yield now
    platform_time.reset_time_provider()


async def session_ids(service: server.ExpiringSessionService) -> set[str]:
    """Return the IDs of the sessions that the service still holds."""
    listed = await service.list_sessions(app_name="app")
    return {session.id for session in listed.sessions}


async def test_idle_sessions_expire(clock: list[float]) -> None:
    service = server.ExpiringSessionService(60, 10, clock=lambda: clock[0])
    await service.create_session(app_name="app", user_id="u", session_id="a")
    clock[0] += 61
    await service.create_session(app_name="app", user_id="u", session_id="b")
    assert await session_ids(service) == {"b"}


async def test_the_oldest_sessions_go_beyond_the_limit(
    clock: list[float],
) -> None:
    service = server.ExpiringSessionService(3_600, 2, clock=lambda: clock[0])
    for session_id in ("a", "b", "c"):
        clock[0] += 1
        await service.create_session(
            app_name="app", user_id=session_id, session_id=session_id
        )
    assert await session_ids(service) == {"b", "c"}
