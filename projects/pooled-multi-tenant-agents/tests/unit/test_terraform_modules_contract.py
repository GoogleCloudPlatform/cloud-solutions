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

# pylint: disable=line-too-long,protected-access

"""Contracts for the Terraform module layout (B2): terraform/modules/{platform_core,tenant,
tenant_data_plane}, the sandbox composition in terraform/ and the stamping examples in envs/.

Guards the refactor's safety properties so later edits can't quietly undo them: the tenant ID
that reaches the row-policy SQL is validated like platform_config does, tenant files must be
named after their tenant, tenant CMEK keys are never destroyed, the runtime gets no TokenCreator
on tenant SAs by default, and a hybrid data plane always names its PSC consumer.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from agents import platform_config as pc

REPO = Path(__file__).resolve().parents[2]
TF = REPO / "terraform"
CORE = TF / "modules" / "platform_core"
AGENT_RUNTIME = TF / "modules" / "agent_runtime"
TENANT = TF / "modules" / "tenant"
DATA_PLANE = TF / "modules" / "tenant_data_plane"


def _variable(text: str, name: str) -> str:
    start = text.index(f'variable "{name}" {{')
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise AssertionError(f"unterminated variable {name}")


def _resource(text: str, kind: str, name: str) -> str:
    m = re.search(rf'resource "{kind}" "{name}" \{{(.*?)\n\}}', text, re.DOTALL)
    assert m, f"{kind}.{name} missing"
    return m.group(1)


def _hcl_regex(block: str) -> str:
    m = re.search(r'regex\("(\^[^"]+\$)"', block)
    assert m, "no regex() validation"
    # HCL string escapes: "\\d" in HCL is \d in the regex.
    return m.group(1).replace("\\\\", "\\")


# --- (1) tenant_id and other identifiers are validated before they reach SQL / resource names ---


def test_tenant_id_validation_matches_platform_config() -> None:
    block = _variable((TENANT / "variables.tf").read_text(), "tenant_id")
    assert "validation {" in block
    assert _hcl_regex(block) == pc._TENANT_ID_RE.pattern


@pytest.mark.parametrize(
    "bad",
    [
        "tenant-x' OR TRUE --",  # would rewrite the row policy filter
        "Tenant-Upper",
        "t",
        "1-starts-with-digit",
        "tenant_with_underscore",
        "tenant-" + "x" * 60,
    ],
)
def test_malformed_tenant_ids_are_rejected(bad: str) -> None:
    rx = re.compile(
        _hcl_regex(
            _variable((TENANT / "variables.tf").read_text(), "tenant_id")
        )
    )
    assert not rx.match(bad)


def test_sandbox_tenant_ids_pass_the_validation() -> None:
    rx = re.compile(
        _hcl_regex(
            _variable((TENANT / "variables.tf").read_text(), "tenant_id")
        )
    )
    for tenant in pc.load_platform_config("sandbox").tenants:
        assert rx.match(tenant.tenant_id)


@pytest.mark.parametrize(
    "name", ["cmek_key_name", "row_policy_id", "secret_ids"]
)
def test_identifier_inputs_have_shape_checks(name: str) -> None:
    block = _variable((TENANT / "variables.tf").read_text(), name)
    rx = re.compile(_hcl_regex(block))
    assert not rx.match("x'; DROP ROW ACCESS POLICY")
    assert not rx.match("")


def test_row_filter_uses_only_the_validated_tenant_id() -> None:
    rap = _resource(
        (TENANT / "main.tf").read_text(),
        "google_bigquery_row_access_policy",
        "tenant",
    )
    assert "filter_predicate = \"tenant_id = '${var.tenant_id}'\"" in rap


def test_tenant_file_names_must_match_tenant_ids() -> None:
    tenants_tf = (TF / "tenants.tf").read_text()
    assert 'f if "${try(cfg.tenant_id, "")}.yaml" != f' in tenants_tf
    outputs = (TF / "outputs.tf").read_text()
    block = outputs[outputs.index('output "tenant_service_accounts"') :].split(
        "\n}\n"
    )[0]
    assert re.search(r"^\s*precondition \{", block, re.MULTILINE)
    assert re.search(
        r"^\s*condition\s+= length\(local\.tenant_file_mismatches\) == 0",
        block,
        re.MULTILINE,
    )
    for path in (REPO / "config" / "tenants").glob("*/*.yaml"):
        assert f"tenant_id: {path.stem}\n" in path.read_text(), path


# --- (2) surviving mutants from the review -------------------------------------------------------


def test_runtime_gets_no_token_creator_on_tenant_sas_by_default() -> None:
    block = _variable(
        (TENANT / "variables.tf").read_text(), "runtime_keeps_token_creator"
    )
    assert re.search(r"default\s+= false", block)


def test_tenant_cmek_is_never_destroyed_by_terraform() -> None:
    key = _resource(
        (TENANT / "main.tf").read_text(), "google_kms_crypto_key", "tenant_cmek"
    )
    assert "prevent_destroy = true" in key


def test_hybrid_data_plane_always_names_its_psc_consumer() -> None:
    block = _variable(
        (DATA_PLANE / "variables.tf").read_text(), "allowed_consumer_projects"
    )
    assert "default" not in block
    assert "length(var.allowed_consumer_projects) > 0" in block
    instance = _resource(
        (DATA_PLANE / "main.tf").read_text(),
        "google_alloydb_instance",
        "primary",
    )
    assert (
        "allowed_consumer_projects = var.allowed_consumer_projects" in instance
    )


# --- (3) B5 S2: per-agent Cloud Run runtime module, dedicated build SA, and rollout runbook ------


def test_agent_runtime_module_defines_cloud_run_service_with_deletion_guard() -> (
    None
):
    main_tf = (AGENT_RUNTIME / "main.tf").read_text()
    svc = _resource(main_tf, "google_cloud_run_v2_service", "agent_runtime")
    assert "max_instance_count = 1" in svc
    assert "deletion_protection = var.deletion_protection" in svc
    assert 'command = ["uvicorn"]' in svc
    assert '"runtime_service.main:create_app"' in svc
    for required_env in (
        "CYMBAL_ENV",
        "CYMBAL_LIVE_GCP",
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_CLOUD_LOCATION",
        "RUNTIME_AGENT_ID",
        "RUNTIME_ALLOWED_CALLERS",
        "RUNTIME_EXPECTED_AUDIENCE",
        "CREDENTIAL_BROKER_URL",
        "CONTEXT_SIGNING_KMS_KEY",
        "CONTEXT_TOKEN_KMS_KEY_VERSION",
        "CONTEXT_TOKEN_REQUIRE_KMS",
        "CONTEXT_TOKEN_REQUIRE_AGENT_ID",
    ):
        assert f'name  = "{required_env}"' in svc, required_env


def test_agent_runtime_least_privilege_iam_and_no_public_or_signing_grants() -> (
    None
):
    main_tf = (AGENT_RUNTIME / "main.tf").read_text()
    assert "allUsers" not in main_tf
    assert "allAuthenticatedUsers" not in main_tf

    # Inbound: only the gateway SA may invoke the agent runtime service.
    invoker = _resource(
        main_tf,
        "google_cloud_run_v2_service_iam_member",
        "gateway_invokes_agent_runtime",
    )
    assert 'role     = "roles/run.invoker"' in invoker
    assert (
        'member   = "serviceAccount:${var.gateway_service_account_email}"'
        in invoker
    )

    # Outbound: agent principal gets KMS publicKeyViewer + broker run.invoker (+ live-mode
    # aiplatform.user).
    assert (
        'agent_principal            = "principal://agents.global.org-${var.organization_id}'
        ".system.id.goog/resources/run/projects/${var.project_number}"
        '/locations/${var.region}/services/${var.service_name}"' in main_tf
    )
    kms_viewer = _resource(
        main_tf, "google_kms_crypto_key_iam_member", "agent_context_key_viewer"
    )
    assert 'role          = "roles/cloudkms.publicKeyViewer"' in kms_viewer
    assert "member        = local.agent_principal" in kms_viewer

    broker_invoker = _resource(
        main_tf,
        "google_cloud_run_v2_service_iam_member",
        "agent_invokes_broker",
    )
    assert 'role     = "roles/run.invoker"' in broker_invoker
    assert "member   = local.agent_principal" in broker_invoker

    ai_user = _resource(
        main_tf, "google_project_iam_member", "agent_aiplatform_user"
    )
    assert "count   = var.enable_live_mode ? 1 : 0" in ai_user
    assert 'role    = "roles/aiplatform.user"' in ai_user
    assert "member  = local.agent_principal" in ai_user

    # Never grant signing or tenant SA impersonation to an agent runtime.
    code_lines = "\n".join(
        line
        for line in main_tf.splitlines()
        if not line.lstrip().startswith("#")
    )
    assert "roles/cloudkms.signerVerifier" not in code_lines
    assert "roles/iam.serviceAccountTokenCreator" not in code_lines


def test_root_composition_defines_both_agent_runtimes_behind_feature_flag() -> (
    None
):
    root_main = (TF / "main.tf").read_text()
    assert 'service_name = "cymbal-agent-shared"' in root_main
    assert 'agent_id     = "cymbal_shared_diagnostic_agent"' in root_main
    assert 'service_name = "cymbal-agent-finvault-alpha"' in root_main
    assert 'agent_id     = "finvault_regulatory_escalation_agent"' in root_main
    assert (
        "for_each = var.enable_agent_runtimes ? local.agent_runtimes : {}"
        in root_main
    )

    flag_block = _variable(
        (TF / "variables.tf").read_text(), "enable_agent_runtimes"
    )
    assert re.search(r"default\s+= false", flag_block)
    if not (TF / "sandbox.tfvars").is_file():
        return
    tfvars = (TF / "sandbox.tfvars").read_text()
    assert "enable_agent_runtimes      = true" in tfvars
    assert "enable_build_sa            = true" in tfvars
    assert "bind_agent_id              = true" in tfvars
    assert "require_agent_binding      = true" in tfvars
    assert "broker_keep_runtime_caller = false" in tfvars

    outputs = (TF / "outputs.tf").read_text()
    assert 'output "agent_runtime_urls"' in outputs
    assert 'output "agent_runtime_principals"' in outputs

    gw_tf = (CORE / "iap_gateway.tf").read_text()
    assert "AGENT_RUNTIME_URLS" in gw_tf
    assert "CONTEXT_TOKEN_BIND_AGENT_ID" in gw_tf
    assert "CONTEXT_TOKEN_REQUIRE_AGENT_ID" in gw_tf

    broker_tf = (CORE / "credential_broker.tf").read_text()
    assert "BROKER_REQUIRE_AGENT_BINDING" in broker_tf
    assert "CONTEXT_TOKEN_REQUIRE_AGENT_ID" in broker_tf


def test_dedicated_build_sa_is_least_privilege() -> None:
    build_tf = (CORE / "build_sa.tf").read_text()
    sa = _resource(build_tf, "google_service_account", "cymbal_build")
    assert 'account_id   = "cymbal-build-sa"' in sa
    assert "count        = var.enable_build_sa ? 1 : 0" in sa

    code_lines = "\n".join(
        line
        for line in build_tf.splitlines()
        if not line.lstrip().startswith("#")
    )
    for required_role in (
        "roles/logging.logWriter",
        "roles/artifactregistry.writer",
        "roles/storage.objectViewer",
        "roles/storage.objectCreator",
    ):
        assert required_role in code_lines, required_role

    for forbidden_role in (
        "roles/owner",
        "roles/editor",
        "roles/run.admin",
        "roles/storage.admin",
        "roles/artifactregistry.admin",
        "roles/iam.serviceAccountAdmin",
        "roles/iam.securityAdmin",
        "roles/iam.serviceAccountTokenCreator",
    ):
        assert forbidden_role not in code_lines, forbidden_role
    assert not re.search(r"roles/iam\.\w*Admin", code_lines)


def test_b5_rollout_runbook_documents_bootstrap_import_flag_order_and_rollback() -> (
    None
):
    runbook = (
        REPO / "docs" / "runbooks" / "b5_agent_runtime_rollout.md"
    ).read_text()
    for required in (
        "--build-service-account",
        "--identity-type=agent-identity",
        "--functional-type=agent",
        "--identity-certificate",
        "terraform -chdir=terraform import",
        "CONTEXT_TOKEN_BIND_AGENT_ID",
        "BROKER_REQUIRE_AGENT_BINDING",
        "CONTEXT_TOKEN_REQUIRE_AGENT_ID",
        "Rollback:",
        "allUsers",
        "allAuthenticatedUsers",
    ):
        assert required in runbook, required
    assert (
        runbook.index("CONTEXT_TOKEN_BIND_AGENT_ID=1")
        < runbook.index("BROKER_REQUIRE_AGENT_BINDING=1")
        < runbook.index("CONTEXT_TOKEN_REQUIRE_AGENT_ID=1")
    )


def test_tenant_module_defines_issuer_bound_wif_pool_and_oidc_provider() -> (
    None
):
    tenant_tf = (TENANT / "main.tf").read_text()
    pool = _resource(
        tenant_tf, "google_iam_workload_identity_pool", "tenant_idp_pool"
    )
    assert (
        "count                     = var.enable_tenant_wif_provider ? 1 : 0"
        in pool
    )

    provider = _resource(
        tenant_tf,
        "google_iam_workload_identity_pool_provider",
        "tenant_oidc_provider",
    )
    assert '"google.subject"      = "assertion.sub"' in provider
    assert '"attribute.tenant_id" = "\'${var.tenant_id}\'"' in provider
    assert '"attribute.user_role" = "assertion.groups"' in provider
    assert (
        "attribute_condition = \"assertion.iss == '${var.tenant_oidc_issuer_uri}'\""
        in provider
    )

    root_main = (TF / "main.tf").read_text()
    assert (
        "enable_tenant_wif_provider  = var.enable_tenant_wif_provider"
        in root_main
    )
    assert (
        "tenant_oidc_issuer_uri      = each.value.oidc_issuer_uri" in root_main
    )
    tenants_tf = (TF / "tenants.tf").read_text()
    assert "var.tenant_wif_issuer_overrides" in tenants_tf
    assert "try(cfg.identity.issuer," in tenants_tf


def test_tenant_module_defines_memory_bank_iam_cel_and_per_tenant_alloydb_iam_user() -> (
    None
):
    tenant_tf = (TENANT / "main.tf").read_text()
    mb = _resource(
        tenant_tf, "google_project_iam_member", "tenant_memory_bank_user"
    )
    assert "count   = var.enable_memory_bank_iam_cel ? 1 : 0" in mb
    assert 'role    = "roles/aiplatform.memoryUser"' in mb
    assert (
        "api.getAttribute('aiplatform.googleapis.com/memoryScope', {})['tenant_id'] "
        "== '${var.tenant_id}'"
    ) in mb

    db_user = _resource(tenant_tf, "google_alloydb_user", "tenant_iam_db_user")
    assert 'user_type      = "ALLOYDB_IAM_USER"' in db_user
    assert "ignore_changes = [database_roles]" in db_user

    runtime_tf = (AGENT_RUNTIME / "main.tf").read_text()
    spans_writer = _resource(
        runtime_tf, "google_bigquery_table_iam_member", "agent_spans_writer"
    )
    assert 'role       = "roles/bigquery.dataEditor"' in spans_writer
    assert "var.enable_platform_live_resources" in spans_writer
    assert "var.enable_redis_tls" in _resource(
        runtime_tf,
        "google_secret_manager_secret_iam_member",
        "agent_redis_tls_accessor",
    )
    assert "ALLOYDB_TENANT_IAM_AUTH" in runtime_tf
    assert "MEMORY_BANK_REASONING_ENGINE" in runtime_tf


def test_modules_use_plan_time_booleans_for_count_and_for_each() -> None:
    """Module `count` and `dynamic` `for_each` gates must depend only on plan-time booleans, never
    on computed attributes from `module.platform_core` (zero-state `terraform apply` safety).
    """
    tenant_tf = (TENANT / "main.tf").read_text()
    for res_name in ("tenant_alloydb_client", "tenant_alloydb_db_user"):
        assert "count   = var.enable_alloydb_iam ? 1 : 0" in _resource(
            tenant_tf, "google_project_iam_member", res_name
        )
    assert "count          = var.enable_alloydb_iam ? 1 : 0" in _resource(
        tenant_tf, "google_alloydb_user", "tenant_iam_db_user"
    )
    runtime_tf = (AGENT_RUNTIME / "main.tf").read_text()
    assert (
        "for_each = (var.enable_live_mode && var.enable_vpc_access) ? [1] : []"
        in runtime_tf
    )
    assert "var.enable_vpc_access" in runtime_tf
    assert "var.enable_alloydb_primary_auth" in runtime_tf
    gw_tf = (CORE / "iap_gateway.tf").read_text()
    assert (
        '(var.agent_runtime_urls_json != "" || var.enable_agent_runtimes)'
        in gw_tf
    )
