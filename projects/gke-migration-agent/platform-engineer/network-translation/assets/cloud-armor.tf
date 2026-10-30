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

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

variable "cluster_project" {
  type        = string
  description = "Target GKE cluster Google Cloud project ID"
}

resource "google_compute_security_policy" "shop_armor" {
  project = var.cluster_project
  name    = "${var.cluster_project}-shop-armor"

  # OWASP CRS v4.22 baseline
  rule {
    action   = "deny(403)"
    priority = 1000
    match {
      expr {
        expression = "evaluatePreconfiguredWaf('sqli-v422-stable', {'sensitivity': 2})"
      }
    }
  }
  rule {
    action   = "deny(403)"
    priority = 1010
    match {
      expr {
        expression = "evaluatePreconfiguredWaf('xss-v422-stable', {'sensitivity': 2})"
      }
    }
  }
  rule {
    action   = "deny(403)"
    priority = 1020
    match {
      expr {
        expression = "evaluatePreconfiguredWaf('protocolattack-v422-stable', {'sensitivity': 2})"
      }
    }
  }
  rule {
    action   = "deny(403)"
    priority = 1030
    match {
      expr {
        expression = "evaluatePreconfiguredWaf('rce-v422-stable', {'sensitivity': 2})"
      }
    }
  }
  rule {
    action   = "deny(403)"
    priority = 1040
    match {
      expr {
        expression = "evaluatePreconfiguredWaf('lfi-v422-stable', {'sensitivity': 2})"
      }
    }
  }

  # Rate limiting (per-IP throttle)
  rule {
    action   = "rate_based_ban"
    priority = 2000
    rate_limit_options {
      rate_limit_threshold {
        count        = 200
        interval_sec = 60
      }
      enforce_on_key   = "IP"
      ban_duration_sec = 600
      conform_action   = "allow"
      exceed_action    = "deny(429)"
    }
    match {
      versioned_expr = "SRC_IPS_V1"
      config { src_ip_ranges = ["*"] }
    }
  }

  # Default allow
  rule {
    action   = "allow"
    priority = 2147483647
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    description = "default rule"
  }
}
