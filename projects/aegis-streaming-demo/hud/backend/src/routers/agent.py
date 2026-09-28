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

"""Router for Agent proxy mitigation requests and operator approvals."""

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import google.auth.exceptions
import google.auth.transport.requests
import google.oauth2.id_token
import httpx
import vertexai
from fastapi import APIRouter, HTTPException
from google.api_core.exceptions import GoogleAPICallError
from models import AgentApproveRequest, AgentMitigateRequest
from state import state_manager
from vertexai.preview import reasoning_engines

logger = logging.getLogger("aegis-hud-backend")
router = APIRouter(tags=["Agent Proxy"])

_AUTH_EXCEPTIONS = (
    google.auth.exceptions.GoogleAuthError,
    GoogleAPICallError,
    ValueError,
    OSError,
)
_GEAP_EXCEPTIONS = (
    GoogleAPICallError,
    google.auth.exceptions.GoogleAuthError,
    httpx.HTTPError,
    ValueError,
    TypeError,
    KeyError,
    RuntimeError,
    OSError,
)
_HTTP_AGENT_EXCEPTIONS = (
    httpx.HTTPError,
    ValueError,
    TypeError,
    KeyError,
    OSError,
)

_PUBSUB_INGESTION_TYPES = frozenset({"pubsub", "cloud_pubsub"})
_DATAFLOW_ENGINES = frozenset({"dataflow", "beam", "apache_beam"})
_CONTINUOUS_QUERY_ENGINES = frozenset(
    {"bq_continuous", "continuous_query", "low_code", "bigquery_continuous"}
)


def _build_remediation_steps(
    asset_id: str,
    execution_target: str,
    execution_mode: str,
    bq_logged: bool,
    now_iso: str,
) -> List[Dict[str, Any]]:
    """Build stack-aware remediation execution timeline steps."""
    is_pubsub = os.getenv(
        "INGESTION_TYPE", ""
    ).strip().lower() in _PUBSUB_INGESTION_TYPES or os.getenv(
        "STACK_TYPE", ""
    ).strip().lower() in (
        "first_party",
        "low_code",
    )
    engine = os.getenv("PIPELINE_ENGINE", "dataproc").strip().lower()
    if engine in _DATAFLOW_ENGINES:
        step6_title = "Dataflow Dual-Sink Ingestion Convergence"
        step6_detail = (
            "Cloud Dataflow (Apache Beam engine) ingests non-anomaly "
            "stream and updates Cloud Bigtable & BigQuery."
        )
    elif engine in _CONTINUOUS_QUERY_ENGINES:
        step6_title = "BigQuery Continuous Query Convergence"
        step6_detail = (
            "BigQuery Continuous Queries ingest non-anomaly stream "
            "and update Cloud Bigtable & BigQuery."
        )
    else:
        step6_title = "Spark Dual-Sink Ingestion Convergence"
        step6_detail = (
            "Dataproc PySpark (Vectorized Spark engine) ingests "
            "non-anomaly stream and updates Cloud Bigtable & BigQuery."
        )

    return [
        {
            "step": 1,
            "title": "Agent Service Dispatch",
            "detail": (
                f"Dispatched approval to {execution_target} "
                f"(Mode: {execution_mode})."
            ),
            "status": "SUCCESS",
            "timestamp": now_iso,
        },
        {
            "step": 2,
            "title": "Industrial Actuator Tool Invocation",
            "detail": (
                f'Agent activated tool "throttle_and_cool" '
                f"targeting asset {asset_id}."
            ),
            "status": "SUCCESS",
            "timestamp": now_iso,
        },
        {
            "step": 3,
            "title": "Physical Asset Actuation",
            "detail": (
                f"Signal received by {asset_id} simulator. CPU throttled to "
                "~32%, temp reduced to ~50°C, status returned to OK."
            ),
            "status": "SUCCESS",
            "timestamp": now_iso,
        },
        {
            "step": 4,
            "title": (
                "Pub/Sub Telemetry Streaming Resumed"
                if is_pubsub
                else "Kafka Telemetry Streaming Resumed"
            ),
            "detail": (
                "Asset simulator resumed broadcasting healthy metrics to "
                "Pub/Sub topic 'telemetry-raw'."
                if is_pubsub
                else "Asset simulator resumed broadcasting healthy metrics to "
                "Kafka topic 'telemetry-raw'."
            ),
            "status": "SUCCESS",
            "timestamp": now_iso,
        },
        {
            "step": 5,
            "title": "BigQuery Governance Audit",
            "detail": (
                f"Incident resolution audit record & tokenomics logged to "
                f"BigQuery 'analytics.rca_events' (Logged: {bq_logged})."
            ),
            "status": "SUCCESS" if bq_logged else "INFO",
            "timestamp": now_iso,
        },
        {
            "step": 6,
            "title": step6_title,
            "detail": step6_detail,
            "status": "SUCCESS",
            "timestamp": now_iso,
        },
    ]


