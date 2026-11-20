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

# pylint: disable=line-too-long,wrong-import-position

"""Provisions and verifies the Agent Sandbox in Gemini runtime (`ADR-0012` / `PR-S2`).

Creates (or reuses) a lightweight parent `ReasoningEngine` resource in Vertex AI / Gemini
Enterprise Agent Platform (`agentplatform`) so Cloud Run services (`cymbal-pooled-gateway`,
`cymbal-agent-shared`, `cymbal-agent-finvault-alpha`) can spawn per-session `sandboxEnvironments`
("The Hands") out-of-process without migrating the stateless multi-tenant orchestrator ("The Brain")
off Cloud Run.

Usage:
    # Offline dry-run verification (default, zero network calls):
    .venv/bin/python scripts/provision_gemini_agent_sandbox.py

    # Live SDK smoke test + end-to-end GeminiAgentSandboxManager & MCP verification:
    .venv/bin/python scripts/provision_gemini_agent_sandbox.py --live --verify-manager \
        --project-id <YOUR_PROJECT_ID> --location us-central1
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import agentplatform
import google.oauth2.credentials
from agentplatform import types as agentplatform_types

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents import context as agent_context
from agents import sandbox_execution
from agents.platform_config import get_platform_config, resolve_project_id
from mcp_server import server as mcp_server_tools


@dataclass(frozen=True)
class _VerifiedToolContext:
    """Minimal verified ADK `tool_context` carrier for live MCP sandbox verification."""

    state: dict[str, object]


def _tfvars_snippet(engine_resource_name: str) -> str:
    """The Terraform variable assignment that points a deployment at this reasoning engine."""
    return f'agent_sandbox_reasoning_engine_name = "{engine_resource_name}"'


def _always_live_mode() -> bool:
    """Returns `True` to force live Gemini REST calls during `--verify-manager` runs."""
    return True


def _resolve_gcloud_access_token() -> str:
    """Fetches an OAuth2 access token from the active `gcloud` CLI configuration.

    Returns:
        Non-empty bearer access token string.

    Raises:
        RuntimeError: If `gcloud auth print-access-token` fails or returns an empty token.
    """
    completed = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        check=True,
        capture_output=True,
        text=True,
        timeout=15.0,
    )
    access_token = completed.stdout.strip()
    if not access_token:
        raise RuntimeError(
            "gcloud auth print-access-token returned an empty token."
        )
    return access_token


def _build_gcloud_headers_provider() -> Callable[[str], dict[str, str]]:
    """Builds a control-plane header provider backed by `gcloud auth print-access-token`."""

    def _headers_for_project(target_project_id: str) -> dict[str, str]:
        token_value = _resolve_gcloud_access_token()
        return {
            "Authorization": f"Bearer {token_value}",
            "X-Goog-User-Project": target_project_id,
        }

    return _headers_for_project


def _mint_verified_envelope(
    *,
    tenant_id: str,
    user_sub: str,
    session_id: str,
    user_role: str = "sre_admin",
) -> agent_context.ContextEnvelope:
    """Builds a verified `ContextEnvelope` for live Claim-and-Taint sandbox verification."""
    tenant_record = agent_context.TENANT_DIRECTORY[tenant_id]
    tier_enum = agent_context.SubscriptionTier(
        str(tenant_record.get("tier", "standard"))
    )
    scopes_raw = [
        str(item) for item in tenant_record.get("authorized_scopes", ())
    ]
    for required_scope in (
        "agent:cymbal_shared_diagnostic_agent",
        "2lo:cymbal.sandbox.execute",
    ):
        if required_scope not in scopes_raw:
            scopes_raw.append(required_scope)
    scopes_tuple = tuple(scopes_raw)
    return agent_context.ContextEnvelope(
        security=agent_context.SecurityContext(
            iss=str(tenant_record["iss"]),
            sub=user_sub,
            aud="https://agent-gateway.cymbal.internal",
            exp=int(time.time()) + 3600,
            jti=f"jwt-live-sbx-{uuid.uuid4().hex[:10]}",
            kid="live-verify",
            dpop_jkt=f"jkt-{tenant_id}-{session_id}",
            user_role=user_role,
            idp_provider=str(
                tenant_record.get("idp_provider", "google_workspace_oidc")
            ),
        ),
        tenant=agent_context.TenantContext(
            tenant_id=tenant_id,
            subscription_tier=tier_enum,
            org_unit=str(tenant_record.get("org_unit", "pooled")),
            authorized_scopes=scopes_tuple,
            thinking_token_budget=int(
                tenant_record.get("thinking_budget", 4000)
            ),
            cmek_key_name=str(tenant_record.get("cmek_key_name", "")),
        ),
        request=agent_context.RequestContext(
            trace_id=f"trace-{uuid.uuid4().hex[:12]}",
            correlation_id=f"corr-{uuid.uuid4().hex[:12]}",
            session_id=session_id,
        ),
        context_token="",
        delegation_sig="",
    )


def build_dry_run_plan(
    *, project_id: str, location: str, ttl_seconds: int
) -> dict[str, object]:
    """Builds the deterministic provisioning and smoke-test plan without network calls.

    Args:
        project_id: Target Google Cloud project ID.
        location: Regional Vertex AI / Gemini endpoint (for example, `us-central1`).
        ttl_seconds: Ephemeral smoke-test sandbox TTL in seconds.

    Returns:
        Dictionary describing the parent runtime, sandbox spec, and Terraform variable snippet.
    """
    placeholder_engine = f"projects/{project_id}/locations/{location}/reasoningEngines/<PROVISIONED_ID>"
    return {
        "mode": "DRY_RUN",
        "project_id": project_id,
        "location": location,
        "sdk_package": "agentplatform",
        "sdk_version": getattr(agentplatform, "__version__", "unknown"),
        "parent_resource_action": "agentplatform.Client.runtimes.create()",
        "smoke_test_spec": {
            "code_execution_environment": {
                "code_language": "LANGUAGE_PYTHON",
            },
            "ttl": f"{ttl_seconds}s",
            "zero_credentials_mounted": True,
        },
        "terraform_tfvars_snippet": _tfvars_snippet(placeholder_engine),
    }


def run_live_manager_verification(
    *,
    project_id: str,
    location: str,
    engine_resource_name: str,
    ttl_seconds: int,
    use_gcloud_auth: bool,
) -> dict[str, object]:
    """Verifies `LiveGeminiAgentSandboxClient`, `GeminiAgentSandboxManager`, and the MCP tool.

    Args:
        project_id: Target Google Cloud project ID.
        location: Regional Vertex AI / Gemini endpoint (`us-central1`).
        engine_resource_name: Full `projects/.../reasoningEngines/...` resource name.
        ttl_seconds: Sandbox TTL in seconds (`<= 3600`).
        use_gcloud_auth: When `True`, authenticates control-plane calls via `gcloud`.

    Returns:
        Structured verification receipt with measured latencies, gVisor kernel, and guard results.

    Raises:
        RuntimeError: If any isolation invariant or live sandbox check fails.
    """
    headers_provider = (
        _build_gcloud_headers_provider() if use_gcloud_auth else None
    )
    live_backend = sandbox_execution.LiveGeminiAgentSandboxClient(
        project_id=project_id,
        location=location,
        reasoning_engine_name=engine_resource_name,
        headers_provider=headers_provider,
        live_mode_fn=_always_live_mode,
    )
    manager = sandbox_execution.GeminiAgentSandboxManager(
        backend=live_backend,
        project_id=project_id,
        location=location,
        default_ttl_seconds=float(ttl_seconds),
    )

    session_id = f"sess-live-{uuid.uuid4().hex[:10]}"
    finvault_tenant = "tenant-finvault-alpha"
    retail_tenant = "tenant-retailstream-beta"
    agent_id = "cymbal_shared_diagnostic_agent"
    finvault_envelope = _mint_verified_envelope(
        tenant_id=finvault_tenant,
        user_sub="sre-lead@finvault.example.com",
        session_id=session_id,
    )
    retail_envelope = _mint_verified_envelope(
        tenant_id=retail_tenant,
        user_sub="ops@retailstream.example.com",
        session_id=f"sess-other-{uuid.uuid4().hex[:8]}",
    )
    tool_context = _VerifiedToolContext(
        state={
            "temp:tenant_id": finvault_tenant,
            "temp:user_sub": finvault_envelope.security.sub,
            "temp:session_id": session_id,
            "temp:tier": "enterprise",
            "temp:user_role": "sre_admin",
            "temp:agent_id": agent_id,
            "temp:authorized_scopes": list(
                finvault_envelope.tenant.authorized_scopes
            ),
        }
    )

    unscoped_tool_context = _VerifiedToolContext(
        state={
            "temp:tenant_id": finvault_tenant,
            "temp:user_sub": finvault_envelope.security.sub,
            "temp:session_id": session_id,
            "temp:tier": "enterprise",
            "temp:user_role": "sre_admin",
            "temp:agent_id": agent_id,
            "temp:authorized_scopes": ["2lo:cymbal.telemetry.read"],
        }
    )
    opt_in_scope_enforced = False
    try:
        asyncio.run(
            mcp_server_tools.execute_diagnostic_sandbox(
                code="print(1)",
                language="python",
                tool_context=unscoped_tool_context,
                sandbox_manager=manager,
            )
        )
    except PermissionError as scope_exc:
        opt_in_scope_enforced = "2lo:cymbal.sandbox.execute" in str(scope_exc)
    if not opt_in_scope_enforced:
        raise RuntimeError(
            "Expected opt-in 2lo:cymbal.sandbox.execute scope gate did not fire."
        )

    metadata_probe_blocked = False
    try:
        asyncio.run(
            mcp_server_tools.execute_diagnostic_sandbox(
                code="target = 'http://169.254.169.254/computeMetadata/v1/'\nprint(target)",
                language="python",
                tool_context=tool_context,
                sandbox_manager=manager,
            )
        )
    except PermissionError as probe_exc:
        metadata_probe_blocked = (
            "E_SANDBOX_CREDENTIAL_OR_METADATA_BLOCKED" in str(probe_exc)
        )
    if not metadata_probe_blocked:
        raise RuntimeError(
            "Expected pre-execution metadata probe block did not trigger."
        )

    claimed_resource_names: list[str] = []
    claimed_sandbox_id = ""
    bash_sandbox_id = ""
    try:
        turn1_code = (
            "import getpass, json, os, platform, socket\n"
            "with open('readonly_input.json', 'r', encoding='utf-8') as handle:\n"
            "    mounted_payload = json.load(handle)\n"
            "internet_blocked = False\n"
            "try:\n"
            "    sock = socket.create_connection(('8.8.8.8', 53), timeout=1.5)\n"
            "    sock.close()\n"
            "except OSError:\n"
            "    internet_blocked = True\n"
            "cloud_env_keys = sorted(\n"
            "    key for key in os.environ\n"
            "    if key.startswith(('GOOGLE_', 'GCE_', 'CLOUD_', 'AWS_'))\n"
            ")\n"
            "with open('/tmp/cymbal_session_state.json', 'w', encoding='utf-8') as marker:\n"
            "    json.dump({'turn': 1, 'incidents': len(mounted_payload['incidents'])}, marker)\n"
            "print(json.dumps({\n"
            "    'kernel_release': platform.release(),\n"
            "    'cwd': os.getcwd(),\n"
            "    'user': getpass.getuser(),\n"
            "    'uid': os.getuid(),\n"
            "    'public_internet_blocked': internet_blocked,\n"
            "    'cloud_env_keys': cloud_env_keys,\n"
            "    'readonly_incident_count': len(mounted_payload['incidents']),\n"
            "    'dlp_probe': '123-45-6789',\n"
            "}, sort_keys=True))\n"
        )
        turn1_started = time.monotonic()
        turn1_mcp_result = asyncio.run(
            mcp_server_tools.execute_diagnostic_sandbox(
                code=turn1_code,
                language="python",
                readonly_tool_output={
                    "incidents": [
                        {"id": "INC-901", "severity": "P1"},
                        {"id": "INC-902", "severity": "P2"},
                    ]
                },
                tool_context=tool_context,
                sandbox_manager=manager,
            )
        )
        turn1_elapsed = round(time.monotonic() - turn1_started, 3)
        turn1_receipt = turn1_mcp_result["sandbox_execution"]
        if not isinstance(turn1_receipt, dict):
            raise TypeError("Unexpected sandbox_execution payload in Turn 1.")
        claimed_sandbox_id = str(turn1_receipt["sandbox_id"])
        claimed_resource_names.append(
            str(turn1_receipt["sandbox_resource_name"])
        )
        turn1_stdout_raw = str(turn1_receipt["sanitized_stdout"]).strip()
        turn1_parsed = json.loads(turn1_stdout_raw)

        if "gvisor" not in str(turn1_parsed.get("kernel_release", "")).lower():
            raise RuntimeError(f"Expected gVisor kernel, got {turn1_parsed!r}.")
        if turn1_parsed.get("public_internet_blocked") is not True:
            raise RuntimeError(
                "Expected public internet egress (8.8.8.8:53) to be blocked."
            )
        if turn1_parsed.get("cloud_env_keys") != []:
            raise RuntimeError(
                f"Unexpected cloud env keys inside sandbox: {turn1_parsed!r}."
            )
        if turn1_parsed.get("readonly_incident_count") != 2:
            raise RuntimeError(
                "readonly_input.json chunk was not mounted cleanly."
            )
        if turn1_parsed.get("dlp_probe") != "[REDACTED_BANKING_SSN]":
            raise RuntimeError(
                "Hop 4 DLP redaction did not scrub SSN in live sandbox stdout."
            )

        turn2_code = (
            "import json\n"
            "with open('/tmp/cymbal_session_state.json', 'r', encoding='utf-8') as marker:\n"
            "    prior_state = json.load(marker)\n"
            "print(json.dumps({'reused_state': prior_state, 'turn': 2}, sort_keys=True))\n"
        )
        turn2_started = time.monotonic()
        turn2_mcp_result = asyncio.run(
            mcp_server_tools.execute_diagnostic_sandbox(
                code=turn2_code,
                language="python",
                tool_context=tool_context,
                sandbox_manager=manager,
            )
        )
        turn2_elapsed = round(time.monotonic() - turn2_started, 3)
        turn2_receipt = turn2_mcp_result["sandbox_execution"]
        if not isinstance(turn2_receipt, dict):
            raise TypeError("Unexpected sandbox_execution payload in Turn 2.")
        if turn2_receipt.get("reused_session_sandbox") is not True:
            raise RuntimeError(
                "Turn 2 did not reuse the session-tainted sandbox."
            )
        if turn2_receipt.get("sandbox_id") != claimed_sandbox_id:
            raise RuntimeError(
                "Turn 2 sandbox_id mismatched Turn 1 sandbox_id."
            )
        turn2_parsed = json.loads(
            str(turn2_receipt["sanitized_stdout"]).strip()
        )

        cross_tenant_hijack_blocked = False
        try:
            manager.execute_in_session_sandbox(
                envelope=retail_envelope,
                agent_id=agent_id,
                code="print(1)",
                language="python",
                expected_sandbox_id=claimed_sandbox_id,
            )
        except PermissionError as hijack_exc:
            cross_tenant_hijack_blocked = (
                "E_CROSS_TENANT_SANDBOX_TAINT_VIOLATION" in str(hijack_exc)
            )
        if not cross_tenant_hijack_blocked:
            raise RuntimeError("Cross-tenant sandbox hijack was not blocked.")

        pause_probe_status = "NOT_TESTED"
        try:
            pause_receipt = manager.pause_session_sandbox(
                envelope=finvault_envelope,
                agent_id=agent_id,
                language=sandbox_execution.SandboxLanguage.PYTHON,
            )
            if str(pause_receipt.get("status")) != "STATE_PAUSED":
                raise RuntimeError(
                    f"Unexpected python pause receipt: {pause_receipt!r}"
                )
            resumed_python_result = asyncio.run(
                mcp_server_tools.execute_diagnostic_sandbox(
                    code="print('python_resumed_ok')",
                    language="python",
                    tool_context=tool_context,
                    sandbox_manager=manager,
                )
            )
            resumed_py_receipt = resumed_python_result["sandbox_execution"]
            if not isinstance(resumed_py_receipt, dict):
                raise TypeError(
                    "Unexpected sandbox_execution payload after python resume."
                )
            if (
                resumed_py_receipt.get("sandbox_id") != claimed_sandbox_id
                or resumed_py_receipt.get("reused_session_sandbox") is not True
                or resumed_py_receipt.get("state") != "STATE_RUNNING"
            ):
                raise RuntimeError(
                    f"Python sandbox resume mismatch: {resumed_py_receipt!r}"
                )
            pause_probe_status = "PAUSED_AND_RESUMED"
        except sandbox_execution.SandboxUnavailableError as pause_exc:
            err_text = str(pause_exc)
            if any(
                marker in err_text
                for marker in ("HTTP 400", "HTTP 404", "HTTP 500", "HTTP 501")
            ):
                pause_probe_status = (
                    f"UNSUPPORTED_ON_BUILTIN_CODE_EXEC ({pause_exc})"
                )
            else:
                raise

        # 3-chunk `bash` (`shellEnvironment`) + `pause` + `resume` end-to-end verification:
        bash_turn1_code = (
            "set -euo pipefail; "
            "echo 'cymbal-bash-state' > /tmp/cymbal_bash_state.txt; "
            "cloud_keys=$(env | grep -E '^(GOOGLE_|GCE_|CLOUD_|AWS_)=' || true); "
            'echo "user=$(id -un) uid=$(id -u) cloud=${cloud_keys} ssn=123-45-6789"'
        )
        bash_started = time.monotonic()
        bash_turn1_result = asyncio.run(
            mcp_server_tools.execute_diagnostic_sandbox(
                code=bash_turn1_code,
                language="bash",
                tool_context=tool_context,
                sandbox_manager=manager,
            )
        )
        bash_elapsed = round(time.monotonic() - bash_started, 3)
        bash_turn1_receipt = bash_turn1_result["sandbox_execution"]
        if not isinstance(bash_turn1_receipt, dict):
            raise TypeError(
                "Unexpected sandbox_execution payload in Bash Turn 1."
            )
        bash_sandbox_id = str(bash_turn1_receipt["sandbox_id"])
        claimed_resource_names.append(
            str(bash_turn1_receipt["sandbox_resource_name"])
        )
        if bash_sandbox_id == claimed_sandbox_id:
            raise RuntimeError(
                "Bash workload reused Python sandbox despite language taint isolation."
            )
        if (
            bash_turn1_receipt.get("backend_mode")
            != "LIVE_AGENT_SANDBOX_SHELL_SANDBOX_ENVIRONMENT"
        ):
            raise RuntimeError(
                f"Expected LIVE_AGENT_SANDBOX_SHELL_SANDBOX_ENVIRONMENT, got {bash_turn1_receipt!r}"
            )
        bash_stdout = str(bash_turn1_receipt.get("sanitized_stdout", ""))
        if (
            "123-45-6789" in bash_stdout
            or "[REDACTED_BANKING_SSN]" not in bash_stdout
        ):
            raise RuntimeError(
                f"Hop 4 DLP redaction failed on bash stdout: {bash_stdout!r}"
            )
        if "cloud=" not in bash_stdout or "cloud=GOOGLE_" in bash_stdout:
            raise RuntimeError(
                f"Unexpected cloud env keys in bash sandbox: {bash_stdout!r}"
            )

        bash_pause_receipt = manager.pause_session_sandbox(
            envelope=finvault_envelope,
            agent_id=agent_id,
            language=sandbox_execution.SandboxLanguage.BASH,
        )
        if (
            bash_pause_receipt.get("status") != "STATE_PAUSED"
            or bash_pause_receipt.get("sandbox_id") != bash_sandbox_id
        ):
            raise RuntimeError(
                f"Bash pause failed or mismatched: {bash_pause_receipt!r}"
            )

        bash_resume_result = asyncio.run(
            mcp_server_tools.execute_diagnostic_sandbox(
                code="cat /tmp/cymbal_bash_state.txt",
                language="bash",
                tool_context=tool_context,
                sandbox_manager=manager,
            )
        )
        bash_resume_receipt = bash_resume_result["sandbox_execution"]
        if not isinstance(bash_resume_receipt, dict):
            raise TypeError(
                "Unexpected sandbox_execution payload after Bash resume."
            )
        if (
            bash_resume_receipt.get("sandbox_id") != bash_sandbox_id
            or bash_resume_receipt.get("reused_session_sandbox") is not True
            or bash_resume_receipt.get("state") != "STATE_RUNNING"
            or "cymbal-bash-state"
            not in str(bash_resume_receipt.get("sanitized_stdout", ""))
        ):
            raise RuntimeError(
                f"Bash sandbox resume mismatch: {bash_resume_receipt!r}"
            )

        release_receipt = manager.release_session_sandbox(
            envelope=finvault_envelope,
            agent_id=agent_id,
        )
        claimed_resource_names.clear()

        reattach_after_destroy_blocked = False
        try:
            manager.execute_in_session_sandbox(
                envelope=finvault_envelope,
                agent_id=agent_id,
                code="print(1)",
                language="python",
                expected_sandbox_id=claimed_sandbox_id,
            )
        except PermissionError as destroy_exc:
            reattach_after_destroy_blocked = (
                "E_SANDBOX_ALREADY_DESTROYED" in str(destroy_exc)
            )
        if not reattach_after_destroy_blocked:
            raise RuntimeError(
                "Destroyed python sandbox_id reattach was not blocked."
            )

        bash_reattach_after_destroy_blocked = False
        try:
            manager.execute_in_session_sandbox(
                envelope=finvault_envelope,
                agent_id=agent_id,
                code="echo ok",
                language="bash",
                expected_sandbox_id=bash_sandbox_id,
            )
        except PermissionError as bash_destroy_exc:
            bash_reattach_after_destroy_blocked = (
                "E_SANDBOX_ALREADY_DESTROYED" in str(bash_destroy_exc)
            )
        if not bash_reattach_after_destroy_blocked:
            raise RuntimeError(
                "Destroyed bash sandbox_id reattach was not blocked."
            )

        return {
            "backend_mode": str(turn1_receipt["backend_mode"]),
            "sandbox_id_tested": claimed_sandbox_id,
            "bash_sandbox_id_tested": bash_sandbox_id,
            "claim_and_turn1_latency_seconds": turn1_elapsed,
            "warm_turn2_latency_seconds": turn2_elapsed,
            "bash_turn1_latency_seconds": bash_elapsed,
            "turn1_sandbox_observations": turn1_parsed,
            "turn2_stateful_reuse": turn2_parsed,
            "bash_turn1_observations": bash_stdout.strip(),
            "bash_pause_receipt": bash_pause_receipt,
            "bash_resume_stateful_reuse": {
                "sandbox_id": bash_resume_receipt["sandbox_id"],
                "state": bash_resume_receipt["state"],
                "reused_session_sandbox": bash_resume_receipt[
                    "reused_session_sandbox"
                ],
                "sanitized_stdout": str(
                    bash_resume_receipt["sanitized_stdout"]
                ).strip(),
            },
            "opt_in_scope_enforced": opt_in_scope_enforced,
            "metadata_probe_blocked_pre_exec": metadata_probe_blocked,
            "cross_tenant_hijack_blocked": cross_tenant_hijack_blocked,
            "builtin_code_exec_pause_probe": pause_probe_status,
            "release_receipt": release_receipt,
            "reattach_after_destroy_blocked": reattach_after_destroy_blocked,
            "bash_reattach_after_destroy_blocked": bash_reattach_after_destroy_blocked,
        }
    finally:
        for res_name in claimed_resource_names:
            try:
                live_backend.delete_sandbox(sandbox_resource_name=res_name)
            except sandbox_execution.SandboxUnavailableError as cleanup_exc:
                print(
                    f"[cleanup warning] failed to delete {res_name}: {cleanup_exc}",
                    file=sys.stderr,
                )


def provision_and_smoke_test_live(
    *,
    project_id: str,
    location: str,
    existing_engine_name: str | None,
    ttl_seconds: int,
    use_gcloud_auth: bool = False,
    verify_manager: bool = False,
) -> dict[str, object]:
    """Creates or reuses a parent `ReasoningEngine` and smoke-tests a live `SandboxEnvironment`.

    Args:
        project_id: Target Google Cloud project ID with `aiplatform.googleapis.com` enabled.
        location: Regional Vertex AI / Gemini endpoint (`us-central1`).
        existing_engine_name: Optional existing `reasoningEngines/{id}` resource name.
        ttl_seconds: TTL in seconds for the ephemeral smoke-test sandbox (`<= 3600`).
        use_gcloud_auth: When `True`, uses `gcloud auth print-access-token` credentials.
        verify_manager: When `True`, also exercises `GeminiAgentSandboxManager` + MCP live flow.

    Returns:
        Receipt with the live `AGENT_SANDBOX_REASONING_ENGINE_NAME` and test outputs.

    Raises:
        RuntimeError: If parent runtime creation or sandbox execution fails.
    """
    explicit_credentials = None
    if use_gcloud_auth:
        explicit_credentials = google.oauth2.credentials.Credentials(
            token=_resolve_gcloud_access_token(),
            quota_project_id=project_id,
        )

    ap_client = agentplatform.Client(
        project=project_id,
        location=location,
        credentials=explicit_credentials,
    )
    if existing_engine_name:
        engine_resource_name = existing_engine_name.strip()
    else:
        created_runtime = ap_client.runtimes.create()
        api_resource = getattr(created_runtime, "api_resource", None)
        engine_resource_name = str(
            getattr(api_resource, "name", "")
            or getattr(created_runtime, "name", "")
            or ""
        ).strip()
        if not engine_resource_name:
            raise RuntimeError(
                "agentplatform.Client.runtimes.create() returned an empty name."
            )

    sdk_create_started = time.monotonic()
    operation = ap_client.sandboxes.create(
        name=engine_resource_name,
        spec={
            "code_execution_environment": {"code_language": "LANGUAGE_PYTHON"}
        },
        config=agentplatform_types.CreateRuntimeSandboxConfig(
            display_name="cymbal-ws2-sandbox-smoketest",
            ttl=f"{ttl_seconds}s",
            wait_for_completion=True,
        ),
    )
    sdk_create_seconds = round(time.monotonic() - sdk_create_started, 3)
    sandbox_response = getattr(operation, "response", None)
    sandbox_name = str(getattr(sandbox_response, "name", "") or "").strip()
    if not sandbox_name:
        raise RuntimeError(
            "sandboxes.create() did not return a SandboxEnvironment name."
        )

    try:
        sdk_exec_started = time.monotonic()
        execution = ap_client.sandboxes.execute_code(
            name=sandbox_name,
            input_data={
                "code": (
                    "import getpass, json, os, platform\n"
                    "print(json.dumps({\n"
                    "    'kernel_release': platform.release(),\n"
                    "    'user': getpass.getuser(),\n"
                    "    'cwd': os.getcwd(),\n"
                    "    'has_adc': 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ,\n"
                    "}, sort_keys=True))"
                )
            },
        )
        sdk_exec_seconds = round(time.monotonic() - sdk_exec_started, 3)
        decoded_chunks: list[str] = []
        for output_chunk in getattr(execution, "outputs", None) or []:
            chunk_bytes = getattr(output_chunk, "data", None)
            if isinstance(chunk_bytes, bytes):
                decoded_chunks.append(
                    chunk_bytes.decode("utf-8", errors="replace")
                )
    finally:
        ap_client.sandboxes.delete(name=sandbox_name)

    shell_create_started = time.monotonic()
    shell_operation = ap_client.sandboxes.create(
        name=engine_resource_name,
        spec={"shell_environment": {}},
        config=agentplatform_types.CreateRuntimeSandboxConfig(
            display_name="cymbal-ws2-shell-smoketest",
            ttl=f"{ttl_seconds}s",
            wait_for_completion=True,
        ),
    )
    shell_create_seconds = round(time.monotonic() - shell_create_started, 3)
    shell_response = getattr(shell_operation, "response", None)
    shell_sandbox_name = str(getattr(shell_response, "name", "") or "").strip()
    if not shell_sandbox_name:
        raise RuntimeError(
            "shell sandboxes.create() did not return a SandboxEnvironment name."
        )

    try:
        shell_exec_started = time.monotonic()
        bash_turn1 = ap_client.sandboxes.execute_bash(
            name=shell_sandbox_name,
            command=(
                "echo 'cymbal-shell-ok' > /tmp/cymbal_sdk_marker.txt && "
                "cat /tmp/cymbal_sdk_marker.txt"
            ),
        )
        shell_exec_seconds = round(time.monotonic() - shell_exec_started, 3)
        if int(
            bash_turn1.get("returncode", -1)
        ) != 0 or "cymbal-shell-ok" not in str(bash_turn1.get("stdout", "")):
            raise RuntimeError(
                f"Unexpected shell execute_bash output: {bash_turn1!r}"
            )

        ap_client.sandboxes.pause(
            name=shell_sandbox_name,
            config={"wait_for_completion": True},
        )
        ap_client.sandboxes.resume(
            name=shell_sandbox_name,
            config={"wait_for_completion": True},
        )
        bash_resumed: dict[str, object] = {}
        for resume_attempt in range(5):
            try:
                bash_resumed = ap_client.sandboxes.execute_bash(
                    name=shell_sandbox_name,
                    command="cat /tmp/cymbal_sdk_marker.txt",
                )
                break
            except Exception as exec_exc:
                if resume_attempt + 1 < 5 and (
                    "UNAVAILABLE on URL" in str(exec_exc)
                    or "URL_UNREACHABLE" in str(exec_exc)
                ):
                    time.sleep(2.0)
                    continue
                raise
        if int(
            bash_resumed.get("returncode", -1)
        ) != 0 or "cymbal-shell-ok" not in str(bash_resumed.get("stdout", "")):
            raise RuntimeError(
                f"Shell sandbox did not preserve state across pause/resume: {bash_resumed!r}"
            )
    finally:
        ap_client.sandboxes.delete(name=shell_sandbox_name)

    result_payload: dict[str, object] = {
        "mode": "LIVE_PROVISIONED_AND_VERIFIED",
        "project_id": project_id,
        "location": location,
        "sdk_package": "agentplatform",
        "sdk_version": getattr(agentplatform, "__version__", "unknown"),
        "agent_sandbox_reasoning_engine_name": engine_resource_name,
        "sdk_sandbox_create_latency_seconds": sdk_create_seconds,
        "sdk_execute_code_latency_seconds": sdk_exec_seconds,
        "smoke_test_sandbox_deleted": sandbox_name,
        "smoke_test_outputs": decoded_chunks,
        "shell_sandbox_create_latency_seconds": shell_create_seconds,
        "shell_execute_bash_latency_seconds": shell_exec_seconds,
        "shell_smoke_test_sandbox_deleted": shell_sandbox_name,
        "shell_smoke_test_outputs": {
            "turn1": bash_turn1,
            "after_pause_resume": bash_resumed,
        },
        "shell_pause_resume_verified": True,
        "terraform_tfvars_snippet": _tfvars_snippet(engine_resource_name),
    }
    if verify_manager:
        result_payload["manager_and_mcp_verification"] = (
            run_live_manager_verification(
                project_id=project_id,
                location=location,
                engine_resource_name=engine_resource_name,
                ttl_seconds=ttl_seconds,
                use_gcloud_auth=use_gcloud_auth,
            )
        )
    return result_payload


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for dry-run planning or live Agent Sandbox in Gemini provisioning.

    Args:
        argv: Optional CLI argument sequence.

    Returns:
        Process exit code (`0` on success).
    """
    parser = argparse.ArgumentParser(
        description="Provision and verify Agent Sandbox in Gemini (ADR-0012 / PR-S2)."
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Execute live Vertex AI / Agent Sandbox in Gemini API calls (default is dry-run).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Explicitly print the offline provisioning plan without network calls (default).",
    )
    parser.add_argument(
        "--use-gcloud-auth",
        action="store_true",
        help="Authenticate control-plane calls via `gcloud auth print-access-token`.",
    )
    parser.add_argument(
        "--verify-manager",
        action="store_true",
        help="Run end-to-end GeminiAgentSandboxManager + MCP execute_diagnostic_sandbox checks.",
    )
    parser.add_argument(
        "--project-id",
        default=None,
        help="Target GCP project ID (defaults to platform config / GOOGLE_CLOUD_PROJECT).",
    )
    parser.add_argument(
        "--location",
        default=None,
        help="Regional Vertex AI / Gemini endpoint (defaults to platform config gcp.region).",
    )
    parser.add_argument(
        "--reasoning-engine-name",
        default=None,
        help="Reuse an existing projects/.../reasoningEngines/... parent resource.",
    )
    parser.add_argument(
        "--ttl-seconds",
        type=int,
        default=300,
        help="Smoke-test sandbox TTL in seconds (default: 300).",
    )
    parsed_args = parser.parse_args(list(argv) if argv is not None else None)

    resolved_location = parsed_args.location or get_platform_config().gcp.region
    resolved_project = parsed_args.project_id or resolve_project_id()

    if not parsed_args.live:
        plan_output = build_dry_run_plan(
            project_id=resolved_project,
            location=resolved_location,
            ttl_seconds=parsed_args.ttl_seconds,
        )
        print(json.dumps(plan_output, indent=2, sort_keys=True))
        return 0

    live_receipt = provision_and_smoke_test_live(
        project_id=resolved_project,
        location=resolved_location,
        existing_engine_name=parsed_args.reasoning_engine_name,
        ttl_seconds=parsed_args.ttl_seconds,
        use_gcloud_auth=parsed_args.use_gcloud_auth,
        verify_manager=parsed_args.verify_manager,
    )
    print(json.dumps(live_receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
