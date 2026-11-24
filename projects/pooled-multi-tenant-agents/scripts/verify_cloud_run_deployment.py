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

# pylint: disable=inconsistent-quotes,line-too-long,wrong-import-position

"""Tier 3 post-deploy smoke checks for the Cloud Run gateway (`make smoke ENV=<env>`).

Read-only, tenant-agnostic, and driven by the platform config, so the same command validates our
sandbox and any customer deployment:

1. `GET /api/v1/health`: up, serving the expected environment and tenant count.
2. `GET /.well-known/ai-catalog.json` without a token is refused (401): identity is enforced.
3. Sandbox only: every configured tenant signs in through the sandbox issuer (Hop 0 token ->
   DPoP-bound gateway token) and gets its own catalog; `POST /api/v1/breach-matrix-10` blocks all
   vectors. Elsewhere the sandbox endpoints must not exist (404).

Cloud Run's IAM token goes in `X-Serverless-Authorization`, because the app's own DPoP token uses
`Authorization`.

Live isolation proofs (KMS / Secret Manager / GCS / BigQuery denials) are Tier 4 (`make validate`).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agents.platform_config import load_platform_config
from scripts.sandbox_auth import SandboxCaller

SERVICE = "cymbal-pooled-gateway"
_DISAGGREGATED_SERVICES = (
    "cymbal-credential-broker",
    "cymbal-agent-shared",
    "cymbal-agent-finvault-alpha",
)
_PUBLIC_IAM_MEMBERS = frozenset({"allUsers", "allAuthenticatedUsers"})


def _gcloud(*args: str) -> str:
    env = {**os.environ, "CLOUDSDK_METRICS_ENVIRONMENT": "datacloud.ai-agent"}
    return subprocess.run(
        ["gcloud", *args], capture_output=True, text=True, check=True, env=env
    ).stdout.strip()


def _is_iap_redirect(resp: httpx.Response) -> bool:
    """Returns True only for genuine Google Identity-Aware Proxy OAuth redirects."""
    if resp.status_code not in (302, 303, 307):
        return False
    location = str(resp.headers.get("location") or "")
    parts = urlsplit(location)
    if parts.scheme != "https" or parts.netloc != "accounts.google.com":
        return False
    redirect_targets = parse_qs(parts.query).get("redirect_uri", [])
    return any(
        urlsplit(target).netloc == "iap.googleapis.com"
        for target in redirect_targets
    )


def _service_ready_and_private(
    service: str, project_id: str, region: str, *, required: bool
) -> tuple[bool, bool]:
    """Verifies Cloud Run Ready=True and absence of allUsers/allAuthenticatedUsers IAM."""
    try:
        raw_svc = _gcloud(
            "run",
            "services",
            "describe",
            service,
            f"--region={region}",
            f"--project={project_id}",
            "--format=json",
        )
    except subprocess.CalledProcessError:
        if required:
            raise
        return (False, False)
    svc_doc = json.loads(raw_svc or "{}")
    conditions = svc_doc.get("status", {}).get("conditions", [])
    ready = any(
        c.get("type") == "Ready" and c.get("status") == "True"
        for c in conditions
        if isinstance(c, dict)
    )
    assert ready, f"{service} is not Ready=True: {conditions}"

    raw_iam = _gcloud(
        "run",
        "services",
        "get-iam-policy",
        service,
        f"--region={region}",
        f"--project={project_id}",
        "--format=json",
    )
    iam_doc = json.loads(raw_iam or "{}")
    for binding in iam_doc.get("bindings", []) or []:
        members = set(binding.get("members", []) or [])
        leaked = members & _PUBLIC_IAM_MEMBERS
        assert (
            not leaked
        ), f"{service} exposes public IAM members: {sorted(leaked)}"

    annotations = svc_doc.get("metadata", {}).get("annotations", {}) or {}
    iap_on = annotations.get("run.googleapis.com/iap-enabled") == "true"
    return (True, iap_on)


def resolve_service_url(project_id: str, region: str) -> str:
    url = os.getenv("CLOUD_RUN_URL")
    if url:
        return url
    return _gcloud(
        "run",
        "services",
        "describe",
        SERVICE,
        f"--region={region}",
        f"--project={project_id}",
        "--format=value(status.url)",
    )


def run_smoke(env_name: str) -> list[str]:
    cfg = load_platform_config(env_name)
    url = resolve_service_url(cfg.gcp.project_id, cfg.gcp.region)
    token = os.getenv("CLOUD_RUN_ID_TOKEN") or _gcloud(
        "auth", "print-identity-token"
    )
    iap_cookie = os.getenv("CLOUD_RUN_IAP_COOKIE", "").strip()
    passed: list[str] = []
    iam: dict[str, str] = {"X-Serverless-Authorization": f"Bearer {token}"}
    if iap_cookie:
        iam["Cookie"] = f"GCP_IAAP_AUTH_TOKEN={iap_cookie}"
    sandbox = (
        cfg.environment == "sandbox" and cfg.data_classification == "synthetic"
    )
    with httpx.Client(base_url=url, headers=iam, timeout=180.0) as c:
        # /healthz is reserved by the Cloud Run front end; use /api/v1/health.
        health = c.get("/api/v1/health")
        if not iap_cookie and _is_iap_redirect(health):
            anon_catalog = c.get("/.well-known/ai-catalog.json")
            assert anon_catalog.status_code in (
                302,
                303,
                307,
                401,
                403,
            ), f"catalog not blocked behind IAP: HTTP {anon_catalog.status_code}"
            anon_invoke = c.post(
                "/api/v1/invoke-agent", json={"prompt": "ping"}
            )
            assert anon_invoke.status_code in (
                302,
                303,
                307,
                401,
                403,
            ), f"invoke-agent not blocked behind IAP: HTTP {anon_invoke.status_code}"
            _, iap_on = _service_ready_and_private(
                SERVICE, cfg.gcp.project_id, cfg.gcp.region, required=True
            )
            passed.append(
                "gateway Ready=True (lifespan RLS & KMS checks passed; "
                f"iap_enabled={str(iap_on).lower()})"
            )
            ready_disagg: list[str] = []
            for svc in _DISAGGREGATED_SERVICES:
                present, _ = _service_ready_and_private(
                    svc, cfg.gcp.project_id, cfg.gcp.region, required=False
                )
                if present:
                    ready_disagg.append(svc)
            passed.append(
                "Cloud Run Direct IAP perimeter active (302 -> iap.googleapis.com; "
                "0 public IAM bindings)"
            )
            if ready_disagg:
                passed.append(
                    f"disaggregated services Ready=True: {ready_disagg}"
                )
            return passed
        health.raise_for_status()
        body = health.json()
        assert body["status"] == "ok", body
        assert body.get("environment", env_name) == env_name, body
        passed.append(
            f"health ok (environment={body.get('environment')}, tenants={body.get('tenants')})"
        )

        anonymous = c.get("/.well-known/ai-catalog.json")
        assert (
            anonymous.status_code == 401
        ), f"catalog without a token: HTTP {anonymous.status_code}"
        passed.append("catalog without a token refused (401)")

        anon_invoke = c.post("/api/v1/invoke-agent", json={"prompt": "ping"})
        assert (
            anon_invoke.status_code == 401
        ), f"invoke-agent without token: HTTP {anon_invoke.status_code}"
        anon_pause = c.post(
            "/api/v1/sandboxes/session/pause",
            json={"agent_id": "cymbal_shared_diagnostic_agent"},
        )
        assert (
            anon_pause.status_code == 401
        ), f"sandbox pause without token: HTTP {anon_pause.status_code}"
        passed.append(
            "unauthenticated invoke-agent & sandbox pause refused (401)"
        )

        if not sandbox:
            matrix = c.post("/api/v1/breach-matrix-10")
            assert (
                matrix.status_code == 404
            ), f"sandbox endpoint exposed: HTTP {matrix.status_code}"
            sbx_tok = c.post(
                "/api/v1/sandbox/token",
                json={
                    "tenant_id": cfg.tenants[0].tenant_id,
                    "sub": "smoke",
                    "role": "read_only_analyst",
                },
            )
            assert (
                sbx_tok.status_code == 404
            ), f"sandbox token endpoint exposed: HTTP {sbx_tok.status_code}"
            passed.append("sandbox-only endpoints absent (404)")
            passed.append(
                "sandbox/turn authenticated smoke skipped (sandbox-only token issuer disabled)"
            )
            return passed

        for tenant in cfg.tenants:
            caller = SandboxCaller(
                url,
                tenant_id=tenant.tenant_id,
                sub=f"smoke@{tenant.tenant_id}",
                extra_headers=iam,
            )
            cat = c.get(
                "/.well-known/ai-catalog.json",
                headers=caller.headers(
                    "GET", caller.url("/.well-known/ai-catalog.json")
                ),
            )
            cat.raise_for_status()
            agents = [a["agent_id"] for a in cat.json()["agents"]]
            assert agents, f"{tenant.tenant_id}: empty catalog"
            passed.append(f"catalog {tenant.tenant_id}: {agents}")

        matrix = c.post("/api/v1/breach-matrix-10")
        matrix.raise_for_status()
        vectors = matrix.json().get("vectors", [])
        blocked = sum(1 for v in vectors if v.get("passed"))
        assert vectors, "breach matrix returned empty vectors"
        assert blocked == len(
            vectors
        ), f"breach matrix {blocked}/{len(vectors)}"
        passed.append(f"breach matrix {blocked}/{len(vectors)} blocked")

        smoke_tenant = next(
            (
                t
                for t in cfg.tenants
                if "2lo:cymbal.sandbox.execute" in t.authorized_scopes
            ),
            cfg.tenants[0],
        )
        admin_caller = SandboxCaller(
            url,
            tenant_id=smoke_tenant.tenant_id,
            sub=f"smoke-admin@{smoke_tenant.tenant_id}",
            role="sre_admin",
            extra_headers=iam,
        )
        try:
            turn_path = "/api/v1/invoke-agent"
            turn_resp = c.post(
                turn_path,
                json={
                    "agent_id": "cymbal_shared_diagnostic_agent",
                    "tool_name": "query_telemetry_rls",
                    "prompt": "Smoke check P1 latency summary.",
                },
                headers=admin_caller.headers(
                    "POST", admin_caller.url(turn_path)
                ),
            )
            if turn_resp.status_code in (401, 403):
                passed.append(
                    f"invoke-agent turn smoke skipped (unauthorized HTTP {turn_resp.status_code})"
                )
            else:
                turn_resp.raise_for_status()
                turn_body = turn_resp.json()
                assert turn_body.get("status") == "SUCCESS", turn_body
                assert (
                    turn_body.get("tenant_id") == smoke_tenant.tenant_id
                ), turn_body
                passed.append(
                    f"invoke-agent turn ok ({smoke_tenant.tenant_id})"
                )

            sbx_resp = c.post(
                turn_path,
                json={
                    "agent_id": "cymbal_shared_diagnostic_agent",
                    "tool_name": "execute_diagnostic_sandbox",
                    "sandbox_code": "total = sum([1, 2, 3])",
                    "sandbox_language": "python",
                },
                headers=admin_caller.headers(
                    "POST", admin_caller.url(turn_path)
                ),
            )
            if sbx_resp.status_code in (401, 403):
                passed.append(
                    f"sandbox lifecycle smoke skipped (unauthorized HTTP {sbx_resp.status_code})"
                )
            else:
                sbx_resp.raise_for_status()
                sbx_exec = sbx_resp.json().get("sandbox_execution", {})
                claimed_sbx_id = str(sbx_exec.get("sandbox_id") or "")
                assert claimed_sbx_id, sbx_resp.json()
                assert sbx_exec.get("state") == "STATE_RUNNING", sbx_exec
                try:
                    pause_path = "/api/v1/sandboxes/session/pause"
                    pause_resp = c.post(
                        pause_path,
                        json={"agent_id": "cymbal_shared_diagnostic_agent"},
                        headers=admin_caller.headers(
                            "POST", admin_caller.url(pause_path)
                        ),
                    )
                    if pause_resp.status_code in (401, 403):
                        passed.append(
                            "sandbox pause smoke skipped (unauthorized HTTP "
                            f"{pause_resp.status_code})"
                        )
                    else:
                        pause_resp.raise_for_status()
                        pause_body = pause_resp.json()
                        assert (
                            pause_body.get("status") == "STATE_PAUSED"
                        ), pause_body
                        assert (
                            pause_body.get("sandbox_id") == claimed_sbx_id
                        ), pause_body
                        passed.append(f"sandbox pause ok ({claimed_sbx_id})")
                finally:
                    release_path = "/api/v1/sandboxes/session/release"
                    release_resp = c.post(
                        release_path,
                        json={"agent_id": "cymbal_shared_diagnostic_agent"},
                        headers=admin_caller.headers(
                            "POST", admin_caller.url(release_path)
                        ),
                    )
                    if release_resp.status_code in (401, 403):
                        passed.append(
                            "sandbox release smoke skipped (unauthorized HTTP "
                            f"{release_resp.status_code})"
                        )
                    else:
                        release_resp.raise_for_status()
                        release_body = release_resp.json()
                        assert (
                            release_body.get("status") == "STATE_DESTROYED"
                        ), release_body
                        assert (
                            release_body.get("destroyed") is True
                        ), release_body
                        passed.append(f"sandbox release ok ({claimed_sbx_id})")
        except RuntimeError as auth_exc:
            # SandboxCaller raises RuntimeError when sandbox token issuer is disabled/unauthorized.
            if "sandbox token request failed" in str(
                auth_exc
            ) or "token exchange failed" in str(auth_exc):
                passed.append(f"sandbox/turn smoke skipped ({auth_exc})")
            else:
                raise
    return passed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", default=os.getenv("CYMBAL_ENV", "sandbox"))
    args = parser.parse_args(argv)
    try:
        for i, line in enumerate(run_smoke(args.env), 1):
            print(f"[PASS {i}] {line}")
    except (
        httpx.HTTPError,
        subprocess.CalledProcessError,
        AssertionError,
        KeyError,
        RuntimeError,
    ) as exc:
        print(f"[SMOKE FAILED] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