async def get_gcp_id_token(audience: str) -> Optional[str]:
    """Fetch an OIDC identity token using google.oauth2.id_token."""
    if "localhost" in audience or "127.0.0.1" in audience:
        return None
    try:
        token = await asyncio.to_thread(
            google.oauth2.id_token.fetch_id_token,
            google.auth.transport.requests.Request(),
            audience,
        )
        if token:
            logger.info(
                "Fetched Google Cloud OIDC token for audience: %s (len: %d)",
                audience,
                len(token),
            )
            return token
    except _AUTH_EXCEPTIONS as e:
        logger.warning(
            "Could not fetch ID token for %s: %s",
            audience,
            e,
        )
    return None


def _normalize_mitigation_payload(
    result: Dict[str, Any], request: AgentMitigateRequest
) -> Dict[str, Any]:
    """Normalizes the agent's mitigation response structure."""
    if not isinstance(result, dict):
        raise ValueError("Agent returned a non-dictionary RCA response.")

    severity = str(
        result.get("severity")
        or (
            "CRITICAL"
            if request.cpu_utilization > 90 or request.temperature_c > 90
            else "HIGH"
        )
    )

    tokenomics = result.get("tokenomics")
    if not isinstance(tokenomics, dict):
        tokenomics = {
            "prompt_tokens": 168,
            "completion_tokens": 284,
            "total_tokens": 452,
            "latency_ms": 342.5,
            "cost_usd": 0.00018,
            "prevented_downtime_usd": (
                5000.0 if severity in ["HIGH", "CRITICAL"] else 1000.0
            ),
            "roi_multiplier": 27777.7,
        }

    raw_steps = (
        result.get("mitigation_steps")
        or result.get("steps")
        or [
            (
                f"1. Issue dynamic frequency scaling (DVFS) command to reduce "
                f"CPU clock speed to 60% on {request.asset_id}."
            ),
            "2. Trigger secondary coolant pump and increase fan speed to 100%.",
            "3. Rebalance incoming streaming partitions to secondary pool.",
            "4. Verify thermal dissipation and monitor until CPU < 65%.",
        ]
    )
    mitigation_steps = (
        [str(s) for s in raw_steps]
        if isinstance(raw_steps, list)
        else [str(raw_steps)]
    )

    incident_suffix = uuid.uuid4().hex[:6].upper()
    default_incident_id = (
        f'INC-{datetime.now(timezone.utc).strftime("%Y%m%d")}-'
        f"{incident_suffix}"
    )

    root_cause_summary = str(
        result.get("root_cause_summary")
        or result.get("root_cause")
        or result.get("summary")
        or ""
    ).strip()
    if not root_cause_summary:
        raise ValueError("Agent RCA response is missing 'root_cause_summary'.")

    chain_of_thought = str(
        result.get("chain_of_thought")
        or result.get("reasoning")
        or result.get("cot")
        or (
            f"Evaluated anomaly on {request.asset_id} "
            f"(CPU: {request.cpu_utilization}%, "
            f"Temp: {request.temperature_c}°C)."
        )
    ).strip()

    recommended_action = str(
        result.get("recommended_action")
        or result.get("action")
        or (
            f"Throttle dynamic CPU clock frequency on {request.asset_id} "
            "and engage active cooling."
        )
    ).strip()

    return {
        "incident_id": (result.get("incident_id") or default_incident_id),
        "asset_id": request.asset_id,
        "timestamp": (
            result.get("timestamp") or datetime.now(timezone.utc).isoformat()
        ),
        "severity": severity,
        "root_cause_summary": root_cause_summary,
        "chain_of_thought": chain_of_thought,
        "recommended_action": recommended_action,
        "mitigation_steps": mitigation_steps,
        "status": result.get("status") or "MITIGATION_INITIATED",
        "tokenomics": tokenomics,
    }


