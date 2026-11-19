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

# pylint: disable=import-outside-toplevel,line-too-long,protected-access
# pylint: disable=redefined-outer-name,reimported,unused-argument

"""Deployment / runtime contract tests (deployment-path audit findings F2-F6).

- Layered config reproduces the tenants, validates strictly, and supports customer environments.
- No hard-coded project fallback; live mode fails closed on a placeholder project.
- One env-var contract shared by code and Terraform.
- One serving identity in Terraform, least-privilege roles, guardrails/RLS as native resources.
- Secret scripts never touch IAM; the runtime never provisions guardrails or issues RLS DDL.
- The Agent Engine recipe grants no project-wide data roles and captures no prompt content.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from agents import platform_config as pc
from agents.context import TENANT_DIRECTORY, SubscriptionTier
from agents.runtime_env import RUNTIME_ENV_CONTRACT
from pydantic import ValidationError

REPO = Path(__file__).resolve().parents[2]
TF = REPO / "terraform"
CORE = TF / "modules" / "platform_core"
TENANT_TF = TF / "modules" / "tenant" / "main.tf"

# The tenant directory exactly as it was hard-coded before config moved to config/.
_SANDBOX_PROJECT_ID = pc.load_platform_config("sandbox").gcp.project_id
_SANDBOX_PROJECT_NUMBER = str(
    pc.load_platform_config("sandbox").gcp.project_number or "123456789012"
)

LEGACY_SANDBOX_TENANTS = {
    "tenant-finvault-alpha": {
        "display_name": "FinVault Bank",
        "tier": SubscriptionTier.ENTERPRISE,
        "iss": "https://accounts.google.com",
        "org_unit": "regulated-banking-us",
        "thinking_budget": 8000,
        "rpm_limit": 120,
        "tpm_limit": 250_000,
        "max_turns_per_session": 12,
        "cmek_key_name": f"projects/{_SANDBOX_PROJECT_ID}/locations/us-central1/"
        "keyRings/cymbal-tenant-kr-prod/cryptoKeys/finvault-alpha-cmek",
        "authorized_scopes": (
            "2lo:cymbal.telemetry.read",
            "2lo:cymbal.runbooks.read",
            "2lo:cymbal.sandbox.execute",
            "3lo:google.drive.readonly",
            "3lo:google.calendar.events",
            "3lo:google.gmail.send",
            "3lo:jira.incidents.write",
            "agent:cymbal_shared_diagnostic_agent",
            "agent:finvault_regulatory_escalation_agent",
        ),
        "secret_ids": ("cymbal-finvault-jira-credentials",),
        "external_mcp_audiences": ("https://mcp.finvault.example/mcp",),
        "topology": {"pattern": "pool"},
    },
    "tenant-retailstream-beta": {
        "display_name": "RetailStream Corp",
        "tier": SubscriptionTier.STANDARD,
        "iss": "https://login.microsoftonline.com/retailstream-tenant-id/v2.0",
        "org_unit": "global-ecommerce-std",
        "thinking_budget": 4000,
        "rpm_limit": 30,
        "tpm_limit": 40_000,
        "max_turns_per_session": 5,
        "cmek_key_name": f"projects/{_SANDBOX_PROJECT_ID}/locations/us-central1/"
        "keyRings/cymbal-tenant-kr-prod/cryptoKeys/retailstream-beta-cmek",
        "authorized_scopes": (
            "2lo:cymbal.telemetry.read",
            "2lo:cymbal.runbooks.read",
            "2lo:cymbal.sandbox.execute",
            "3lo:microsoft.sharepoint.readonly",
            "3lo:servicenow.itom.write",
            "agent:cymbal_shared_diagnostic_agent",
        ),
        "secret_ids": (
            "cymbal-retailstream-servicenow-credentials",
            "cymbal-retailstream-entra-credentials",
        ),
        "external_mcp_audiences": (),
        "topology": {"pattern": "pool"},
    },
}


# ---------------------------------------------------------------------------------------------
# Layered config
# ---------------------------------------------------------------------------------------------


def test_sandbox_config_reproduces_legacy_tenant_directory_exactly() -> None:
    for tenant_id, expected in LEGACY_SANDBOX_TENANTS.items():
        assert TENANT_DIRECTORY[tenant_id] == expected


def test_customer_template_loads_with_minimal_tenant_file_and_its_own_project() -> (
    None
):
    cfg = pc.load_platform_config("customer.example")
    entries = cfg.tenant_directory_entries(project_id="acme-prod")
    acme = entries["tenant-acme-corp"]
    assert acme["thinking_budget"] == 4000  # inherited from base tier defaults
    assert (
        acme["authorized_scopes"] == cfg.default_scopes
    )  # inherited default scopes
    assert acme["cmek_key_name"].startswith("projects/acme-prod/")
    assert _SANDBOX_PROJECT_ID not in str(entries)


def _write_env(root: Path, tenants: dict[str, dict]) -> Path:
    (root / "environments").mkdir(parents=True)
    (root / "tenants" / "t").mkdir(parents=True)
    (root / "base.yaml").write_text((REPO / "config" / "base.yaml").read_text())
    (root / "environments" / "test.yaml").write_text(
        yaml.safe_dump(
            {
                "environment": "test",
                "data_classification": "synthetic",
                "tenants_dir": "tenants/t",
                "gcp": {"project_id": "p"},
            }
        )
    )
    for name, body in tenants.items():
        (root / "tenants" / "t" / f"{name}.yaml").write_text(
            yaml.safe_dump(body)
        )
    return root


def _tenant(tid: str, key: str, **extra: object) -> dict:
    return {
        "tenant_id": tid,
        "display_name": tid,
        "tier": "standard",
        "identity": {"issuer": "https://idp.example.com"},
        "cmek_key": key,
        **extra,
    }


def test_config_accepts_valid_custom_environment(tmp_path: Path) -> None:
    root = _write_env(tmp_path, {"tenant-one": _tenant("tenant-one", "k1")})
    cfg = pc.load_platform_config("test", root=root)
    assert [t.tenant_id for t in cfg.tenants] == ["tenant-one"]


@pytest.mark.parametrize(
    ("tenants", "error"),
    [
        (
            {"tenant-one": _tenant("tenant-one", "k1", unknown_field=1)},
            "Extra inputs",
        ),
        ({"tenant-one": _tenant("tenant-one", "k1", tier="platinum")}, "tier"),
        (
            {
                "tenant-one": {
                    **_tenant("tenant-one", "k1"),
                    "identity": {"issuer": "http://x"},
                }
            },
            "https",
        ),
        (
            {
                "tenant-a": _tenant("tenant-a", "k1"),
                "tenant-b": _tenant("tenant-b", "k1"),
            },
            "cmek_key shared",
        ),
        (
            {"tenant-one": _tenant("tenant-two", "k1")},
            "must match the file name",
        ),
        (
            {
                "tenant-one": {
                    k: v
                    for k, v in _tenant("tenant-one", "k1").items()
                    if k != "cmek_key"
                }
            },
            "cmek_key",
        ),
    ],
)
def test_config_rejects_invalid_tenants(
    tmp_path: Path, tenants: dict, error: str
) -> None:
    root = _write_env(tmp_path, tenants)
    with pytest.raises((ValidationError, ValueError), match=error):
        pc.load_platform_config("test", root=root)


def test_unknown_environment_is_an_error() -> None:
    with pytest.raises(FileNotFoundError, match="E_CONFIG_ENV_NOT_FOUND"):
        pc.load_platform_config("does-not-exist")


def test_declarative_gemini4_models_config_validates_defaults_and_allowlists() -> (
    None
):
    cfg = pc.load_platform_config("sandbox")
    assert cfg.models.default_shared_model == "gemini-4-hydrogen"
    assert cfg.models.default_executor_model == "gemini-4-hydrogen"
    assert cfg.models.default_frontier_model == "gemini-4-carbon"
    assert cfg.models.fallback_frontier_model == "gemini-4-argon"
    assert cfg.models.fallback_fast_model == "gemini-3.8-flash"
    assert cfg.models.eval_judge_model == "gemini-4-hydrogen"
    assert "gemini-4-hydrogen" in cfg.models.standard_allowed_models
    assert "gemini-4-carbon" in cfg.models.standard_allowed_models
    assert "gemini-4-argon" in cfg.models.enterprise_allowed_models
    assert "claude-3-7-sonnet@20250219" in cfg.models.enterprise_allowed_models

    with pytest.raises(ValidationError, match="standard_allowed_models"):
        pc.ModelSettings(
            default_shared_model="gemini-4-hydrogen",
            standard_allowed_models=("gemini-4-carbon",),
        )


# ---------------------------------------------------------------------------------------------
# Project resolution: no hard-coded fallback, fail closed in live mode
# ---------------------------------------------------------------------------------------------


@pytest.fixture
def customer_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CYMBAL_ENV", "customer.example")
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    pc._cached_platform_config.cache_clear()
    yield
    pc._cached_platform_config.cache_clear()


def test_env_var_project_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "acme-prod")
    assert pc.resolve_project_id() == "acme-prod"


def test_configured_project_number_maps_to_project_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    assert pc.resolve_project_id(_SANDBOX_PROJECT_NUMBER) == _SANDBOX_PROJECT_ID
    assert (
        pc.resolve_project_id("999999999999") == "999999999999"
    )  # not silently remapped


def test_live_mode_refuses_placeholder_project(
    customer_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CYMBAL_LIVE_GCP", "1")
    monkeypatch.delenv("CYMBAL_OFFLINE_CI", raising=False)
    with pytest.raises(RuntimeError, match="E_PROJECT_NOT_CONFIGURED"):
        pc.resolve_project_id()


def test_offline_mode_never_targets_the_sandbox_project_for_a_customer(
    customer_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CYMBAL_LIVE_GCP", raising=False)
    monkeypatch.delenv("RUN_LIVE_GCP_TESTS", raising=False)
    assert pc.resolve_project_id() != _SANDBOX_PROJECT_ID


def test_no_hard_coded_project_in_runtime_code() -> None:
    for path in [
        *(REPO / "agents").rglob("*.py"),
        *(REPO / "app").rglob("*.py"),
    ]:
        code = "\n".join(
            line
            for line in path.read_text().splitlines()
            if not line.lstrip().startswith(("#", '"""'))
        )
        assert f'"{_SANDBOX_PROJECT_ID}"' not in code, path.name
        assert _SANDBOX_PROJECT_NUMBER not in code, path.name


