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

# pylint: disable=import-outside-toplevel,inconsistent-quotes,line-too-long
# pylint: disable=missing-class-docstring,redefined-outer-name

"""Unit and mocked end-to-end tests for deploy, provisioning, and Cloud Run smoke scripts."""

from __future__ import annotations

import base64
import json
import os
import shutil
import stat
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from agents import context as agent_context
from agents import sandbox_execution
from app import main as gateway_main
from fastapi.testclient import TestClient
from scripts import (
    provision_gemini_agent_sandbox,
    sandbox_auth,
    verify_cloud_run_deployment,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _make_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _setup_fake_deploy_repo(
    tmp_path: Path,
    *,
    sandbox_tfvars: str,
    auto_tfvars: str | None = None,
    ready_statuses: Mapping[str, str] | None = None,
    fail_update_service: str = "",
    cur_id_type: str = "",
) -> tuple[Path, Path, dict[str, str]]:
    """Creates an isolated temp workspace with real `deploy.sh` and recording CLI stubs."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "terraform").mkdir()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log_file = tmp_path / "cli_calls.log"

    shutil.copy2(
        REPO_ROOT / "scripts" / "deploy.sh", tmp_path / "scripts" / "deploy.sh"
    )
    _make_executable(
        tmp_path / "scripts" / "config_check.py",
        "#!/usr/bin/env python3\nprint('{\"problems\": []}')\n",
    )
    _make_executable(
        tmp_path / "scripts" / "preflight_context_signing.py",
        "#!/usr/bin/env python3\nprint('preflight ok')\n",
    )
    _make_executable(
        tmp_path / "scripts" / "verify_cloud_run_deployment.py",
        "#!/usr/bin/env python3\nimport sys\nprint('smoke ok', sys.argv[1:])\n",
    )
    (tmp_path / "terraform" / "sandbox.tfvars").write_text(
        sandbox_tfvars, encoding="utf-8"
    )
    if auto_tfvars is not None:
        (tmp_path / "terraform" / "sandbox.auto.tfvars").write_text(
            auto_tfvars, encoding="utf-8"
        )

    # Fake uv: passes python -c / python <script> (with optional --frozen) through to real python3
    _make_executable(
        fake_bin / "uv",
        f"""#!/usr/bin/env python3
import subprocess, sys
with open({str(log_file)!r}, "a", encoding="utf-8") as fh:
    fh.write("uv " + " ".join(sys.argv[1:]) + "\\n")
args = sys.argv[1:]
if args[:1] == ["run"]:
    py_args = args[2:] if args[1:2] == ["--frozen"] else args[1:]
    if py_args[:1] == ["python"]:
        if len(py_args) >= 3 and py_args[1] == "-c":
            print("cymbal-multitenancy-example us-central1")
            sys.exit(0)
        res = subprocess.run([sys.executable, *py_args[1:]], check=False)
        sys.exit(res.returncode)
sys.exit(0)
""",
    )

    ready_map = dict(ready_statuses or {})
    _make_executable(
        fake_bin / "gcloud",
        f"""#!/usr/bin/env python3
import sys
args = sys.argv[1:]
with open({str(log_file)!r}, "a", encoding="utf-8") as fh:
    fh.write("gcloud " + " ".join(args) + "\\n")
ready_map = {ready_map!r}
fail_update = {fail_update_service!r}
cur_id_type = {cur_id_type!r}

if args[:3] == ["run", "services", "describe"]:
    svc = args[3]
    fmt = next((a for a in args if a.startswith("--format=")), "")
    if "containers[0].image" in fmt:
        print("us-central1-docker.pkg.dev/cymbal-multitenancy-example/cloud-run-source-deploy/cymbal-pooled-gateway:v1")
    elif "status.conditions[0].status" in fmt:
        if svc in ready_map:
            print(ready_map[svc])
    sys.exit(0)
if args[:4] == ["alpha", "run", "services", "describe"]:
    print(cur_id_type)
    sys.exit(0)
if args[:4] == ["alpha", "run", "services", "update"]:
    svc = args[4]
    if fail_update and svc == fail_update:
        sys.stderr.write(f"simulated update failure for {{svc}}\\n")
        sys.exit(1)
    sys.exit(0)
if args[:2] == ["projects", "describe"]:
    print("123456789012")
    sys.exit(0)
sys.exit(0)
""",
    )

    _make_executable(
        fake_bin / "terraform",
        f"""#!/usr/bin/env python3
import sys
args = sys.argv[1:]
with open({str(log_file)!r}, "a", encoding="utf-8") as fh:
    fh.write("terraform " + " ".join(args) + "\\n")
# Simulate agent_runtime not yet in state so import + apply both execute:
if "state" in args and "show" in args:
    sys.exit(1)
sys.exit(0)
""",
    )

    clean_env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("AGENT_SANDBOX_", "TF_VAR_"))
    }
    clean_env["PATH"] = f"{fake_bin}:{clean_env.get('PATH', '')}"
    return tmp_path / "scripts" / "deploy.sh", log_file, clean_env


def test_deploy_sh_syntax_and_cli_validation() -> None:
    """`scripts/deploy.sh` passes `bash -n` and rejects missing env or unknown CLI options."""
    syntax = subprocess.run(
        ["bash", "-n", str(REPO_ROOT / "scripts" / "deploy.sh")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert syntax.returncode == 0, syntax.stderr

    missing = subprocess.run(
        ["bash", str(REPO_ROOT / "scripts" / "deploy.sh")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert missing.returncode != 0
    assert "Usage:" in missing.stdout + missing.stderr

    unknown = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "scripts" / "deploy.sh"),
            "sandbox",
            "--bogus-flag",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert unknown.returncode != 0
    assert "Unknown option" in unknown.stdout + unknown.stderr


def test_deploy_sh_resolves_auto_tfvars_passes_sandbox_tf_vars_and_respects_live_mode(
    tmp_path: Path,
) -> None:
    """Proves `_resolve_sandbox_var` reads `*.auto.tfvars`, shell AGENT_SANDBOX_* passes `-var`, and
    `enable_live_mode` controls `CYMBAL_LIVE_GCP`.
    """
    script_path, log_file, env = _setup_fake_deploy_repo(
        tmp_path,
        sandbox_tfvars=(
            "enable_live_mode = false\nenable_agent_runtimes = true\n"
        ),
        auto_tfvars=(
            "agent_sandbox_reasoning_engine_name = "
            '"projects/p/locations/us-central1/reasoningEngines/auto-99"\n'
            'agent_sandbox_code_template = "auto-code-tpl"\n'
        ),
        ready_statuses={
            "cymbal-credential-broker": "True",
            "cymbal-agent-shared": "True",
            "cymbal-agent-finvault-alpha": "True",
        },
        cur_id_type="",  # triggers bootstrap deploy
    )
    env["AGENT_SANDBOX_SHELL_TEMPLATE"] = "shell-override-tpl"

    proc = subprocess.run(
        ["bash", str(script_path), "sandbox", "--auto-approve"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    calls = log_file.read_text(encoding="utf-8").splitlines()

    # Bootstrap respects `enable_live_mode = false` -> `CYMBAL_LIVE_GCP=0` and propagates resolved
    # Gemini vars:
    bootstrap_deploys = [
        c for c in calls if c.startswith("gcloud alpha run deploy ")
    ]
    assert len(bootstrap_deploys) == 2
    for dep in bootstrap_deploys:
        assert "CYMBAL_LIVE_GCP=0" in dep
        assert "CYMBAL_LIVE_GCP=1" not in dep
        assert (
            "AGENT_SANDBOX_REASONING_ENGINE_NAME=projects/p/locations/us-central1/reasoningEngines/auto-99"
            in dep
        )
        assert "AGENT_SANDBOX_CODE_TEMPLATE=auto-code-tpl" in dep
        assert "AGENT_SANDBOX_SHELL_TEMPLATE=shell-override-tpl" in dep

    # Shell env override is passed as `-var=geap_...` to `terraform apply` so gateway matches
    # runtimes:
    tf_applies = [
        c
        for c in calls
        if c.startswith("terraform ") and " apply " in c and "-target=" not in c
    ]
    assert len(tf_applies) == 1
    assert "-auto-approve" in tf_applies[0]
    assert (
        "-var=agent_sandbox_shell_template=shell-override-tpl" in tf_applies[0]
    )

    # Active disaggregated service updates pass `--update-env-vars` for agent runtimes only (never
    # broker):
    updates = [
        c for c in calls if c.startswith("gcloud alpha run services update ")
    ]
    broker_updates = [c for c in updates if "cymbal-credential-broker" in c]
    agent_updates = [c for c in updates if "cymbal-agent-" in c]
    assert broker_updates
    assert all("AGENT_SANDBOX_" not in b for b in broker_updates)
    assert agent_updates
    assert all(
        "AGENT_SANDBOX_SHELL_TEMPLATE=shell-override-tpl" in a
        for a in agent_updates
    )


def test_deploy_sh_live_mode_true_empty_sandbox_removal_and_skip_flags(
    tmp_path: Path,
) -> None:
    """Verifies `enable_live_mode=true`, `--remove-env-vars` when AGENT_SANDBOX_* empty, and `--skip-*`
    flags.
    """
    script_path, log_file, env = _setup_fake_deploy_repo(
        tmp_path,
        sandbox_tfvars="enable_live_mode = true\nenable_agent_runtimes = true\n",
        auto_tfvars=None,
        ready_statuses={"cymbal-agent-shared": "True"},
        cur_id_type="",
    )
    proc = subprocess.run(
        ["bash", str(script_path), "sandbox", "--skip-image", "--skip-smoke"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    calls = log_file.read_text(encoding="utf-8").splitlines()
    bootstrap_deploys = [
        c for c in calls if c.startswith("gcloud alpha run deploy ")
    ]
    assert bootstrap_deploys
    assert all("CYMBAL_LIVE_GCP=1" in d for d in bootstrap_deploys)
    updates = [
        c
        for c in calls
        if c.startswith("gcloud alpha run services update cymbal-agent-shared")
    ]
    assert updates
    assert (
        "--remove-env-vars=AGENT_SANDBOX_REASONING_ENGINE_NAME,AGENT_SANDBOX_CODE_TEMPLATE,AGENT_SANDBOX_SHELL_TEMPLATE"
        in updates[0]
    )
    assert not any("verify_cloud_run_deployment.py" in c for c in calls)


def test_deploy_sh_does_not_swallow_active_service_update_failures(
    tmp_path: Path,
) -> None:
    """Proves active `gcloud alpha run services update` failure aborts `deploy.sh` instead of `||
    true`.
    """
    script_path, _, env = _setup_fake_deploy_repo(
        tmp_path,
        sandbox_tfvars="enable_live_mode = false\nenable_agent_runtimes = false\n",
        ready_statuses={"cymbal-agent-shared": "True"},
        fail_update_service="cymbal-agent-shared",
        cur_id_type="agent-identity",
    )
    proc = subprocess.run(
        ["bash", str(script_path), "sandbox", "--auto-approve"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0


def test_deploy_sh_deletes_tainted_service_before_active_updates(
    tmp_path: Path,
) -> None:
    """Services in `Ready=False` state are deleted cleanly before active `services update` runs."""
    script_path, log_file, env = _setup_fake_deploy_repo(
        tmp_path,
        sandbox_tfvars="enable_live_mode = false\nenable_agent_runtimes = false\n",
        ready_statuses={
            "cymbal-credential-broker": "False",
            "cymbal-agent-shared": "True",
        },
        cur_id_type="agent-identity",
    )
    proc = subprocess.run(
        ["bash", str(script_path), "sandbox", "--auto-approve"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    calls = log_file.read_text(encoding="utf-8").splitlines()
    delete_idx = next(
        i
        for i, c in enumerate(calls)
        if "gcloud run services delete cymbal-credential-broker" in c
    )
    update_idx = next(
        i
        for i, c in enumerate(calls)
        if "gcloud alpha run services update cymbal-agent-shared" in c
    )
    assert delete_idx < update_idx


_REAL_HTTPX_CLIENT = httpx.Client


def _install_testclient_httpx_mock(
    monkeypatch: pytest.MonkeyPatch,
    *,
    overrides: (
        Mapping[tuple[str, str], tuple[int, dict[str, Any]]] | None
    ) = None,
    raw_overrides: (
        Mapping[tuple[str, str], tuple[int, dict[str, str], bytes]] | None
    ) = None,
    auth_only_overrides: bool = False,
) -> None:
    """Routes `verify_cloud_run_deployment` + `SandboxCaller` HTTP calls to `gateway_main.app`."""
    tc = TestClient(gateway_main.app, base_url="https://gateway.example")
    override_map = dict(overrides or {})
    raw_override_map = dict(raw_overrides or {})

    class _Transport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            path = request.url.path
            key = (request.method.upper(), path)
            if key in raw_override_map:
                status, resp_headers, content = raw_override_map[key]
                return httpx.Response(
                    status_code=status, headers=resp_headers, content=content
                )
            if key in override_map and (
                not auth_only_overrides or "authorization" in request.headers
            ):
                status, payload = override_map[key]
                return httpx.Response(status_code=status, json=payload)
            hdrs = {
                k: v for k, v in request.headers.items() if k.lower() != "host"
            }
            resp = tc.request(
                request.method,
                str(request.url.raw_path.decode("ascii")),
                content=request.content,
                headers=hdrs,
            )
            return httpx.Response(
                status_code=resp.status_code,
                headers=dict(resp.headers),
                content=resp.content,
            )

    transport = _Transport()
    real_client_cls = _REAL_HTTPX_CLIENT

    def fake_client(
        *,
        base_url: str = "",
        headers: Mapping[str, str] | None = None,
        timeout: float = 60.0,
    ) -> httpx.Client:
        return real_client_cls(
            base_url=base_url,
            headers=headers,
            timeout=timeout,
            transport=transport,
        )

    def fake_post(
        url: str,
        *,
        json: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float = 30.0,
    ) -> httpx.Response:
        with real_client_cls(transport=transport, timeout=timeout) as c:
            return c.post(url, json=json, headers=headers)

    monkeypatch.setattr(
        verify_cloud_run_deployment.httpx, "Client", fake_client
    )
    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setenv("CLOUD_RUN_URL", "https://gateway.example")
    monkeypatch.setenv("CLOUD_RUN_ID_TOKEN", "fake-cloud-run-id-token")
    monkeypatch.setattr(
        sandbox_auth, "SandboxCaller", sandbox_auth.SandboxCaller
    )


def test_verify_cloud_run_deployment_cli_paths(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exercises sandbox pass, unauthorized 403 skip, non-sandbox 404 skip, and 500 failure."""
    gateway_main.TOKEN_BULKHEAD.evict_tenant("tenant-finvault-alpha")
    gateway_main.SANDBOX_MANAGER.evict_tenant("tenant-finvault-alpha")

    # 1. Full sandbox pass against real FastAPI gateway via MockTransport
    _install_testclient_httpx_mock(monkeypatch)
    assert verify_cloud_run_deployment.main(["--env", "sandbox"]) == 0
    out = capsys.readouterr().out
    assert "invoke-agent turn ok" in out
    assert "sandbox pause ok" in out
    assert "sandbox release ok" in out

    # 2. Unauthorized (403) on sandbox endpoints skips cleanly without failing
    _install_testclient_httpx_mock(
        monkeypatch,
        overrides={
            ("POST", "/api/v1/invoke-agent"): (
                403,
                {"detail": {"error": "E_SANDBOX_SCOPE_DENIED"}},
            )
        },
        auth_only_overrides=True,
    )
    passed_403 = verify_cloud_run_deployment.run_smoke("sandbox")
    assert any("skipped (unauthorized HTTP 403)" in line for line in passed_403)

    # 3. Non-sandbox (`customer.example`) asserts 404 on sandbox-only routes & skips auth sandbox
    # smoke
    _install_testclient_httpx_mock(
        monkeypatch,
        overrides={
            ("GET", "/api/v1/health"): (
                200,
                {
                    "status": "ok",
                    "environment": "customer.example",
                    "tenants": 1,
                },
            ),
            ("GET", "/.well-known/ai-catalog.json"): (
                401,
                {"detail": "unauthorized"},
            ),
            ("POST", "/api/v1/invoke-agent"): (401, {"detail": "unauthorized"}),
            ("POST", "/api/v1/sandboxes/session/pause"): (
                401,
                {"detail": "unauthorized"},
            ),
            ("POST", "/api/v1/breach-matrix-10"): (
                404,
                {"detail": "Not found"},
            ),
            ("POST", "/api/v1/sandbox/token"): (404, {"detail": "Not found"}),
        },
    )
    passed_non_sbx = verify_cloud_run_deployment.run_smoke("customer.example")
    assert "sandbox-only endpoints absent (404)" in passed_non_sbx
    assert any("skipped" in line for line in passed_non_sbx)

    # 4. Unexpected 500 on `/api/v1/invoke-agent` fails non-zero cleanly
    _install_testclient_httpx_mock(
        monkeypatch,
        overrides={
            ("POST", "/api/v1/invoke-agent"): (
                500,
                {"detail": "internal error"},
            )
        },
        auth_only_overrides=True,
    )
    monkeypatch.setattr(
        "sys.argv", ["verify_cloud_run_deployment.py", "--env", "sandbox"]
    )
    assert verify_cloud_run_deployment.main() == 1
    assert "[SMOKE FAILED]" in capsys.readouterr().err


def test_verify_cloud_run_deployment_iap_redirect_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct IAP `302` to `iap.googleapis.com` verifies Ready=True and 0 public IAM; non-IAP
    redirects or public IAM bindings fail closed.
    """
    iap_loc = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        "redirect_uri=https://iap.googleapis.com/v1/oauth/clientIds/abc:handleRedirect"
    )
    _install_testclient_httpx_mock(
        monkeypatch,
        raw_overrides={
            ("GET", "/api/v1/health"): (302, {"Location": iap_loc}, b""),
            ("GET", "/.well-known/ai-catalog.json"): (
                302,
                {"Location": iap_loc},
                b"",
            ),
            ("POST", "/api/v1/invoke-agent"): (302, {"Location": iap_loc}, b""),
        },
    )
    public_iam: dict[str, list[str]] = {"cymbal-pooled-gateway": []}

    def _fake_gcloud(*args: str) -> str:
        cmd = list(args)
        if cmd[:3] == ["run", "services", "describe"]:
            svc = cmd[3]
            if svc not in ("cymbal-pooled-gateway", "cymbal-credential-broker"):
                raise subprocess.CalledProcessError(1, cmd)
            return json.dumps(
                {
                    "status": {
                        "conditions": [{"type": "Ready", "status": "True"}]
                    },
                    "metadata": {
                        "annotations": {
                            "run.googleapis.com/iap-enabled": "true"
                        }
                    },
                }
            )
        if cmd[:3] == ["run", "services", "get-iam-policy"]:
            svc = cmd[3]
            members = public_iam.get(svc) or [
                "serviceAccount:service-123@gcp-sa-iap.iam.gserviceaccount.com"
            ]
            return json.dumps(
                {
                    "bindings": [
                        {"role": "roles/run.invoker", "members": members}
                    ]
                }
            )
        raise AssertionError(f"unexpected gcloud call: {cmd}")

    monkeypatch.setattr(verify_cloud_run_deployment, "_gcloud", _fake_gcloud)
    passed = verify_cloud_run_deployment.run_smoke("customer.example")
    assert any("gateway Ready=True" in line for line in passed)
    assert any(
        "Cloud Run Direct IAP perimeter active" in line for line in passed
    )
    assert any("cymbal-credential-broker" in line for line in passed)

    # Public IAM fails closed:
    public_iam["cymbal-pooled-gateway"] = ["allUsers"]
    with pytest.raises(AssertionError, match="public IAM members"):
        verify_cloud_run_deployment.run_smoke("customer.example")

    # Non-IAP redirect still fails instead of being treated as IAP:
    _install_testclient_httpx_mock(
        monkeypatch,
        raw_overrides={
            ("GET", "/api/v1/health"): (
                302,
                {"Location": "https://evil.example/login"},
                b"",
            ),
        },
    )
    assert verify_cloud_run_deployment.main(["--env", "customer.example"]) == 1


@dataclass
class _FakeResponse:
    status_code: int
    payload: dict[str, Any]

    @property
    def content(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def json(self) -> dict[str, Any]:
        return dict(self.payload)


def test_provision_live_with_verify_manager_exercises_3chunk_bash_and_pause_resume(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Mocks `agentplatform.Client` + HTTP to test `--live --use-gcloud-auth --verify-manager`
    end-to-end.
    """
    sdk_calls: list[tuple[str, Any]] = []
    http_calls: list[tuple[str, str, dict[str, Any] | None]] = []

    class _FakeSandboxes:
        def create(
            self, *, name: str, spec: dict[str, Any], config: Any
        ) -> Any:
            del config
            is_shell = "shell_environment" in spec
            sdk_calls.append(("create", "shell" if is_shell else "python"))
            sbx_id = "sdk-shell-1" if is_shell else "sdk-py-1"
            return SimpleNamespace(
                response=SimpleNamespace(
                    name=f"{name}/sandboxEnvironments/{sbx_id}"
                )
            )

        def execute_code(self, *, name: str, input_data: dict[str, Any]) -> Any:
            del input_data
            sdk_calls.append(("execute_code", name))
            chunk = SimpleNamespace(
                data=b'{"kernel_release": "4.19.0-gvisor", "has_adc": false}'
            )
            return SimpleNamespace(outputs=[chunk])

        def execute_bash(self, *, name: str, command: str) -> dict[str, Any]:
            sdk_calls.append(("execute_bash", name, command))
            return {
                "stdout": "cymbal-shell-ok\n",
                "stderr": "",
                "returncode": 0,
            }

        def pause(self, *, name: str, config: Any = None) -> Any:
            del config
            sdk_calls.append(("pause", name))
            return {"done": True}

        def resume(self, *, name: str, config: Any = None) -> Any:
            del config
            sdk_calls.append(("resume", name))
            return {"done": True}

        def delete(self, *, name: str) -> Any:
            sdk_calls.append(("delete", name))
            return {"done": True}

    class _FakeRuntimes:
        def create(self) -> Any:
            sdk_calls.append(("runtimes.create", None))

            class _R:
                name = "projects/acme-prod/locations/us-central1/reasoningEngines/re-live-1"

            return _R()

    class _FakeApClient:
        def __init__(self, **kwargs: Any) -> None:
            sdk_calls.append(("Client", kwargs))
            self.runtimes = _FakeRuntimes()
            self.sandboxes = _FakeSandboxes()

    def _fake_subproc(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs

        class _Done:
            stdout = "fake-gcloud-oauth-token\n"

        return _Done()

    def _fake_httpx_request(
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        json: dict[str, Any] | None = None,
        timeout: float = 60.0,
    ) -> _FakeResponse:
        del headers, timeout
        http_calls.append((method, url, json))
        if method == "POST" and url.endswith("/sandboxEnvironmentTemplates"):
            return _FakeResponse(
                200,
                {
                    "done": True,
                    "response": {
                        "name": (
                            "projects/acme-prod/locations/us-central1/"
                            "reasoningEngines/re-live-1/sandboxEnvironmentTemplates/tpl-shell-1"
                        )
                    },
                },
            )
        if method == "POST" and url.endswith("/sandboxEnvironments"):
            is_shell = isinstance(json, Mapping) and "shellEnvironment" in dict(
                json.get("spec") or {}
            )
            sbx_id = "sbx-mgr-bash-1" if is_shell else "sbx-mgr-py-1"
            return _FakeResponse(
                200,
                {
                    "done": True,
                    "response": {
                        "name": (
                            "projects/acme-prod/locations/us-central1/reasoningEngines/"
                            "re-live-1/sandboxEnvironments/"
                            f"{sbx_id}"
                        )
                    },
                },
            )
        if method == "POST" and url.endswith("/:execute"):
            if "/sbx-mgr-bash-1" in url:
                inputs = (json or {}).get("inputs") or []
                cmd = json_loads_b64(inputs[2]["data"])["command"]
                out = (
                    "user=appuser uid=1000 cloud= ssn=123-45-6789\n"
                    if "env |" in cmd
                    else "cymbal-bash-state\n"
                )
                b64 = base64.b64encode(
                    json_dumps({"returncode": 0, "stdout": out, "stderr": ""})
                ).decode("ascii")
            else:
                inputs = (json or {}).get("inputs") or []
                code = json_loads_b64(inputs[0]["data"])["code"]
                if (
                    "cymbal_session_state" in code
                    and "readonly_input.json" in code
                ):
                    out_obj = {
                        "kernel_release": "4.19.0-gvisor",
                        "public_internet_blocked": True,
                        "cloud_env_keys": [],
                        "readonly_incident_count": 2,
                        "dlp_probe": "123-45-6789",
                    }
                elif "reused_state" in code:
                    out_obj = {
                        "reused_state": {"turn": 1, "incidents": 2},
                        "turn": 2,
                    }
                else:
                    out_obj = {"resumed": True}
                b64 = base64.b64encode(
                    json_dumps(
                        {
                            "exit_status_int": 0,
                            "msg_out": json_dumps_str(out_obj),
                            "msg_err": "",
                        }
                    )
                ).decode("ascii")
            return _FakeResponse(
                200,
                {"outputs": [{"mimeType": "application/json", "data": b64}]},
            )
        return _FakeResponse(200, {"done": True})

    def json_dumps(obj: Any) -> bytes:
        return json.dumps(obj).encode("utf-8")

    def json_dumps_str(obj: Any) -> str:
        return json.dumps(obj)

    def json_loads_b64(val: str) -> dict[str, Any]:
        return dict(json.loads(base64.b64decode(val).decode("utf-8")))

    monkeypatch.setattr(
        provision_gemini_agent_sandbox.agentplatform, "Client", _FakeApClient
    )
    monkeypatch.setattr(
        provision_gemini_agent_sandbox.subprocess, "run", _fake_subproc
    )
    monkeypatch.setattr(sandbox_execution.httpx, "request", _fake_httpx_request)

    rc = provision_gemini_agent_sandbox.main(
        [
            "--live",
            "--use-gcloud-auth",
            "--verify-manager",
            "--project-id",
            "acme-prod",
            "--location",
            "us-central1",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["mode"] == "LIVE_PROVISIONED_AND_VERIFIED"
    assert out["shell_pause_resume_verified"] is True
    mgr_res = out["manager_and_mcp_verification"]
    assert mgr_res["builtin_code_exec_pause_probe"] == "PAUSED_AND_RESUMED"
    assert mgr_res["bash_pause_receipt"]["status"] == "STATE_PAUSED"
    assert (
        mgr_res["bash_resume_stateful_reuse"]["reused_session_sandbox"] is True
    )
    assert mgr_res["reattach_after_destroy_blocked"] is True
    assert mgr_res["bash_reattach_after_destroy_blocked"] is True

    # Verify 3-chunk bash proxy payload was sent in manager verification too:
    bash_execs = [
        body
        for m, u, body in http_calls
        if m == "POST" and u.endswith("/sbx-mgr-bash-1/:execute")
    ]
    assert len(bash_execs) == 2
    chunks = bash_execs[0]["inputs"]  # type: ignore[index]
    assert [c["mimeType"] for c in chunks] == [
        "application/x.sandbox-request-uri",
        "application/x.sandbox-request-port",
        "application/json",
    ]
    assert (
        "pause",
        "projects/acme-prod/locations/us-central1/reasoningEngines/re-live-1/sandboxEnvironments/sdk-shell-1",
    ) in sdk_calls
    assert (
        "resume",
        "projects/acme-prod/locations/us-central1/reasoningEngines/re-live-1/sandboxEnvironments/sdk-shell-1",
    ) in sdk_calls


def test_provision_does_not_swallow_unexpected_pause_or_bash_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unexpected HTTP 500 on `pause` or non-zero `execute_bash` must raise, not get swallowed."""
    deleted_resources: list[str] = []

    def _failing_pause_httpx(
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        json: dict[str, Any] | None = None,
        timeout: float = 60.0,
    ) -> _FakeResponse:
        del headers, timeout
        if method == "DELETE":
            deleted_resources.append(url)
            return _FakeResponse(200, {"done": True})
        if method == "POST" and url.endswith("/:pause"):
            return _FakeResponse(503, {"error": "internal outage"})
        if method == "POST" and url.endswith("/sandboxEnvironments"):
            return _FakeResponse(
                200,
                {
                    "done": True,
                    "response": {
                        "name": (
                            "projects/acme-prod/locations/us-central1/reasoningEngines/re-1/"
                            "sandboxEnvironments/sbx-py-err"
                        )
                    },
                },
            )
        if method == "POST" and url.endswith("/:execute"):
            inputs = (json or {}).get("inputs") or []
            code = globals()["json"].loads(
                base64.b64decode(inputs[0]["data"]).decode("utf-8")
            )["code"]
            out_obj = (
                {
                    "kernel_release": "4.19.0-gvisor",
                    "public_internet_blocked": True,
                    "cloud_env_keys": [],
                    "readonly_incident_count": 2,
                    "dlp_probe": "123-45-6789",
                }
                if "readonly_input.json" in code
                else {"reused_state": {"turn": 1, "incidents": 2}, "turn": 2}
            )
            b64 = base64.b64encode(
                globals()["json"]
                .dumps(
                    {
                        "exit_status_int": 0,
                        "msg_out": globals()["json"].dumps(out_obj),
                        "msg_err": "",
                    }
                )
                .encode("utf-8")
            ).decode("ascii")
            return _FakeResponse(
                200,
                {"outputs": [{"mimeType": "application/json", "data": b64}]},
            )
        return _FakeResponse(200, {"done": True})

    monkeypatch.setattr(
        sandbox_execution.httpx, "request", _failing_pause_httpx
    )
    monkeypatch.setattr(
        sandbox_execution,
        "_control_plane_adc_headers",
        lambda project_id: {
            "Authorization": "Bearer fake-adc",
            "X-Goog-User-Project": project_id,
        },
    )
    with pytest.raises(
        sandbox_execution.SandboxUnavailableError, match="HTTP 503"
    ):
        provision_gemini_agent_sandbox.run_live_manager_verification(
            project_id="acme-prod",
            location="us-central1",
            engine_resource_name="projects/acme-prod/locations/us-central1/reasoningEngines/re-1",
            ttl_seconds=300,
            use_gcloud_auth=False,
        )
    # `finally` cleaned up the claimed sandbox when verification aborted:
    assert any("sbx-py-err" in url for url in deleted_resources)
    assert agent_context.TENANT_DIRECTORY  # directory untouched


def test_provision_smoke_raises_on_nonzero_bash_exit_and_cleans_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`provision_and_smoke_test_live` fails loudly on bad shell exit while still deleting
    sandbox.
    """
    deleted: list[str] = []

    class _BadBashSandboxes:
        def create(
            self, *, name: str, spec: dict[str, Any], config: Any
        ) -> Any:
            del config
            sbx = "sdk-sh-fail" if "shell_environment" in spec else "sdk-py-ok"
            return SimpleNamespace(
                response=SimpleNamespace(
                    name=f"{name}/sandboxEnvironments/{sbx}"
                )
            )

        def execute_code(self, *, name: str, input_data: dict[str, Any]) -> Any:
            del name, input_data
            return SimpleNamespace(
                outputs=[SimpleNamespace(data=b'{"ok": true}')]
            )

        def execute_bash(self, *, name: str, command: str) -> dict[str, Any]:
            del name, command
            return {
                "stdout": "",
                "stderr": "permission denied",
                "returncode": 1,
            }

        def delete(self, *, name: str) -> dict[str, Any]:
            deleted.append(name)
            return {"done": True}

    class _FakeApClient:
        def __init__(self, **_kwargs: Any) -> None:
            self.sandboxes = _BadBashSandboxes()

    monkeypatch.setattr(
        provision_gemini_agent_sandbox.agentplatform, "Client", _FakeApClient
    )
    with pytest.raises(
        RuntimeError, match="Unexpected shell execute_bash output"
    ):
        provision_gemini_agent_sandbox.provision_and_smoke_test_live(
            project_id="acme-prod",
            location="us-central1",
            existing_engine_name="projects/acme-prod/locations/us-central1/reasoningEngines/re-1",
            ttl_seconds=300,
        )
    assert any("sdk-py-ok" in d for d in deleted)
    assert any("sdk-sh-fail" in d for d in deleted)


def test_deploy_sh_bootstraps_tfstate_and_image_on_fresh_project(
    tmp_path: Path,
) -> None:
    """When `gs://*-tfstate` and `cymbal-pooled-gateway` are absent, `deploy.sh` creates the
    state bucket, submits a bootstrap image, and passes `-var=gateway_container_image`.
    """
    script_path, log_file, env = _setup_fake_deploy_repo(
        tmp_path,
        sandbox_tfvars="enable_live_mode = true\nenable_agent_runtimes = true\n",
        cur_id_type="",
    )
    gcloud_stub = tmp_path / "bin" / "gcloud"
    gcloud_stub.write_text(
        f"""#!/usr/bin/env python3
import sys
args = sys.argv[1:]
with open({str(log_file)!r}, "a", encoding="utf-8") as fh:
    fh.write("gcloud " + " ".join(args) + "\\n")
if args[:3] == ["storage", "buckets", "describe"]:
    sys.exit(1)
if args[:3] == ["run", "services", "describe"] and args[3] == "cymbal-pooled-gateway":
    sys.exit(1)
if args[:2] == ["projects", "describe"]:
    print("9988776655")
    sys.exit(0)
sys.exit(0)
""",
        encoding="utf-8",
    )
    proc = subprocess.run(
        ["bash", str(script_path), "sandbox", "--auto-approve", "--skip-smoke"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    calls = log_file.read_text(encoding="utf-8").splitlines()
    assert any(
        "gcloud storage buckets create gs://cymbal-multitenancy-example-tfstate"
        in c
        for c in calls
    )
    assert any("gcloud builds submit ." in c for c in calls)
    assert any(
        "-var=gateway_container_image=us-central1-docker.pkg.dev/cymbal-multitenancy-example/"
        "cloud-run-source-deploy/cymbal-pooled-gateway:bootstrap" in c
        for c in calls
    )


def test_deploy_sh_syncs_redis_tls_secret_version_from_gateway_env(
    tmp_path: Path,
) -> None:
    """When gateway has `REDIS_TLS_SECRET_VERSION`, `deploy.sh` propagates it to agent runtimes."""
    script_path, log_file, env = _setup_fake_deploy_repo(
        tmp_path,
        sandbox_tfvars="enable_live_mode = true\nenable_agent_runtimes = true\n",
        cur_id_type="agent-identity",
    )
    tls_ver = "projects/p/secrets/cymbal-redis-tls-auth-prod/versions/1"
    gw_payload = json.dumps(
        {
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "env": [
                                    {
                                        "name": "REDIS_TLS_SECRET_VERSION",
                                        "value": tls_ver,
                                    }
                                ]
                            }
                        ]
                    }
                }
            }
        }
    )
    gcloud_stub = tmp_path / "bin" / "gcloud"
    orig = gcloud_stub.read_text(encoding="utf-8")
    patched = orig.replace(
        '    elif "status.conditions[0].status" in fmt:\n',
        f"""    elif "containers[0].env" in fmt and svc == "cymbal-pooled-gateway":
        print({gw_payload!r})
    elif "status.conditions[0].status" in fmt:
""",
    )
    gcloud_stub.write_text(patched, encoding="utf-8")
    proc = subprocess.run(
        [
            "bash",
            str(script_path),
            "sandbox",
            "--auto-approve",
            "--skip-image",
            "--skip-smoke",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    calls = log_file.read_text(encoding="utf-8").splitlines()
    tls_updates = [
        c
        for c in calls
        if c.startswith("gcloud alpha run services update cymbal-agent-")
        and f"REDIS_TLS_SECRET_VERSION={tls_ver}" in c
    ]
    assert len(tls_updates) == 2
    assert any("cymbal-agent-shared " in c for c in tls_updates)
    assert any("cymbal-agent-finvault-alpha " in c for c in tls_updates)
    assert all(
        "REDIS_URL" in c and "--remove-env-vars=" in c for c in tls_updates
    )


@pytest.mark.parametrize(
    ("public_ip_tfvars", "expect_private_ip"),
    [
        (
            "",
            True,
        ),  # variable absent: Terraform default is false (private address only)
        ("alloydb_enable_public_ip = false\n", True),
        ("alloydb_enable_public_ip = true\n", False),
    ],
)
def test_deploy_sh_pre_bootstraps_alloydb_and_cleans_tainted_gateway(
    tmp_path: Path, public_ip_tfvars: str, expect_private_ip: bool
) -> None:
    """When AlloyDB primary is enabled on a fresh project, `deploy.sh` removes an unimported
    `Ready=False` gateway and runs `bootstrap_alloydb_rls.py` BEFORE full `terraform apply`.
    The Auth Proxy targets the public IP only when the operator set `alloydb_enable_public_ip`.
    """
    script_path, log_file, env = _setup_fake_deploy_repo(
        tmp_path,
        sandbox_tfvars=(
            "enable_live_mode = true\n"
            "enable_alloydb_cluster = true\n"
            "enable_alloydb_primary_instance = true\n" + public_ip_tfvars
        ),
        ready_statuses={"cymbal-pooled-gateway": "False"},
    )
    inst_uri = "projects/p/locations/us-central1/clusters/cymbal-pooled-rls-prod/instances/i1"
    _make_executable(
        tmp_path / "scripts" / "bootstrap_alloydb_rls.py",
        f"""#!/usr/bin/env python3
import sys
with open({str(log_file)!r}, "a", encoding="utf-8") as fh:
    fh.write("bootstrap_alloydb_rls.py " + " ".join(sys.argv[1:]) + "\\n")
""",
    )
    _make_executable(
        tmp_path / "bin" / "alloydb-auth-proxy",
        "#!/usr/bin/env bash\nexit 0\n",
    )
    tf_stub = tmp_path / "bin" / "terraform"
    tf_stub.write_text(
        f"""#!/usr/bin/env python3
import sys
args = sys.argv[1:]
with open({str(log_file)!r}, "a", encoding="utf-8") as fh:
    fh.write("terraform " + " ".join(args) + "\\n")
if "state" in args and "show" in args:
    if any("pooled_rls_primary" in a for a in args):
        print('name = "{inst_uri}"')
        sys.exit(0)
    sys.exit(1)
sys.exit(0)
""",
        encoding="utf-8",
    )
    gcloud_stub = tmp_path / "bin" / "gcloud"
    orig_gcloud = gcloud_stub.read_text(encoding="utf-8")
    gcloud_stub.write_text(
        orig_gcloud.replace(
            'if args[:2] == ["projects", "describe"]:\n',
            """if args[:3] == ["config", "get-value", "account"]:
    print("ops-admin@example.com")
    sys.exit(0)
if args[:2] == ["projects", "describe"]:
""",
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            "bash",
            str(script_path),
            "sandbox",
            "--auto-approve",
            "--skip-image",
            "--skip-smoke",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    calls = log_file.read_text(encoding="utf-8").splitlines()
    gw_del_idx = next(
        i
        for i, c in enumerate(calls)
        if "gcloud run services delete cymbal-pooled-gateway" in c
    )
    target_idx = next(
        i
        for i, c in enumerate(calls)
        if "-target=module.platform_core.google_alloydb_instance.pooled_rls_primary"
        in c
    )
    pre_rls_idx = next(
        i
        for i, c in enumerate(calls)
        if c.startswith("bootstrap_alloydb_rls.py ")
    )
    full_apply_idx = next(
        i
        for i, c in enumerate(calls)
        if c.startswith("terraform ") and " apply " in c and "-target=" not in c
    )
    assert gw_del_idx < target_idx < pre_rls_idx < full_apply_idx
    assert f"--instance-uri {inst_uri}" in calls[pre_rls_idx]
    assert (
        "--grant-iam-user cymbal-pooled-runtime-sa@cymbal-multitenancy-example.iam"
        in calls[pre_rls_idx]
    )
    rls_calls = [c for c in calls if c.startswith("bootstrap_alloydb_rls.py ")]
    assert rls_calls
    assert all(
        ("--private-ip" in c.split()) is expect_private_ip for c in rls_calls
    )
    assert ("AlloyDB public IP is off" in proc.stdout) is expect_private_ip


def test_deploy_sh_cleans_terraform_tainted_gateway_service(
    tmp_path: Path,
) -> None:
    """When `cymbal-pooled-gateway` is both `Ready=False` and `(tainted)` in TF state,
    `deploy.sh` removes it from state and deletes the service before rebuilding.
    """
    script_path, log_file, env = _setup_fake_deploy_repo(
        tmp_path,
        sandbox_tfvars="enable_live_mode = false\n",
        ready_statuses={"cymbal-pooled-gateway": "False"},
    )
    tf_stub = tmp_path / "bin" / "terraform"
    tf_stub.write_text(
        f"""#!/usr/bin/env python3
import sys
args = sys.argv[1:]
with open({str(log_file)!r}, "a", encoding="utf-8") as fh:
    fh.write("terraform " + " ".join(args) + "\\n")
if "state" in args and "show" in args and any("cymbal_pooled_gateway" in a for a in args):
    print("# module.platform_core.google_cloud_run_v2_service.cymbal_pooled_gateway: (tainted)")
    sys.exit(0)
sys.exit(0)
""",
        encoding="utf-8",
    )
    proc = subprocess.run(
        ["bash", str(script_path), "sandbox", "--auto-approve", "--skip-smoke"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    calls = log_file.read_text(encoding="utf-8").splitlines()
    assert any(
        "terraform -chdir=terraform state rm "
        "module.platform_core.google_cloud_run_v2_service.cymbal_pooled_gateway"
        in c
        for c in calls
    )
    assert any(
        "gcloud run services delete cymbal-pooled-gateway" in c for c in calls
    )


@pytest.mark.parametrize("private_ip", [False, True])
def test_bootstrap_alloydb_rls_proxy_uses_public_ip_only_when_not_private(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, private_ip: bool
) -> None:
    """`--private-ip` drops the proxy's `--public-ip` flag (Terraform default: no public IP)."""
    from scripts import bootstrap_alloydb_rls

    argv_log = tmp_path / "proxy_argv.txt"
    recording_proxy = tmp_path / "alloydb-auth-proxy"
    recording_proxy.write_text(
        f'#!/usr/bin/env bash\necho "$@" > {argv_log}\nexit 1\n',
        encoding="utf-8",
    )
    recording_proxy.chmod(0o755)
    monkeypatch.setattr(
        bootstrap_alloydb_rls.shutil,
        "which",
        lambda _name: str(recording_proxy),
    )
    argv = [
        "bootstrap_alloydb_rls.py",
        "--instance-uri",
        "projects/p/locations/us-central1/clusters/c/instances/i",
        "--db-user",
        "ops-admin@example.com",
    ]
    if private_ip:
        argv.append("--private-ip")
    monkeypatch.setattr("sys.argv", argv)
    with pytest.raises(RuntimeError, match="alloydb-auth-proxy exited early"):
        bootstrap_alloydb_rls.main()
    proxy_args = argv_log.read_text(encoding="utf-8").split()
    assert ("--public-ip" in proxy_args) is (not private_ip)
    assert "--auto-iam-authn" in proxy_args


def test_bootstrap_alloydb_rls_fails_fast_when_proxy_exits_early(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`bootstrap_alloydb_rls.py` detects an early proxy crash before DB connect retries."""
    from scripts import bootstrap_alloydb_rls

    failing_proxy = tmp_path / "alloydb-auth-proxy"
    _make_executable(
        failing_proxy,
        "#!/usr/bin/env bash\necho 'simulated proxy crash' >&2\nexit 2\n",
    )
    monkeypatch.setattr(
        bootstrap_alloydb_rls.shutil, "which", lambda _name: str(failing_proxy)
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "bootstrap_alloydb_rls.py",
            "--instance-uri",
            "projects/p/locations/us-central1/clusters/c/instances/i",
            "--db-user",
            "admin@example.com",
            "--iam-auth",
        ],
    )
    with pytest.raises(RuntimeError, match="alloydb-auth-proxy exited early"):
        bootstrap_alloydb_rls.main()
