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

# pylint: disable=import-outside-toplevel,line-too-long

"""Live Model Armor and Cloud DLP guardrail adapters (Hops 2 and 4)."""

from __future__ import annotations

from typing import Any

from agents.adapters._bridge_runtime import (
    DEFAULT_DLP_DEIDENTIFY_TEMPLATE,
    DEFAULT_DLP_INSPECT_TEMPLATE,
    DEFAULT_GCP_PROJECT,
    DEFAULT_GCP_REGION,
    DEFAULT_MODEL_ARMOR_TEMPLATE_ID,
    _egress_guardrail,
)
from agents.interceptors import screen_tool_output_for_indirect_injection
from agents.kms_rest import (
    configure_client_certificate_env,
    workload_spiffe_mtls_active,
)
from agents.shared_diagnostic_agent import get_clean_project_id


class LiveModelArmorGuardrail:
    """Hop 2 Ingress & Hop 4 Egress PEP backed by live Model Armor
    (`modelarmor.googleapis.com`).
    """

    def __init__(
        self,
        project_id: str = DEFAULT_GCP_PROJECT,
        location: str = DEFAULT_GCP_REGION,
        template_id: str = DEFAULT_MODEL_ARMOR_TEMPLATE_ID,
    ) -> None:
        from google.api_core.client_options import ClientOptions
        from google.cloud import modelarmor_v1

        configure_client_certificate_env()
        self.project_id = get_clean_project_id(project_id)
        self.location = location
        self.template_id = template_id
        self.parent = f"projects/{self.project_id}/locations/{location}"
        self.template_name = f"{self.parent}/templates/{template_id}"
        self._ma = modelarmor_v1
        endpoint_host = (
            f"https://modelarmor.{location}.rep.mtls.googleapis.com"
            if workload_spiffe_mtls_active()
            else f"https://modelarmor.{location}.rep.googleapis.com"
        )
        self._client = modelarmor_v1.ModelArmorClient(
            transport="rest",
            client_options=ClientOptions(
                api_endpoint=endpoint_host,
                quota_project_id=self.project_id,
            ),
        )

    def require_template(self) -> str:
        """Returns the Model Armor template; never creates it at runtime.

        The template is owned by Terraform (`google_model_armor_template`). A missing template is a
        deployment error, not something a request should silently provision.
        """
        from google.api_core import exceptions as gcp_exceptions

        try:
            return self._client.get_template(name=self.template_name).name
        except gcp_exceptions.NotFound as exc:
            raise RuntimeError(
                "E_GUARDRAIL_NOT_PROVISIONED: Model Armor template '"
                f"{self.template_name}"
                "' is missing. "
                "Apply terraform (google_model_armor_template) before serving traffic."
            ) from exc

    def sanitize_prompt(self, prompt: str) -> dict[str, Any]:
        """Calls live Model Armor `sanitize_user_prompt`."""
        template_path = self.require_template()
        req = self._ma.SanitizeUserPromptRequest(
            name=template_path,
            user_prompt_data=self._ma.DataItem(text=prompt),
        )
        resp = self._client.sanitize_user_prompt(request=req)
        match_state = resp.sanitization_result.filter_match_state.name
        return {
            "template": template_path,
            "filter_match_state": match_state,
            "blocked": match_state == "MATCH_FOUND",
        }

    def sanitize_model_response(self, response_text: str) -> dict[str, Any]:
        """Hop 4 Egress: Calls live Model Armor `sanitize_model_response`."""
        template_path = self.require_template()
        req = self._ma.SanitizeModelResponseRequest(
            name=template_path,
            model_response_data=self._ma.DataItem(text=response_text),
        )
        resp = self._client.sanitize_model_response(request=req)
        match_state = resp.sanitization_result.filter_match_state.name
        return {
            "template": template_path,
            "filter_match_state": match_state,
            "blocked": match_state == "MATCH_FOUND",
        }


class LiveCloudDLPGuardrail:
    """Hop 4 Egress PEP backed by live regional Cloud DLP templates."""

    def __init__(
        self,
        project_id: str = DEFAULT_GCP_PROJECT,
        location: str = DEFAULT_GCP_REGION,
        inspect_template: str = DEFAULT_DLP_INSPECT_TEMPLATE,
        deidentify_template: str = DEFAULT_DLP_DEIDENTIFY_TEMPLATE,
    ) -> None:
        from google.api_core.client_options import ClientOptions
        from google.cloud import dlp_v2

        configure_client_certificate_env()
        self.project_id = get_clean_project_id(project_id)
        self.location = location
        self.parent = f"projects/{self.project_id}/locations/{location}"
        self.inspect_template = inspect_template
        self.deidentify_template = deidentify_template
        dlp_kwargs: dict[str, Any] = {
            "client_options": ClientOptions(quota_project_id=self.project_id),
        }
        if workload_spiffe_mtls_active():
            dlp_kwargs["transport"] = "rest"
        self._client = dlp_v2.DlpServiceClient(**dlp_kwargs)

    def deidentify_tool_output(
        self, *, raw_output: str, tool_name: str, tenant_id: str
    ) -> dict[str, Any]:
        """Screens for 2nd-order prompt injection, then calls live Cloud DLP
        `deidentify_content`.
        """
        screen_tool_output_for_indirect_injection(
            raw_output=raw_output, tool_name=tool_name
        )

        response = self._client.deidentify_content(
            request={
                "parent": self.parent,
                "inspect_template_name": self.inspect_template,
                "deidentify_template_name": self.deidentify_template,
                "item": {"value": raw_output},
            }
        )
        overview = response.overview
        matched_info_types = [
            summary.info_type.name
            for summary in overview.transformation_summaries
            if summary.info_type.name
        ]
        final_text = _egress_guardrail(
            tenant_id=tenant_id,  # the caller's tenant, never a hard-coded one
            tool_name=tool_name,
            tool_args={},
            raw_output=response.item.value,
        )
        return {
            "redacted_text": final_text,
            "transformed_units": overview.transformed_bytes,
            "matched_info_types": matched_info_types,
            "inspect_template": self.inspect_template,
            "deidentify_template": self.deidentify_template,
        }