# ---------------------------------------------------------------------------------------------
# One env-var contract shared by code and Terraform
# ---------------------------------------------------------------------------------------------

_ENV_READ_RE = re.compile(
    r'(?:os\.(?:getenv|environ\.get|environ\.setdefault)|flag_enabled)\(\s*"([A-Z][A-Z0-9_]+)"',
    re.MULTILINE,
)
_ENV_CONST_RE = re.compile(
    r'^[A-Z0-9_]+_ENV\s*=\s*"([A-Z][A-Z0-9_]+)"', re.MULTILINE
)


def _env_vars_read_by_code() -> set[str]:
    names: set[str] = set()
    for pkg in (
        "agents",
        "app",
        "mcp_server",
        "runtime_service",
        "broker_service",
    ):
        for path in (REPO / pkg).rglob("*.py"):
            text = path.read_text()
            names |= set(_ENV_READ_RE.findall(text))
            names |= set(_ENV_CONST_RE.findall(text))
    return names


def _env_vars_set_by_terraform() -> set[str]:
    names: set[str] = set()
    for tf_path in (
        CORE / "iap_gateway.tf",
        CORE / "credential_broker.tf",
        TF / "modules" / "agent_runtime" / "main.tf",
    ):
        tf = tf_path.read_text()
        for match in re.finditer(
            r'dynamic\s+"env"\s*\{(.*?)\n\s*content\s*\{', tf, re.DOTALL
        ):
            names.update(
                re.findall(
                    r"(?:^|\{)\s*([A-Z][A-Z0-9_]+)\s*=",
                    match.group(1),
                    re.MULTILINE,
                )
            )
        names.update(
            re.findall(
                r'^\s*env\s*\{\s*name\s*=\s*"([A-Z][A-Z0-9_]+)"',
                tf,
                re.MULTILINE | re.DOTALL,
            )
        )
    return names


