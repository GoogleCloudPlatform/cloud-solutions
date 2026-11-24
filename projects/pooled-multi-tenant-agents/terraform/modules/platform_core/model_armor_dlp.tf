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

# ============================================================================
# Hop 2 & Hop 4: Model Armor Template & Cloud DLP SDP Guardrails
# ============================================================================

# Model Armor inbound/outbound PEP template. Owned by Terraform: the runtime only verifies
# it exists (LiveModelArmorGuardrail.require_template) and never creates it.
resource "google_model_armor_template" "inbound_pep" {
  location    = var.region
  template_id = var.model_armor_template_id
  labels      = local.common_labels

  filter_config {
    pi_and_jailbreak_filter_settings {
      filter_enforcement = "ENABLED"
      confidence_level   = "LOW_AND_ABOVE"
    }
    malicious_uri_filter_settings {
      filter_enforcement = "ENABLED"
    }
  }

  # The API returns server-set template_metadata (e.g. data_residency_compliant) and rejects updates
  # that send it empty; Terraform does not manage it.
  lifecycle {
    ignore_changes = [template_metadata]
  }

  depends_on = [google_project_service.enabled_apis]
}

resource "google_data_loss_prevention_inspect_template" "tenant_pii_inspect" {
  parent       = "projects/${var.project_id}/locations/${var.region}"
  display_name = "Cymbal Multi-Tenant Banking & Payment PII Inspect Template"
  description  = "Inspects egress tool payloads for FinVault banking PII (SSN/ABA) and RetailStream payment PANs"
  depends_on   = [google_project_service.enabled_apis]

  inspect_config {
    min_likelihood = "POSSIBLE"
    info_types {
      name = "US_SOCIAL_SECURITY_NUMBER"
    }
    info_types {
      name = "CREDIT_CARD_NUMBER"
    }
    info_types {
      name = "US_BANK_ROUTING_MICR"
    }
    info_types {
      name = "IBAN_CODE"
    }
    info_types {
      name = "SWIFT_CODE"
    }
    info_types {
      name = "EMAIL_ADDRESS"
    }
  }
}

resource "google_data_loss_prevention_deidentify_template" "tenant_pii_deidentify" {
  parent       = "projects/${var.project_id}/locations/${var.region}"
  display_name = "Cymbal Multi-Tenant PII Masking Deidentify Template"
  description  = "Replaces detected banking and payment PII with info-type tags before egress"
  depends_on   = [google_project_service.enabled_apis]

  deidentify_config {
    info_type_transformations {
      transformations {
        primitive_transformation {
          replace_with_info_type_config = true
        }
      }
    }
  }
}
