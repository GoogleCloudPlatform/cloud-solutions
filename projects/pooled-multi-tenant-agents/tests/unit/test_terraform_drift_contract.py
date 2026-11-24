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

# pylint: disable=line-too-long

"""Terraform describes the intended sandbox state (docs/terraform_drift_2026-11-04.md).

Guards the decisions from the 2026-11-04 drift review so later edits can't quietly undo them:
the context-signing key and its IAM are codified; human access (IAP reviewers, operator
impersonation) always expires; no public members; buckets enforce public access prevention;
the runtime is decrypt-only on the platform key and gets data-plane roles only in live mode;
the sandbox inputs contain no personal emails; the import script adopts only intended
resources (never the retired legacy SA).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TF = REPO / "terraform"
CORE = TF / "modules" / "platform_core"
# Root composition, modules and stamping examples (not provider caches).
ALL_TF = "\n".join(
    p.read_text()
    for p in sorted(TF.rglob("*.tf"))
    if ".terraform" not in p.parts
)


def _block(kind: str, name: str) -> str:
    m = re.search(
        rf'resource "{kind}" "{name}" \{{(.*?)\n\}}', ALL_TF, re.DOTALL
    )
    assert m, f"{kind}.{name} missing"
    return m.group(1)


def test_context_signing_key_and_its_iam_are_codified() -> None:
    ring = _block("google_kms_key_ring", "platform")
    key = _block("google_kms_crypto_key", "context_signing")
    assert 'name       = "cymbal-platform-kr"' in ring
    assert 'name     = "ws2-context-signing"' in key
    assert 'purpose  = "ASYMMETRIC_SIGN"' in key
    assert 'algorithm        = "EC_SIGN_P256_SHA256"' in key
    assert "prevent_destroy = true" in key
    signer = _block(
        "google_kms_crypto_key_iam_member", "runtime_context_signer"
    )
    assert 'role          = "roles/cloudkms.signerVerifier"' in signer
    assert "google_kms_crypto_key.context_signing.id" in signer
    viewer = _block(
        "google_kms_crypto_key_iam_member", "broker_context_key_viewer"
    )
    assert 'role          = "roles/cloudkms.publicKeyViewer"' in viewer
    assert "google_kms_crypto_key.context_signing.id" in viewer


def test_human_access_always_expires() -> None:
    reviewers = _block(
        "google_iap_web_cloud_run_service_iam_member",
        "gateway_time_boxed_accessors",
    )
    assert "condition {" in reviewers
    assert "request.time < timestamp(" in reviewers
    assert "var.iap_time_boxed_accessors.expires" in reviewers
    operator = _block(
        "google_service_account_iam_member", "operator_time_boxed_impersonation"
    )
    assert "condition {" in operator
    assert "var.operator_impersonation.expires" in operator
    variables = (TF / "variables.tf").read_text()
    for var in ("iap_time_boxed_accessors", "operator_impersonation"):
        body = variables[variables.index(f'variable "{var}"') :].split("\n}\n")[
            0
        ]
        assert "validation {" in body
        assert "expires" in body


def test_no_public_members_anywhere() -> None:
    members = re.findall(r'^\s*member\s*=\s*"([^"]+)"', ALL_TF, re.MULTILINE)
    assert members
    assert not [
        m for m in members if m in ("allUsers", "allAuthenticatedUsers")
    ]
    assert "cymbal-ingress-pep-sa" not in ALL_TF.replace(
        "`cymbal-ingress-pep-sa`", ""
    )


def test_gateway_is_iap_protected_and_invoked_only_by_iap() -> None:
    gw = _block("google_cloud_run_v2_service", "cymbal_pooled_gateway")
    assert "iap_enabled         = true" in gw
    assert "provider            = google-beta" in gw
    assert "max_instance_count = var.gateway_max_instance_count" in gw
    precond = (
        "var.gateway_max_instance_count <= 1 || "
        "(var.enable_live_mode && var.enable_memorystore_redis)"
    )
    assert precond in gw
    assert "startup_cpu_boost = true" in gw
    for var_file in (TF / "variables.tf", CORE / "variables.tf"):
        txt = var_file.read_text()
        block = txt[txt.index('variable "gateway_max_instance_count"') :].split(
            "\n}\n"
        )[0]
        assert re.search(r"default\s+= 1\b", block), var_file
    invoker = _block(
        "google_cloud_run_v2_service_iam_member", "iap_invokes_gateway"
    )
    assert "gcp-sa-iap.iam.gserviceaccount.com" in invoker
    invokers = re.findall(
        r'resource "google_cloud_run_v2_service_iam_member" "(\w+)"', ALL_TF
    )
    assert sorted(invokers) == [
        "agent_invokes_broker",
        "gateway_invokes_agent_runtime",
        "iap_invokes_gateway",
        "runtime_invokes_broker",
    ]


def test_buckets_enforce_public_access_prevention() -> None:
    for name in ("pooled_cmek_runbooks", "tenant_skills"):
        assert 'public_access_prevention    = "enforced"' in _block(
            "google_storage_bucket", name
        )


def test_runtime_is_decrypt_only_on_the_platform_key_and_data_roles_need_live_mode() -> (
    None
):
    glob_key = _block(
        "google_kms_crypto_key_iam_member", "runtime_platform_global"
    )
    assert 'role          = "roles/cloudkms.cryptoKeyDecrypter"' in glob_key
    gw = (CORE / "iap_gateway.tf").read_text()
    start = gw.index("runtime_project_roles = setunion(")
    roles = gw[
        start : gw.index(
            'resource "google_project_iam_member" "runtime_bindings"'
        )
    ]
    always, live_only = roles.split("var.enable_live_mode ?")
    assert "roles/aiplatform.user" in live_only
    assert "roles/aiplatform.user" not in always
    assert "roles/serviceusage.serviceUsageConsumer" in always


def test_edge_waf_is_opt_in() -> None:
    waf = _block("google_compute_security_policy", "cymbal_edge_waf")
    assert re.search(r"count\s+= var\.enable_edge_waf \? 1 : 0", waf)


def test_sandbox_inputs_hold_no_personal_emails_and_local_inputs_are_ignored() -> (
    None
):
    if not (TF / "sandbox.tfvars").is_file():
        pytest.skip("Internal sandbox.tfvars is excluded from public exports.")
    tfvars = (TF / "sandbox.tfvars").read_text()
    assert "@" not in tfvars
    assert "enable_live_mode         = true" in tfvars
    assert "enable_tenant_wif_provider = true" in tfvars
    assert "enable_memory_bank_iam_cel = true" in tfvars
    assert "runtime_keeps_token_creator = false" in tfvars
    gitignore = (REPO / ".gitignore").read_text()
    assert "*.auto.tfvars" in gitignore


def test_import_script_adopts_only_intended_resources() -> None:
    script = REPO / "scripts" / "terraform_import_sandbox.sh"
    if not script.is_file():
        pytest.skip(
            "Internal terraform_import_sandbox.sh is excluded from public exports."
        )
    assert (
        subprocess.run(["bash", "-n", str(script)], check=False).returncode == 0
    )
    out = subprocess.run(
        ["bash", str(script)],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    ).stdout
    commands = [
        line for line in out.splitlines() if line.startswith("terraform ")
    ]
    assert len(commands) > 60
    assert all("-var-file=sandbox.tfvars" in c for c in commands)
    joined = "\n".join(commands)
    assert "cymbal-ingress-pep-sa" not in joined
    # S3 was fixed live (decrypt-only), so the binding is adopted, but never the broader role.
    platform_global = [c for c in commands if "runtime_platform_global" in c]
    assert len(platform_global) == 1
    assert "roles/cloudkms.cryptoKeyDecrypter" in platform_global[0]
    assert "EncrypterDecrypter" not in platform_global[0]
    assert "context_signing" in out
    assert "credential_broker" in out


def test_alloydb_public_ip_is_opt_in_and_the_sandbox_opts_in_explicitly() -> (
    None
):
    """The primary instance gets a public IP only when the operator asks for it.

    The module and root variables default to false; the instance reads the variable (never a
    literal `true`); the live sandbox and the turnkey example set it explicitly, with the reason.
    """
    instance = _block("google_alloydb_instance", "pooled_rls_primary")
    assert "enable_public_ip = var.alloydb_enable_public_ip" in instance
    assert "authorized_external_networks" not in instance
    assert not re.search(
        r"^\s*enable_public_ip\s*=\s*true", ALL_TF, re.MULTILINE
    )
    for variables in (TF / "variables.tf", CORE / "variables.tf"):
        m = re.search(
            r'variable "alloydb_enable_public_ip" \{(.*?)\n\}',
            variables.read_text(),
            re.DOTALL,
        )
        assert m, f"alloydb_enable_public_ip missing in {variables}"
        assert re.search(r"default\s*=\s*false", m.group(1)), variables
    assert re.search(
        r"alloydb_enable_public_ip\s*=\s*var\.alloydb_enable_public_ip",
        (TF / "main.tf").read_text(),
    )
    if (TF / "sandbox.tfvars").is_file():
        assert re.search(
            r"^alloydb_enable_public_ip\s*=\s*true$",
            (TF / "sandbox.tfvars").read_text(),
            re.MULTILINE,
        )
    example = (TF / "terraform.tfvars.example").read_text()
    assert re.search(
        r"^alloydb_enable_public_ip\s*=\s*false$", example, re.MULTILINE
    )
    assert "internet-facing" in example