def test_every_env_var_the_code_reads_is_in_the_contract() -> None:
    missing = _env_vars_read_by_code() - set(RUNTIME_ENV_CONTRACT)
    assert not missing, f"add to agents/runtime_env.py: {sorted(missing)}"


def test_terraform_sets_only_contract_env_vars_that_code_reads() -> None:
    tf_vars = _env_vars_set_by_terraform()
    assert tf_vars, "no env vars found in terraform Cloud Run definition"
    assert tf_vars <= set(RUNTIME_ENV_CONTRACT), sorted(
        tf_vars - set(RUNTIME_ENV_CONTRACT)
    )
    # GOOGLE_GENAI_USE_VERTEXAI is consumed by google-genai SDK; the two CONTEXT_TOKEN_* vars
    # are contract-documented compatibility pins on agent_runtime (verified in
    # test_terraform_modules_contract.py).
    sdk_or_compat_vars = {
        "GOOGLE_GENAI_USE_VERTEXAI",
        "CONTEXT_TOKEN_KMS_KEY_VERSION",
        "CONTEXT_TOKEN_REQUIRE_KMS",
    }
    unread = tf_vars - _env_vars_read_by_code() - sdk_or_compat_vars
    assert (
        not unread
    ), f"terraform sets env vars no code reads: {sorted(unread)}"


