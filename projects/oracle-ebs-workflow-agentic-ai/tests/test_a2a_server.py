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

"""Unit and integration tests for A2A Gateway server and catalog."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from src.a2a.a2a_server import app as a2a_app
from src.a2a.agent_card import AgentCard
from src.a2a.formatter import render_evaluations_table
from src.a2a.proxy import (
    _extract_conversation_turns,
    _resolve_recommendation_reference,
    get_forward_headers,
    is_guardrail_fallback_required,
    sanitize_user_input,
)
from src.a2a.schemas import ActionPlan
from src.a2a.session_store import extract_session_id, get_session_store


def test_a2a_health(a2a_client: TestClient) -> None:
    """Test A2A Gateway health check."""
    res = a2a_client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


def test_agent_card_endpoints(a2a_client: TestClient) -> None:
    """Test all compliant A2A agent card route aliases."""
    for path in (
        "/agent.json",
        "/.well-known/agent.json",
        "/agent-card.json",
        "/.well-known/agent-card.json",
        "/a2a/agent.json",
        "/a2a/card",
    ):
        res = a2a_client.get(path)
        assert res.status_code == 200
        card = res.json()
        assert card["protocolVersion"] == "0.3.0"
        assert "Workflow" in card["name"]
        assert len(card["skills"]) >= 3
        assert "authentication" not in card
        AgentCard.model_validate(card)


def test_discover_agents(a2a_client: TestClient) -> None:
    """Test dynamic worker service discovery catalog."""
    res = a2a_client.get("/agents/discover")
    assert res.status_code == 200
    data = res.json()
    assert "registered_services" in data
    assert any(
        s["name"] == "workflow_agent" for s in data["registered_services"]
    )


def test_agent_registry_crud(a2a_client: TestClient) -> None:
    """Test dynamic agent registration, lookup, and deregistration."""
    test_card = AgentCard(
        name="test_worker_agent",
        description="A test agent",
        url="http://127.0.0.1:8999",
    )
    # Register
    post_res = a2a_client.post(
        "/register", json=test_card.model_dump(by_alias=True)
    )
    assert post_res.status_code == 201

    # Get
    get_res = a2a_client.get("/agents/test_worker_agent")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "test_worker_agent"

    # List
    list_res = a2a_client.get("/agents")
    assert list_res.status_code == 200
    assert any(a["name"] == "test_worker_agent" for a in list_res.json())

    # Delete
    del_res = a2a_client.delete("/agents/test_worker_agent")
    assert del_res.status_code == 204

    # 404 after delete
    get_404 = a2a_client.get("/agents/test_worker_agent")
    assert get_404.status_code == 404


def test_custom_openapi_generation() -> None:
    """Verify custom OpenAPI 3.0 schema generation."""
    schema = a2a_app.openapi()
    assert schema["openapi"] == "3.0.0"
    assert "servers" in schema
    assert "/notifications" in schema["paths"]
    assert "/notifications/{notification_id}" in schema["paths"]
    assert "/verify-policy" in schema["paths"]
    assert "/triage" in schema["paths"]
    assert "/execute" in schema["paths"]


def test_proxy_inspect_invalid_id(a2a_client: TestClient) -> None:
    """Verify explicit HTTP 422 when notification ID is <= 0 on proxy."""
    res = a2a_client.get("/notifications/-5")
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_get_forward_headers_local() -> None:
    """Verify OIDC headers are omitted for local URLs."""
    headers = await get_forward_headers("http://localhost:8001")
    assert "Authorization" not in headers
    assert headers["Content-Type"] == "application/json"


def test_greeting_instant_response_chat(a2a_client: TestClient) -> None:
    """Verify greeting 'Hi' in /chat returns executive welcome message."""
    res = a2a_client.post("/chat", json={"message": "Hi"})
    assert res.status_code == 200
    data = res.json()
    assert "reply" in data
    assert "Oracle EBS Workflow" in data["reply"]
    assert "Inspection" in data["reply"]
    assert data["jsonrpc"] == "2.0"
    assert data["result"]["status"]["state"] == "completed"


def test_greeting_instant_response_root_post(a2a_client: TestClient) -> None:
    """Verify greeting on root POST / returns A2A JSON-RPC 2.0 response."""
    payload = {
        "jsonrpc": "2.0",
        "id": 42,
        "method": "tasks/send",
        "params": {"message": {"role": "user", "parts": [{"text": "Hello"}]}},
    }
    res = a2a_client.post("/", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == 42
    assert data["jsonrpc"] == "2.0"
    assert "result" in data
    assert "Oracle EBS Workflow" in data["result"]["text"]
    assert data["result"]["parts"][0]["text"] == data["result"]["text"]


def test_greeting_root_get(a2a_client: TestClient) -> None:
    """Verify GET / returns compliant greeting."""
    res = a2a_client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert "Oracle EBS Workflow" in data["text"]


def test_extract_conversation_turns_helper() -> None:
    """Verify helper parses multi-turn dialogue structures."""

    payload = {
        "messages": [
            {"role": "user", "parts": [{"text": "Approve expense 6423623"}]},
            {
                "role": "agent",
                "parts": [
                    {
                        "text": (
                            "⚠️ Human Confirmation Gate Required for "
                            "notification 6423623"
                        )
                    }
                ],
            },
            {"role": "user", "parts": [{"text": "confirm"}]},
        ]
    }
    turns = _extract_conversation_turns(payload)
    assert len(turns) == 3
    assert turns[0] == "User: Approve expense 6423623"
    assert "Gate Required" in turns[1]
    assert turns[2] == "User: confirm"


def test_extract_conversation_turns_empty() -> None:
    """Verify helper returns empty list on empty payload."""
    assert not _extract_conversation_turns({})
    assert not _extract_conversation_turns(None)
    assert not _extract_conversation_turns({"messages": "not-a-list"})


@pytest.mark.asyncio
async def test_multi_turn_confirm_flow(a2a_client: TestClient) -> None:
    """Verify multi-turn confirmation gate preserves target notification IDs."""

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "SUCCESS",
        "action": "APPROVE",
        "results": [
            {
                "notification_id": 6423623,
                "action": "APPROVE",
                "status": "SUCCESS",
                "execution_path": "REST",
                "message": "Response recorded",
            }
        ],
    }

    with (
        patch("src.a2a.proxy.get_ai_client") as mock_ai_client,
        patch("src.a2a.proxy.generate_content_with_models") as mock_generate,
        patch("src.a2a.proxy.forward_request", return_value=mock_resp),
    ):
        mock_ai_client.return_value = MagicMock()
        mock_generate.return_value = MagicMock(
            text=(
                '{"action": "approve", "notification_ids": [6423623], '
                '"confirmed": true, "comments": "Approved via AI"}'
            )
        )

        payload = {
            "messages": [
                {
                    "role": "user",
                    "parts": [{"text": "Approve expense 6423623"}],
                },
                {
                    "role": "agent",
                    "parts": [
                        {
                            "text": (
                                "⚠️ Human Confirmation Gate Required for "
                                "notification 6423623. Impact: $15,200.00. "
                                "Reply CONFIRM to execute."
                            )
                        }
                    ],
                },
                {"role": "user", "parts": [{"text": "confirm"}]},
            ],
            "message": {"parts": [{"text": "confirm"}]},
        }

        res = a2a_client.post("/", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "result" in data
        assert "6423623" in data["result"]["text"]

        call_args = mock_generate.call_args[0]
        prompt_sent = call_args[1]
        assert "Conversation History:" in prompt_sent
        assert "Approve expense 6423623" in prompt_sent
        assert "Latest User Query: confirm" in prompt_sent


def test_session_store_staged_proposal_confirmation(
    a2a_client: TestClient,
) -> None:
    """Verify staged proposal confirmation without IDs in user prompt."""
    store = get_session_store()
    session = store.get_or_create("test_session_conf")
    session.set_pending_proposal(
        {
            "action": "APPROVE",
            "notification_ids": [7857291],
            "comments": "Confirmed by manager",
        }
    )

    with patch(
        "src.a2a.proxy.forward_request", new_callable=AsyncMock
    ) as mock_forward:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "status": "COMPLETED",
            "action": "APPROVE",
            "processed_items": [
                {
                    "notification_id": 7857291,
                    "status": "SUCCESS",
                    "execution_path": "PLSQL",
                    "message": "Approved",
                }
            ],
            "failed_items": [],
        }
        mock_forward.return_value = mock_resp

        payload = {
            "session_id": "test_session_conf",
            "message": "Confirm",
        }
        res = a2a_client.post("/", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "7857291" in data["result"]["text"]
        assert "SUCCESS" in data["result"]["text"]

        # Ensure pending proposal was cleared after execution
        assert session.pending_proposal is None


def test_session_store_bulk_approval_from_triage(
    a2a_client: TestClient,
) -> None:
    """Verify confirmed=True executes bulk approval on triaged items."""
    store = get_session_store()
    session = store.get_or_create("test_session_triage")
    triage_ids = [6434723, 6434424, 6429883]
    session.set_triage_items(triage_ids, low_risk_ids=triage_ids)

    with patch(
        "src.a2a.proxy.forward_request", new_callable=AsyncMock
    ) as mock_forward:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "status": "COMPLETED",
            "action": "APPROVE",
            "processed_items": [
                {"notification_id": nid, "status": "SUCCESS"}
                for nid in triage_ids
            ],
            "failed_items": [],
        }
        mock_forward.return_value = mock_resp

        payload = {
            "session_id": "test_session_triage",
            "message": "confirmed=True",
        }
        res = a2a_client.post("/", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "6434723" in data["result"]["text"]
        assert "6434424" in data["result"]["text"]
        assert "6429883" in data["result"]["text"]
        assert "SUCCESS" in data["result"]["text"]


def test_gibberish_input_falls_back_to_help_menu(
    a2a_client: TestClient,
) -> None:
    """Verify gibberish input returns Help Menu instead of empty worklist."""
    gibberish = (
        "klsjhdfodhsb sjdfhsgaodhlas dsaldjogasdhubjs "
        "dsjdhsaodhs dsadskjdgahsjd"
    )
    res = a2a_client.post("/", json={"message": gibberish})
    assert res.status_code == 200
    data = res.json()
    assert "Oracle EBS Workflow" in data["result"]["text"]
    assert "Workflow Worklist Inspection" in data["result"]["text"]
    assert "No pending notifications found" not in data["result"]["text"]


def test_sql_statements_and_injection_fall_back_to_help_menu(
    a2a_client: TestClient,
) -> None:
    """Verify SELECT, DELETE, DROP, and SQLi inputs return Help Menu."""
    unsafe_prompts = [
        "SELECT * FROM wf_notifications",
        "DELETE FROM wf_notifications WHERE notification_id = 1001",
        "DROP TABLE wf_notifications;",
        "Show notifications for ' OR '1'='1",
        "What is the weather in Tokyo today?",
    ]
    for prompt in unsafe_prompts:
        assert is_guardrail_fallback_required(prompt) is True
        res = a2a_client.post("/chat", json={"message": prompt})
        assert res.status_code == 200
        data = res.json()
        assert "Oracle EBS Workflow" in data["reply"]
        assert "No pending notifications found" not in data["reply"]


def test_input_sanitization_and_action_plan_validators() -> None:
    """Verify input sanitization and ActionPlan field guardrails."""
    dirty = "  <script>alert(1)</script>Show\x00   pending   notifications  "
    assert sanitize_user_input(dirty) == "alert(1)Show pending notifications"

    plan_invalid = ActionPlan(
        action="DROP_TABLE",
        recipient="JSMITH' OR '1'='1",
        comments="<b>Approved</b>\x00",
    )
    assert plan_invalid.action == "help"
    assert plan_invalid.recipient is None
    assert plan_invalid.comments == "Approved"

    plan_gibberish = ActionPlan(
        action="notifications",
        recipient="klsjhdfodhsb",
    )
    assert plan_gibberish.recipient is None


def test_multi_item_expense_report_recommendation_followup(
    a2a_client: TestClient,
) -> None:
    """Verify asking for 3 pending Expense Reports returns all 3 items."""
    session_store = get_session_store()
    session_store.clear("test_session_apexp3")
    session = session_store.get_or_create("test_session_apexp3")
    session.set_triage_items(
        notification_ids=[10294, 10295, 10296],
        low_risk_ids=[10294, 10295, 10296],
        items_by_type={"APEXP": [10294, 10295, 10296]},
    )

    with (
        patch("src.a2a.proxy.get_ai_client") as mock_get_ai,
        patch("src.a2a.proxy.generate_content_with_models") as mock_gen,
        patch(
            "src.a2a.proxy.forward_request", new_callable=AsyncMock
        ) as mock_forward,
    ):
        mock_get_ai.return_value = MagicMock()
        mock_llm_resp = MagicMock()
        mock_llm_resp.text = '{"action": "inspect", "notification_id": 10294}'
        mock_gen.return_value = mock_llm_resp

        def fake_forward(
            method: str,
            target_service_url: str,
            path: str,
            **_kwargs: Any,
        ) -> MagicMock:
            del method, target_service_url
            nid = int(path.rstrip("/").split("/")[-1])
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "header": {
                    "notification_id": nid,
                    "message_type": "APEXP",
                    "recipient_role": "JSMITH",
                    "status": "OPEN",
                    "subject": f"Expense Report for {nid}",
                    "amount": 95.0,
                },
                "attributes": {
                    "APPROVER_DISPLAY_NAME": "Approver, Manager",
                    "EXPENSE_DETAILS": "JSP:/OA_HTML/OA.jsp?test=1",
                },
            }
            return resp

        mock_forward.side_effect = fake_forward

        res = a2a_client.post(
            "/",
            json={
                "session_id": "test_session_apexp3",
                "message": (
                    "Verify receipt attachments for 3 pending Expense Report(s)"
                ),
            },
        )
        assert res.status_code == 200
        text_out = res.json()["result"]["text"]
        assert "10294" in text_out
        assert "10295" in text_out
        assert "10296" in text_out
        assert "OA.jsp" not in text_out


def test_render_evaluations_table_with_dict_violations() -> None:
    """Verify render_evaluations_table handles PolicyViolation dicts cleanly."""
    evals = [
        {
            "notification_id": 1001,
            "message_type": "APEXP",
            "compliance_status": "FLAGGED_FOR_REVIEW",
            "risk_level": "HIGH",
            "recommendation": "ESCALATE",
            "violations": [
                {
                    "code": "EXP_MISSING_RECEIPT",
                    "message": "Missing required receipt attachment.",
                    "severity": "HIGH",
                }
            ],
        }
    ]
    md = render_evaluations_table(evals)
    assert "EXP_MISSING_RECEIPT: Missing required receipt attachment." in md
    assert "⚠️ HIGH" in md


def test_extract_session_id_nested_a2a_params() -> None:
    """Verify extract_session_id reads nested params and message contextId."""
    body = {
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "contextId": "ctx-nested-999",
                "parts": [{"text": "Triage my queue"}],
            }
        },
    }
    assert extract_session_id(body) == "ctx-nested-999"


def test_single_approve_after_triage_does_not_approve_all(
    a2a_client: TestClient,
) -> None:
    """Verify approving a specific ID after triage only targets that ID."""
    session_store = get_session_store()
    session_store.clear("test_session_single_after_triage")
    session = session_store.get_or_create("test_session_single_after_triage")
    session.set_triage_items(
        notification_ids=[10294, 10295, 10296],
        low_risk_ids=[10294, 10295, 10296],
    )

    with (
        patch("src.a2a.proxy.get_ai_client") as mock_get_ai,
        patch("src.a2a.proxy.generate_content_with_models") as mock_gen,
        patch(
            "src.a2a.proxy.forward_request", new_callable=AsyncMock
        ) as mock_forward,
    ):
        mock_get_ai.return_value = MagicMock()
        mock_llm_resp = MagicMock()
        mock_llm_resp.text = (
            '{"action": "approve", "notification_id": 10294, '
            '"confirmed": false}'
        )
        mock_gen.return_value = mock_llm_resp

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "status": "CONFIRMATION_REQUIRED",
            "action": "APPROVE",
            "requires_confirmation": True,
            "proposal": {
                "action": "APPROVE",
                "notification_ids": [10294],
                "total_financial_impact": 95.0,
                "risk_summary": "1 notification",
                "confirmation_prompt": "Please confirm 10294",
            },
        }
        mock_forward.return_value = mock_resp

        res = a2a_client.post(
            "/",
            json={
                "session_id": "test_session_single_after_triage",
                "message": "Approve notification 10294",
            },
        )
        assert res.status_code == 200
        sent_body = mock_forward.call_args.kwargs["json_body"]
        assert sent_body["notification_ids"] == [10294]


def test_resolve_recommendation_reference() -> None:
    """Verify ordinal recommendation prompts resolve to stored next steps."""
    recs = [
        "Verify receipt attachments for 2 pending Expense Report(s)",
        "Confirm approved supplier for 1 Purchase Order(s)",
    ]
    resolved = _resolve_recommendation_reference(
        "can you help me with the first recommendation?", recs
    )
    assert (
        "Verify receipt attachments for 2 pending Expense Report(s)" in resolved
    )
    assert not is_guardrail_fallback_required(
        "can you help me with the first recommendation?"
    )


def test_session_prunes_completed_and_closed_notifications() -> None:
    """Verify closed notifications are removed from session memory."""
    store = get_session_store()
    session = store.get_or_create("test_session_prune_closed")
    session.set_triage_items(
        [7900386, 7905317],
        low_risk_ids=[7900386, 7905317],
        items_by_type={"POAPPR": [7900386], "APEXP": [7905317]},
    )
    session.remove_completed_notifications([7900386])
    assert session.last_notification_ids == [7905317]
    assert session.last_low_risk_ids == [7905317]
    assert session.last_items_by_type["POAPPR"] == []
    assert session.last_items_by_type["APEXP"] == [7905317]


def test_validation_error_sanitized_in_exception_handler(
    a2a_client: TestClient,
) -> None:
    """Verify ValidationError logs internally and returns sanitized message."""
    with patch(
        "src.a2a.proxy.sanitize_user_input",
        side_effect=ActionPlan.model_validate,
    ) as mock_extract:
        mock_extract.side_effect = lambda *_args, **_kwargs: (
            ActionPlan.model_validate("invalid-non-dict-payload")
        )
        res = a2a_client.post("/chat", json={"message": "Triage worklist"})
        assert res.status_code == 200
        data = res.json()
        assert "Invalid request payload or parameters." in data["reply"]
        assert "12345" not in data["reply"]


def test_proxy_endpoints_sanitize_upstream_errors(
    a2a_client: TestClient,
) -> None:
    """Verify upstream raw error bodies are logged and not leaked to clients."""
    mock_resp = MagicMock()
    mock_resp.status_code = 502
    mock_resp.text = "ORA-12541: TNS:no listener at internal-db.corp:1521"
    with patch(
        "src.a2a.proxy.forward_request",
        new_callable=AsyncMock,
        return_value=mock_resp,
    ):
        res = a2a_client.get("/notifications?limit=10")
        assert res.status_code == 502
        body = res.json()
        assert body["detail"] == "Upstream workflow service request failed."
        assert "ORA-12541" not in body["detail"]


def test_session_store_strict_isolation_between_sessions() -> None:
    """Verify sessions are strictly isolated by session_id without leakage."""
    store = get_session_store()
    store.clear("default_session")
    store.clear("user_a_session")
    store.clear("user_b_session")

    default_sess = store.get_or_create("default_session")
    default_sess.set_pending_proposal(
        {"action": "APPROVE", "notification_ids": [1001]}
    )
    default_sess.set_triage_items([1001, 1002], low_risk_ids=[1001])
    default_sess.add_turn("user", "Approve 1001")

    user_a = store.get_or_create("user_a_session")
    user_a.set_pending_proposal(
        {"action": "REJECT", "notification_ids": [2001]}
    )
    user_a.set_triage_items([2001], low_risk_ids=[2001])
    user_a.add_turn("user", "Reject 2001")

    user_b = store.get_or_create("user_b_session")
    assert user_b.pending_proposal is None
    assert user_b.last_notification_ids == []
    assert user_b.last_low_risk_ids == []
    assert user_b.dialogue_turns == []


def test_confirmation_with_echoed_context_id_and_rotated_session(
    a2a_client: TestClient,
) -> None:
    """Verify Confirm executes staged approval across echoed or rotated IDs."""
    store = get_session_store()
    store.clear("default_session")

    mock_gate_resp = MagicMock()
    mock_gate_resp.status_code = 200
    mock_gate_resp.json.return_value = {
        "status": "CONFIRMATION_REQUIRED",
        "action": "APPROVE",
        "notification_ids": [7905316, 7905317],
        "proposal": {
            "action": "APPROVE",
            "notification_ids": [7905316, 7905317],
            "total_financial_impact": 270.0,
            "risk_summary": "Action proposed: APPROVE 2 notification(s)",
            "confirmation_prompt": "Reply CONFIRM to execute.",
        },
    }

    mock_exec_resp = MagicMock()
    mock_exec_resp.status_code = 200
    mock_exec_resp.json.return_value = {
        "status": "COMPLETED",
        "action": "APPROVE",
        "processed_items": [
            {"notification_id": 7905316, "status": "SUCCESS"},
            {"notification_id": 7905317, "status": "SUCCESS"},
        ],
        "failed_items": [],
    }

    with (
        patch("src.a2a.proxy.get_ai_client") as mock_get_ai,
        patch("src.a2a.proxy.generate_content_with_models") as mock_generate,
        patch(
            "src.a2a.proxy.forward_request", new_callable=AsyncMock
        ) as mock_forward,
    ):
        mock_get_ai.return_value = MagicMock()
        mock_llm_resp = MagicMock()
        mock_llm_resp.text = ActionPlan(
            action="approve",
            notification_ids=[7905316, 7905317],
            confirmed=False,
        ).model_dump_json()
        mock_generate.return_value = mock_llm_resp
        mock_forward.return_value = mock_gate_resp

        turn1 = a2a_client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "message/send",
                "params": {
                    "message": {
                        "role": "user",
                        "parts": [
                            {
                                "text": (
                                    "Approve notifications 7905316 and 7905317"
                                )
                            }
                        ],
                    }
                },
            },
        )
        assert turn1.status_code == 200
        returned_ctx_id = turn1.json()["result"]["contextId"]

        mock_forward.return_value = mock_exec_resp
        turn2 = a2a_client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "id": "2",
                "method": "message/send",
                "params": {
                    "contextId": "rotated-gemini-ctx-id",
                    "message": {
                        "role": "user",
                        "parts": [{"text": "Confirm"}],
                        "contextId": returned_ctx_id,
                    },
                },
            },
        )
        assert turn2.status_code == 200
        turn2_data = turn2.json()
        assert turn2_data["status"] == "COMPLETED"
        sent_body = mock_forward.call_args.kwargs["json_body"]
        assert sent_body["confirmed"] is True
        assert sent_body["notification_ids"] == [7905316, 7905317]
