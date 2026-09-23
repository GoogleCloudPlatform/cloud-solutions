/**
 * Copyright 2026 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

resource "google_project_service" "target" {
  for_each = toset([
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "compute.googleapis.com",
    "vmmigration.googleapis.com",
    "migrationcenter.googleapis.com",
    "cloudaicompanion.googleapis.com",
    "aiplatform.googleapis.com",
    "orgpolicy.googleapis.com"
  ])
  project            = var.target_project_id
  service            = each.value
  disable_on_destroy = false
}

# Dedicated service accounts for the migrated instance and the Migrate to
# Virtual Machines (M2VM) connector.
resource "google_service_account" "web_app" {
  project      = var.target_project_id
  account_id   = "${var.migrated_instance_name}-sa"
  display_name = "Migrated Web App Service Account"
  depends_on   = [google_project_service.target]
}

resource "google_service_account" "m2vm_connector" {
  project      = var.target_project_id
  account_id   = "m2vm-connector-sa"
  display_name = "Migrate Connector Service Account"
  depends_on   = [google_project_service.target]
}

locals {
  vm_roles = [
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter"
  ]

  connector_roles = [
    "roles/vmmigration.admin"
  ]
}

resource "google_project_iam_member" "web_app_roles" {
  for_each = toset(local.vm_roles)
  project  = var.target_project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.web_app.email}"
}

resource "google_project_iam_member" "connector_roles" {
  for_each = toset(local.connector_roles)
  project  = var.target_project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.m2vm_connector.email}"
}

# The M2VM connector attaches the migrated-VM service account to the instance it creates.
resource "google_service_account_iam_member" "connector_act_as_vm_sa" {
  service_account_id = google_service_account.web_app.id
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.m2vm_connector.email}"
}

# Force the creation of the VM Migration Service Agent.
resource "google_project_service_identity" "vmmigration" {
  provider   = google-beta
  project    = var.target_project_id
  service    = "vmmigration.googleapis.com"
  depends_on = [google_project_service.target]
}

# Authorize the VM Migration Service Agent to attach the service account during test-clone and cutover.
resource "google_service_account_iam_member" "vmmigration_act_as_vm_sa" {
  service_account_id = google_service_account.web_app.id
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_project_service_identity.vmmigration.email}"
}

# Allow M2VM test-clone and cutover instances to receive ephemeral IPs
# when target projects enforce the vmExternalIpAccess list constraint.
resource "google_project_organization_policy" "vm_external_ip_access" {
  project    = var.target_project_id
  constraint = "constraints/compute.vmExternalIpAccess"
  depends_on = [google_project_service.target]

  list_policy {
    allow {
      values = [
        "projects/${var.target_project_id}/zones/${var.zone}/instances/${var.migrated_instance_name}",
      ]
    }
  }
}

# Allow BIOS workloads to boot in Compute Engine when the organization
# enforces the Shielded VM constraint.
resource "google_project_organization_policy" "require_shielded_vm" {
  project    = var.target_project_id
  constraint = "constraints/compute.requireShieldedVm"
  depends_on = [google_project_service.target]

  boolean_policy {
    enforced = false
  }
}

# Allow Migrate Connector to authenticate using service account keys.
resource "google_project_organization_policy" "disable_sa_key_creation" {
  project    = var.target_project_id
  constraint = "constraints/iam.disableServiceAccountKeyCreation"
  depends_on = [google_project_service.target]

  boolean_policy {
    enforced = false
  }
}

# Allow VPC Network Peering between target and source projects.
resource "google_project_organization_policy" "restrict_vpc_peering" {
  project    = var.target_project_id
  constraint = "constraints/compute.restrictVpcPeering"
  depends_on = [google_project_service.target]

  list_policy {
    allow {
      all = true
    }
  }
}

# Wait for Resource Manager org policy changes to propagate to Compute Engine
resource "time_sleep" "wait_for_org_policies" {
  depends_on = [
    google_project_organization_policy.vm_external_ip_access,
    google_project_organization_policy.require_shielded_vm,
    google_project_organization_policy.disable_sa_key_creation,
    google_project_organization_policy.restrict_vpc_peering
  ]
  create_duration = "45s"
}

resource "google_compute_network" "landing_vpc" {
  project                 = var.target_project_id
  name                    = var.network_name
  auto_create_subnetworks = false
  depends_on              = [google_project_service.target]
}

resource "google_compute_subnetwork" "landing_subnet" {
  project       = var.target_project_id
  name          = var.subnetwork_name
  ip_cidr_range = var.subnet_cidr
  region        = var.region
  network       = google_compute_network.landing_vpc.id
}

# Scoped to the migrated VM's service account, not every instance in the VPC.
resource "google_compute_firewall" "allow_http" {
  name                    = "allow-http-webapp"
  network                 = google_compute_network.landing_vpc.name
  source_ranges           = var.allowed_ingress_cidrs
  target_service_accounts = [google_service_account.web_app.email]
  allow {
    protocol = "tcp"
    ports    = [tostring(var.app_port)]
  }
  depends_on = [google_compute_network.landing_vpc, google_service_account.web_app]
}

# Network Load Balancer health checks originate from standard Google Cloud ranges.
resource "google_compute_firewall" "allow_health_checks" {
  name                    = "allow-lb-health-checks"
  network                 = google_compute_network.landing_vpc.name
  source_ranges           = ["35.191.0.0/16", "209.85.152.0/22", "209.85.204.0/22"]
  target_service_accounts = [google_service_account.web_app.email]
  allow {
    protocol = "tcp"
    ports    = [tostring(var.app_port)]
  }
  depends_on = [google_compute_network.landing_vpc, google_service_account.web_app]
}

# SSH access through Identity-Aware Proxy (IAP) tunnel.
resource "google_compute_firewall" "allow_iap_ssh" {
  name                    = "allow-iap-ssh-web-app"
  network                 = google_compute_network.landing_vpc.name
  source_ranges           = ["35.235.240.0/20"]
  target_service_accounts = [google_service_account.web_app.email]
  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
  depends_on = [google_compute_network.landing_vpc, google_service_account.web_app]
}

# Cloud Router and Cloud NAT provide egress for private workloads without
# external IP addresses.
resource "google_compute_router" "router" {
  name       = "landing-router"
  project    = var.target_project_id
  region     = var.region
  network    = google_compute_network.landing_vpc.name
  depends_on = [google_compute_network.landing_vpc]
}

resource "google_compute_router_nat" "nat" {
  name                               = "landing-nat"
  project                            = var.target_project_id
  router                             = google_compute_router.router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

# External passthrough Network Load Balancer. The instance group starts
# empty. You add the migrated instance to this backend service after cutover.
resource "google_compute_address" "lb" {
  name         = "web-app-lb-ip"
  region       = var.region
  address_type = "EXTERNAL"
  depends_on   = [google_project_service.target]
}

resource "google_compute_instance_group" "web" {
  name       = "web-app-group"
  zone       = var.zone
  depends_on = [google_project_service.target]
}

resource "google_compute_region_health_check" "http" {
  name   = "web-app-hc"
  region = var.region
  tcp_health_check {
    port = var.app_port
  }
  depends_on = [google_project_service.target]
}

resource "google_compute_region_backend_service" "web" {
  name                  = "web-app-backend"
  region                = var.region
  load_balancing_scheme = "EXTERNAL"
  protocol              = "TCP"
  health_checks         = [google_compute_region_health_check.http.id]
  backend {
    group          = google_compute_instance_group.web.id
    balancing_mode = "CONNECTION"
  }
}

resource "google_compute_forwarding_rule" "web" {
  name                  = "web-app-fr"
  region                = var.region
  load_balancing_scheme = "EXTERNAL"
  ip_address            = google_compute_address.lb.address
  backend_service       = google_compute_region_backend_service.web.id
  port_range            = tostring(var.app_port)
}

# Simulated hybrid connectivity: VPC Network Peering between landing and bastion VPCs
resource "google_compute_network_peering" "landing_to_bastion" {
  name         = "landing-to-bastion-peering"
  network      = google_compute_network.landing_vpc.id
  peer_network = "projects/${var.source_project_id}/global/networks/${var.source_network_name}"
  depends_on   = [time_sleep.wait_for_org_policies]
}

resource "google_compute_network_peering" "bastion_to_landing" {
  provider     = google.source
  name         = "bastion-to-landing-peering"
  network      = "projects/${var.source_project_id}/global/networks/${var.source_network_name}"
  peer_network = google_compute_network.landing_vpc.id
  depends_on   = [time_sleep.wait_for_org_policies, google_compute_network_peering.landing_to_bastion]
}