# ---------------------------------------------------------------------------------------------
# Terraform: one serving identity, least privilege, native guardrail/RLS resources
# ---------------------------------------------------------------------------------------------


def test_cloud_run_runs_as_the_single_runtime_identity() -> None:
    tf = (CORE / "iap_gateway.tf").read_text()
    assert re.search(
        r"service_account\s+= google_service_account\.pooled_agent_runtime\.email",
        tf,
    )
    iso = TENANT_TF.read_text()
    impersonation = iso[iso.index('"gateway_impersonates_tenant"') :]
    # Until ADR-0014 B4 step 4 (runtime_keeps_token_creator = false) the runtime keeps this grant.
    block = impersonation.split("\n}\n")[0]
    assert "var.runtime_sa_email" in block
    assert "var.runtime_keeps_token_creator" in block
    root = (TF / "main.tf").read_text()
    assert (
        "runtime_sa_email            = module.platform_core.pooled_agent_runtime_sa_email"
        in root
    )


def test_serving_identity_has_no_admin_or_data_roles() -> None:
    tf = (CORE / "iap_gateway.tf").read_text()
    start = tf.index("runtime_project_roles = setunion(")
    roles = tf[
        start : tf.index(
            'resource "google_project_iam_member" "runtime_bindings"'
        )
    ]
    for forbidden in (
        "roles/bigquery.admin",
        "roles/modelarmor.admin",
        "roles/dlp.admin",
        "roles/cloudkms.cryptoKeyEncrypterDecrypter",
        "roles/secretmanager.secretAccessor",
        "roles/storage.objectAdmin",
        "roles/owner",
        "roles/editor",
    ):
        assert forbidden not in roles, forbidden


def test_guardrails_and_row_policies_are_real_terraform_resources() -> None:
    all_tf = "\n".join(
        p.read_text() for p in TF.rglob("*.tf") if ".terraform" not in p.parts
    )
    assert 'resource "google_model_armor_template" "inbound_pep"' in all_tf
    assert 'resource "google_bigquery_row_access_policy" "tenant"' in all_tf
    assert (
        "terraform_data" not in all_tf
    ), "inert terraform_data placeholders must not stand in for resources"


def test_terraform_row_policy_ids_match_tenant_config() -> None:
    # The root module reads the same tenant YAML and applies the same default as
    # TenantConfig.row_policy_id(); the tenant module uses that ID verbatim.
    tenants_tf = (TF / "tenants.tf").read_text()
    assert 'fileset(local.tenant_config_dir, "*.yaml")' in tenants_tf
    assert (
        'cfg.bigquery_row_policy_id : "rap_${replace(tenant_id, "-", "_")}"'
        in tenants_tf
    )
    assert "policy_id        = var.row_policy_id" in TENANT_TF.read_text()
    cfg = pc.load_platform_config("sandbox")
    for tenant in cfg.tenants:
        expected = (
            tenant.bigquery_row_policy_id
            or "rap_" + tenant.tenant_id.replace("-", "_")
        )
        assert tenant.row_policy_id() == expected


# ---------------------------------------------------------------------------------------------
# Scripts and runtime never (re)grant access or provision security resources
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "script", ["configure_3p_connectors.py", "rotate_jira_api_token.sh"]
)
def test_secret_scripts_do_not_modify_iam(script: str) -> None:
    text = (REPO / "scripts" / script).read_text()
    assert "add-iam-policy-binding" not in text
    assert "setIamPolicy" not in text


def test_runtime_does_not_provision_guardrails_or_issue_rls_ddl() -> None:
    code = "\n".join(
        p.read_text()
        for p in [
            *(REPO / "agents").rglob("*.py"),
            *(REPO / "app").rglob("*.py"),
        ]
    )
    assert "create_template(" not in code
    assert "ensure_row_access_policies" not in code
    py_only = re.sub(
        r"code: `[^`]*`", "", code
    )  # ignore DDL shown as text in the demo UI
    assert not re.search(
        r"client\.query\([^)]*ROW ACCESS POLICY", py_only, re.DOTALL
    )