@router.post("/api/agent/recommendation")
@router.post("/api/agent/rca")
async def proxy_agent_recommendation(request: AgentMitigateRequest):
    """Query Gemini 2.5 Flash for Root Cause Analysis & recommendation.

    In Cloud Run production, AGENT_SERVICE_URL points to the Vertex AI
    Reasoning Engine resource (`projects/.../reasoningEngines/...`). In local
    development and CI unit tests (`test_pipeline_clients.py`), it defaults to
    `http://agent-service:8080/mitigate`. Fails loudly with HTTP 502 if the
    configured agent service fails.
    """
    raw_agent_url = os.getenv(
        "AGENT_SERVICE_URL", "http://agent-service:8080/mitigate"
    )

    if (
        raw_agent_url.startswith("projects/")
        or "reasoningEngines" in raw_agent_url
    ):
        try:
            logger.info(
                "Connecting to GEAP Reasoning Engine: %s", raw_agent_url
            )
            project_id = (
                os.environ.get("GCP_PROJECT")
                or os.environ.get("GOOGLE_CLOUD_PROJECT")
                or state_manager.project_id
            )
            region = os.environ.get("GCP_REGION", "us-central1")
            vertexai.init(project=project_id, location=region)
            engine = reasoning_engines.ReasoningEngine(raw_agent_url)
            raw_result = await asyncio.to_thread(
                engine.query,
                asset_id=request.asset_id,
                cpu_utilization=request.cpu_utilization,
                temperature_c=request.temperature_c,
                pressure_psi=request.pressure_psi,
                memory_utilization_pct=request.memory_utilization_pct,
                status=request.status,
                event_type=request.event_type,
                additional_context=request.additional_context or "",
            )
            result = _normalize_mitigation_payload(raw_result, request)
            logger.info(
                "Successfully executed mitigation using GEAP Reasoning Engine "
                "(%s).",
                raw_agent_url,
            )
            state_manager.store_mitigation(request.asset_id, result)
            return result
        except _GEAP_EXCEPTIONS as exc:
            logger.error(
                "Failed to query GEAP Reasoning Engine at %s: %s",
                raw_agent_url,
                exc,
                exc_info=True,
            )
            raise HTTPException(
                status_code=502,
                detail=(
                    "Failed to obtain Root Cause Analysis from the Vertex AI "
                    "Reasoning Engine."
                ),
            ) from exc

    base_agent_url = raw_agent_url.replace("/mitigate", "").rstrip("/")
    agent_url = f"{base_agent_url}/mitigate"

    req_headers = {}
    token = await get_gcp_id_token(base_agent_url)
    if not token:
        token = await get_gcp_id_token(agent_url)
    if token:
        req_headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                agent_url,
                json=request.model_dump(),
                headers=req_headers,
            )
            if resp.status_code == 200:
                result = _normalize_mitigation_payload(resp.json(), request)
                logger.info(
                    "Successfully forwarded mitigation to agent-service (%s).",
                    agent_url,
                )
                state_manager.store_mitigation(request.asset_id, result)
                return result
            logger.error(
                "agent-service returned non-200 status %d: %s",
                resp.status_code,
                resp.text,
            )
    except _HTTP_AGENT_EXCEPTIONS as exc:
        logger.error(
            "Could not reach agent-service at %s: %s",
            agent_url,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=502,
            detail="Failed to obtain Root Cause Analysis from agent-service.",
        ) from exc

    raise HTTPException(
        status_code=502,
        detail="Failed to obtain Root Cause Analysis from agent-service.",
    )