def test_agent_engine_recipe_is_least_privilege_and_captures_no_content() -> (
    None
):
    text = (REPO / "scripts" / "deploy_vertex_agent_engine.py").read_text()
    roles = text[
        text.index("REQUIRED_REASONING_ENGINE_ROLES") : text.index(
            ")", text.index("REQUIRED_REASONING_ENGINE_ROLES")
        )
    ]
    assert "cryptoKeyEncrypterDecrypter" not in roles
    assert "secretAccessor" not in roles
    assert "CAPTURE_MESSAGE_CONTENT=SPAN_AND_EVENT" not in text
    assert "ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS=true" not in text


def test_bootstrap_uses_the_single_deploy_path() -> None:
    text = (REPO / "scripts" / "bootstrap_customer_env.sh").read_text()
    assert "scripts/deploy.sh" in text
    assert "--service-account" not in text
    deploy = (REPO / "scripts" / "deploy.sh").read_text()
    run_deploy = deploy[deploy.index("gcloud run deploy") :].split("\n")[0]
    assert "--service-account" not in run_deploy
    assert "--set-env-vars" not in run_deploy


# ---------------------------------------------------------------------------------------------
# Review follow-ups (#2 suggestion 2, #3 suggestion 1)
# ---------------------------------------------------------------------------------------------


def test_registered_tenant_secrets_are_enforced_without_code_edits() -> None:
    from agents.context import register_tenant, reset_dynamic_tenants
    from agents.tenant_credentials import TenantIsolationPolicy

    try:
        register_tenant(
            tenant_id="tenant-acme-corp",
            display_name="Acme",
            secret_ids=("acme-jira-credentials",),
        )
        policy = TenantIsolationPolicy(project_id="cymbal-multitenancy-example")
        policy.assert_secret(
            "tenant-acme-corp", "acme-jira-credentials"
        )  # owner: allowed
        with pytest.raises(PermissionError):
            policy.assert_secret(
                "tenant-finvault-alpha", "acme-jira-credentials"
            )
        with pytest.raises(PermissionError):
            policy.assert_secret(
                "tenant-acme-corp", "cymbal-finvault-jira-credentials"
            )
    finally:
        reset_dynamic_tenants()


def test_a_secret_cannot_belong_to_two_tenants() -> None:
    from agents.context import register_tenant, reset_dynamic_tenants

    try:
        with pytest.raises(ValueError, match="already owned"):
            register_tenant(
                tenant_id="tenant-evil-corp",
                display_name="Evil",
                secret_ids=("cymbal-finvault-jira-credentials",),
            )
    finally:
        reset_dynamic_tenants()
    cfg = pc.load_platform_config("sandbox").model_dump()
    cfg["tenants"][1]["secret_ids"] = cfg["tenants"][0]["secret_ids"]
    with pytest.raises(ValueError, match="secret_ids shared"):
        pc.PlatformConfig.model_validate(cfg)


def test_reset_dynamic_tenants_reloads_config_for_the_current_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agents.context import TENANT_DIRECTORY, reset_dynamic_tenants

    try:
        monkeypatch.setenv("CYMBAL_ENV", "customer.example")
        reset_dynamic_tenants()
        assert set(TENANT_DIRECTORY) == {"tenant-acme-corp"}
    finally:
        monkeypatch.setenv("CYMBAL_ENV", "sandbox")
        reset_dynamic_tenants()
    assert "tenant-finvault-alpha" in TENANT_DIRECTORY


def test_sandbox_child_module_validations_and_silo_wiring() -> None:
    for var_file in (
        TF / "variables.tf",
        CORE / "variables.tf",
        TF / "modules" / "agent_runtime" / "variables.tf",
    ):
        text = var_file.read_text(encoding="utf-8")
        for var_name in (
            "agent_sandbox_reasoning_engine_name",
            "agent_sandbox_code_template",
            "agent_sandbox_shell_template",
        ):
            block = text[text.index(f'variable "{var_name}"') :].split("\n}\n")[
                0
            ]
            assert (
                "validation {" in block
            ), f"{var_file}: {var_name} missing validation block"

    silo_main = (TF / "envs" / "silo-example" / "main.tf").read_text(
        encoding="utf-8"
    )
    for var_name in (
        "agent_sandbox_reasoning_engine_name",
        "agent_sandbox_code_template",
        "agent_sandbox_shell_template",
    ):
        assert var_name in silo_main, f"silo-example/main.tf missing {var_name}"