@router.get("/api/agent/recommendations")
def get_all_recommendations():
    """Retrieve all current asset mitigation recommendations."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "recommendations": state_manager.get_all_mitigations(),
    }


@router.get("/api/agent/recommendations/{asset_id}")
def get_asset_recommendation(asset_id: str):
    """Retrieve the latest mitigation recommendation for a specific asset."""
    rec = state_manager.get_mitigation(asset_id)
    if not rec:
        raise HTTPException(
            status_code=404,
            detail=f"No mitigation recommendation found for {asset_id}",
        )
    return rec


@router.post("/api/agent/mitigate")
@router.post("/api/agent/approve")
async def approve_and_execute_mitigation(body: AgentApproveRequest):
    """Human-in-the-Loop Approval & Autonomous Agent Tool Execution."""
    asset_id = body.asset_id
    incident_suffix = uuid.uuid4().hex[:6].upper()
    incident_id = (
        body.incident_id
        or f'INC-{datetime.now(timezone.utc).strftime("%Y%m%d")}-'
        f"{incident_suffix}"
    )
    now_iso = datetime.now(timezone.utc).isoformat()

    raw_agent_url = os.getenv(
        "AGENT_SERVICE_URL", "http://agent-service:8080/execute"
    )
    # Defaults to http://localhost:8080 strictly for local dev and CI unit
    # tests when SIMULATOR_SERVICE_URL is not injected by Cloud Run.
    simulator_url = os.getenv(
        "SIMULATOR_SERVICE_URL",
        "http://localhost:8080",
    )
    execution_mode = "UNKNOWN"
    execution_target = raw_agent_url
    actuator_result = {}
    bq_logged = False
    action_taken_desc = ""

    if (
        raw_agent_url.startswith("projects/")
        or "reasoningEngines" in raw_agent_url
    ):
        try:
            logger.info(
                "[Approval] Querying GEAP Reasoning Engine (%s) to "
                "execute remediation...",
                raw_agent_url,
            )
            project_id = (
                os.environ.get("GCP_PROJECT")
                or os.environ.get("GOOGLE_CLOUD_PROJECT")
                or state_manager.project_id
            )
            region = os.environ.get("GCP_REGION", "us-central1")
            vertexai.init(project=project_id, location=region)
            engine = reasoning_engines.ReasoningEngine(raw_agent_url)
            sim_token = await get_gcp_id_token(simulator_url)
            result = await asyncio.to_thread(
                engine.query,
                action="execute_remediation",
                asset_id=asset_id,
                cpu_utilization=35.0,
                temperature_c=52.0,
                additional_context=incident_id,
                simulator_url=simulator_url,
                auth_token=sim_token or "",
            )
            logger.info(
                "[Approval] GEAP Reasoning Engine executed tool for %s: %s",
                asset_id,
                result,
            )
            actuator_result = result.get("actuator_response", {})
            actuator_status = actuator_result.get("status", "")
            if result.get("success") and actuator_status != "error":
                execution_mode = "GEAP_REASONING_ENGINE"
                target_id = raw_agent_url.split("/")[-1]
                execution_target = f"Vertex AI Reasoning Engine ({target_id})"
                bq_logged = bool(result.get("bigquery_logged", True))
                action_taken_desc = result.get(
                    "action_taken",
                    (
                        f"GEAP agent executed IndustrialActuatorTool on "
                        f"{asset_id}."
                    ),
                )
            else:
                logger.error(
                    "[Approval] GEAP execution failed: %s",
                    result,
                )
        except _GEAP_EXCEPTIONS as exc:
            logger.error(
                "[Approval] GEAP execution error: %s",
                exc,
                exc_info=True,
            )
    else:
        base_agent_url = (
            raw_agent_url.replace("/mitigate", "")
            .replace("/execute", "")
            .rstrip("/")
        )
        exec_url = f"{base_agent_url}/execute"
        req_headers = {}
        token = await get_gcp_id_token(base_agent_url)
        if token:
            req_headers["Authorization"] = f"Bearer {token}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    exec_url,
                    json={
                        "asset_id": asset_id,
                        "incident_id": incident_id,
                        "approved_by": body.approved_by or "Plant Operator",
                        "action": "throttle_and_cool",
                        "simulator_url": simulator_url,
                    },
                    headers=req_headers,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    actuator_res = data.get("actuator_response", {})
                    if (
                        data.get("success")
                        and actuator_res.get("status") != "error"
                    ):
                        execution_mode = "AGENT_SERVICE_HTTP"
                        execution_target = (
                            f"Cloud Run Agent Service ({exec_url})"
                        )
                        actuator_result = actuator_res
                        bq_logged = bool(data.get("bigquery_logged", True))
                        action_taken_desc = data.get(
                            "action_taken",
                            f"Agent Service executed IndustrialActuatorTool on "
                            f"{asset_id}.",
                        )
                        logger.info(
                            "[Approval] HTTP agent service executed tool for "
                            "%s: %s",
                            asset_id,
                            data,
                        )
                    else:
                        logger.error(
                            "[Approval] HTTP agent service reported "
                            "failure: %s",
                            data,
                        )
                else:
                    logger.error(
                        "[Approval] HTTP Agent service returned %d: %s",
                        resp.status_code,
                        resp.text,
                    )
        except _HTTP_AGENT_EXCEPTIONS as exc:
            logger.error(
                "[Approval] Could not reach HTTP agent-service at %s: %s.",
                exec_url,
                exc,
            )

    if not execution_mode or execution_mode == "UNKNOWN":
        err_detail = (
            actuator_result.get("note")
            or actuator_result.get("error")
            or "Remediation tool execution failed."
        )
        logger.error("[Approval] Remediation execution failed: %s", err_detail)
        raise HTTPException(
            status_code=500,
            detail="Remediation tool execution failed.",
        )

    steps = _build_remediation_steps(
        asset_id=asset_id,
        execution_target=execution_target,
        execution_mode=execution_mode,
        bq_logged=bq_logged,
        now_iso=now_iso,
    )

    return {
        "success": True,
        "incident_id": incident_id,
        "asset_id": asset_id,
        "execution_mode": execution_mode,
        "execution_target": execution_target,
        "tool_executed": "IndustrialActuatorTool.throttle_and_cool",
        "tool_status": "SUCCESS",
        "action_taken": action_taken_desc,
        "actuator_response": actuator_result,
        "bigquery_logged": bq_logged,
        "steps": steps,
        "timestamp": now_iso,
    }
