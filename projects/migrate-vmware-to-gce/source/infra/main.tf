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

resource "google_project_service" "required_apis" {
  for_each = toset([
    "cloudresourcemanager.googleapis.com",
    "vmwareengine.googleapis.com",
    "compute.googleapis.com",
    "dns.googleapis.com",
    "iam.googleapis.com",
    "orgpolicy.googleapis.com"
  ])
  project            = var.source_project_id
  service            = each.value
  disable_on_destroy = false
}

# Allow VPC Network Peering across projects and organizations, such as when
# connecting a target landing zone project to this source environment.
resource "google_project_organization_policy" "restrict_vpc_peering" {
  project    = var.source_project_id
  constraint = "constraints/compute.restrictVpcPeering"
  depends_on = [google_project_service.required_apis]

  list_policy {
    allow {
      all = true
    }
  }
}

resource "google_vmwareengine_network" "this" {
  project     = var.source_project_id
  name        = var.vmware_engine_network_name
  location    = "global"
  type        = var.vmware_engine_network_type
  description = "VMware Engine network for the demo private cloud."

  depends_on = [google_project_service.required_apis]
}

# GCVE private cloud. TIME_LIMITED, single node. Provisioning takes 2 to 3
# hours.
resource "google_vmwareengine_private_cloud" "this" {
  project     = var.source_project_id
  location    = var.zone
  name        = var.private_cloud_name
  description = "Demo private cloud — mock on-premises vSphere for VMware to Compute Engine migration."
  type        = var.private_cloud_type

  deletion_delay_hours = var.deletion_delay_hours

  network_config {
    management_cidr       = var.management_cidr
    vmware_engine_network = google_vmwareengine_network.this.id
  }

  management_cluster {
    cluster_id = "${var.private_cloud_name}-mgmt"
    node_type_configs {
      node_type_id = var.node_type_id
      node_count   = var.node_count
    }
  }

  depends_on = [
    google_project_service.required_apis,
    google_vmwareengine_network.this
  ]
}

# Public external address for vCenter access
resource "google_vmwareengine_external_address" "vcenter" {
  name        = "vcenter-public-access"
  parent      = google_vmwareengine_private_cloud.this.id
  internal_ip = google_vmwareengine_private_cloud.this.vcenter[0].internal_ip
  description = "Public IP mapping for vCenter Web UI access"
}

# Public external address for NSX Manager access
resource "google_vmwareengine_external_address" "nsx" {
  name        = "nsx-public-access"
  parent      = google_vmwareengine_private_cloud.this.id
  internal_ip = google_vmwareengine_private_cloud.this.nsx[0].internal_ip
  description = "Public IP mapping for NSX-T Web UI access"
}

# Detect the public IPv4 address of the machine running Terraform. This
# request goes to an external service, so set var.admin_ip_cidr explicitly
# when you run Terraform on a network that cannot reach it.
data "http" "my_ip" {
  count = var.admin_ip_cidr == "" ? 1 : 0
  url   = "https://ifconfig.me/ip"
}

locals {
  # Use var.admin_ip_cidr if provided. Otherwise fall back to the auto-detected IP (/32).
  admin_ip_cidr = var.admin_ip_cidr != "" ? var.admin_ip_cidr : "${chomp(data.http.my_ip[0].response_body)}/32"
}

# Internet egress and external IP service for workloads.
resource "google_vmwareengine_network_policy" "this" {
  project               = var.source_project_id
  location              = var.region
  name                  = "${var.private_cloud_name}-net-policy"
  edge_services_cidr    = var.edge_services_cidr
  vmware_engine_network = google_vmwareengine_network.this.id

  internet_access {
    enabled = true
  }

  external_ip {
    enabled = true
  }

  depends_on = [google_vmwareengine_network.this]
}

# Public IP -> internal IP NAT mapping for the demo workload.
resource "google_vmwareengine_external_address" "web_app" {
  name        = "web-app-01"
  parent      = google_vmwareengine_private_cloud.this.id
  internal_ip = var.web_app_internal_ip
  description = "Public entry point for the demo workload."

  depends_on = [google_vmwareengine_network_policy.this]
}

# Ensure all external access rules finish deleting and GCVE NetworkPolicy
# reconciles before Terraform attempts to delete the underlying ExternalAddresses.
resource "time_sleep" "wait_for_external_access_rules" {
  destroy_duration = "30s"

  depends_on = [
    google_vmwareengine_network_policy.this,
    google_vmwareengine_external_address.web_app,
    google_vmwareengine_external_address.vcenter,
    google_vmwareengine_external_address.nsx
  ]
}

# Allow external inbound HTTP traffic to the web app workload.
resource "google_vmwareengine_external_access_rule" "allow_web_app" {
  name              = "allow-web-app"
  parent            = google_vmwareengine_network_policy.this.id
  priority          = 100
  action            = "ALLOW"
  ip_protocol       = "TCP"
  source_ports      = ["1-65535"]
  destination_ports = [tostring(var.web_app_port)]

  dynamic "source_ip_ranges" {
    for_each = var.web_app_allowed_source_cidrs
    content {
      ip_address_range = source_ip_ranges.value
    }
  }

  destination_ip_ranges {
    external_address = google_vmwareengine_external_address.web_app.id
  }

  depends_on = [
    time_sleep.wait_for_external_access_rules
  ]
}

locals {
  management_access_rules = {
    vcenter = {
      name             = "allow-vcenter"
      priority         = 101
      external_address = google_vmwareengine_external_address.vcenter.id
    }
    nsx = {
      name             = "allow-nsx"
      priority         = 102
      external_address = google_vmwareengine_external_address.nsx.id
    }
  }
}

resource "google_vmwareengine_external_access_rule" "management_access" {
  for_each = local.management_access_rules

  name              = each.value.name
  parent            = google_vmwareengine_network_policy.this.id
  priority          = each.value.priority
  action            = "ALLOW"
  ip_protocol       = "TCP"
  source_ports      = ["1-65535"]
  destination_ports = ["443"]

  source_ip_ranges {
    ip_address_range = local.admin_ip_cidr
  }

  destination_ip_ranges {
    external_address = each.value.external_address
  }

  depends_on = [
    time_sleep.wait_for_external_access_rules
  ]
}

resource "google_compute_network" "bastion_vpc" {
  project                 = var.source_project_id
  name                    = var.bastion_network_name
  auto_create_subnetworks = false
  depends_on              = [google_project_service.required_apis]
}

resource "google_compute_subnetwork" "bastion_subnet" {
  project       = var.source_project_id
  name          = var.bastion_subnetwork_name
  ip_cidr_range = var.bastion_subnet_cidr
  region        = var.region
  network       = google_compute_network.bastion_vpc.id
}

# Allow SSH (22) from the Identity-Aware Proxy (IAP) range 35.235.240.0/20.
resource "google_compute_firewall" "allow_iap_ssh" {
  project = var.source_project_id
  name    = "bastion-allow-iap-ssh"
  network = google_compute_network.bastion_vpc.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["35.235.240.0/20"]
  depends_on    = [google_compute_network.bastion_vpc]
}

# Peer VMware Engine Network to Bastion VPC
resource "google_vmwareengine_network_peering" "bastion_peering" {
  name                  = "bastion-peering"
  project               = var.source_project_id
  vmware_engine_network = google_vmwareengine_network.this.id
  peer_network          = google_compute_network.bastion_vpc.id
  peer_network_type     = "STANDARD"
  export_custom_routes  = true
  import_custom_routes  = true

  depends_on = [
    google_vmwareengine_network.this,
    google_compute_network.bastion_vpc
  ]
}

# Dedicated service account for linux-bastion so Terraform on the bastion can
# retrieve vCenter and NSX-T credentials.
resource "google_service_account" "bastion" {
  project      = var.source_project_id
  account_id   = "bastion-sa"
  display_name = "Linux Bastion Host Service Account"
  depends_on   = [google_project_service.required_apis]
}

# roles/vmwareengine.viewer omits the credential permissions, and
# roles/vmwareengine.editor grants write access that the demo never uses. Grant
# only the permissions that the single-tier-workload module calls.
#
# Google reserves a deleted custom role ID for 37 days. Suffixing the role ID
# with the private cloud name rotates it alongside the name bump that the
# teardown instructions already describe.
resource "google_project_iam_custom_role" "gcve_credentials_reader" {
  project     = var.source_project_id
  role_id     = "gcveCredentialsReader_${replace(var.private_cloud_name, "-", "_")}"
  title       = "GCVE Credentials Reader"
  description = "Read private cloud metadata and vCenter and NSX-T credentials."
  permissions = [
    "vmwareengine.privateClouds.get",
    "vmwareengine.privateClouds.showNsxCredentials",
    "vmwareengine.privateClouds.showVcenterCredentials",
  ]
  depends_on = [google_project_service.required_apis]
}

resource "google_project_iam_member" "bastion_gcve_credentials" {
  project = var.source_project_id
  role    = google_project_iam_custom_role.gcve_credentials_reader.id
  member  = "serviceAccount:${google_service_account.bastion.email}"
}

# IAM bindings are eventually consistent. Wait before the bastion boots and
# Terraform running on it reads the vCenter and NSX-T credentials.
resource "time_sleep" "wait_for_bastion_iam" {
  depends_on      = [google_project_iam_member.bastion_gcve_credentials]
  create_duration = "60s"
}

# Linux jump host: Ubuntu 22.04 LTS instance for management access
resource "google_compute_instance" "linux_bastion" {
  project      = var.source_project_id
  name         = "linux-bastion"
  machine_type = var.bastion_machine_type
  zone         = var.zone

  boot_disk {
    initialize_params {
      image = var.bastion_image
      size  = var.bastion_disk_size_gb
    }
  }

  network_interface {
    network    = google_compute_network.bastion_vpc.name
    subnetwork = google_compute_subnetwork.bastion_subnet.name
  }

  service_account {
    email  = google_service_account.bastion.email
    scopes = ["cloud-platform"]
  }

  metadata = {
    startup-script = <<-EOT
      #!/bin/bash
      apt-get update -qq && apt-get install -y -qq gnupg software-properties-common curl
      curl -fsSL https://apt.releases.hashicorp.com/gpg | gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
      echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com jammy main" > /etc/apt/sources.list.d/hashicorp.list
      apt-get update -qq && apt-get install -y -qq terraform
    EOT
  }

  depends_on = [
    google_project_service.required_apis,
    google_compute_router_nat.bastion_nat,
    google_vmwareengine_network_peering.bastion_peering,
    google_compute_firewall.allow_iap_ssh,
    time_sleep.wait_for_bastion_iam
  ]
}

# Cloud DNS Inbound Server Policy for enterprise on-premises DNS forwarding.
# Enables corporate DNS servers across a Cloud VPN or Cloud Interconnect
# connection to query Cloud DNS for gve.goog and resolve VMware Engine
# management appliances.
resource "google_dns_policy" "inbound" {
  project                   = var.source_project_id
  name                      = "gve-inbound-dns"
  description               = "Inbound DNS forwarding policy for VMware Engine management access"
  enable_inbound_forwarding = true

  networks {
    network_url = google_compute_network.bastion_vpc.id
  }

  depends_on = [
    google_project_service.required_apis,
    google_compute_network.bastion_vpc
  ]
}

# Forward all *.gve.goog queries to the GCVE internal DNS server
resource "google_dns_managed_zone" "gve_forwarding" {
  project     = var.source_project_id
  name        = "gve-goog-forwarding"
  dns_name    = "gve.goog."
  description = "Forwarding zone for GCVE appliances"
  visibility  = "private"

  private_visibility_config {
    networks {
      network_url = google_compute_network.bastion_vpc.id
    }
  }

  forwarding_config {
    target_name_servers {
      ipv4_address = google_vmwareengine_private_cloud.this.network_config[0].dns_server_ip
    }
  }

  depends_on = [
    google_project_service.required_apis,
    google_vmwareengine_private_cloud.this,
    google_compute_network.bastion_vpc
  ]
}

# Cloud Router and Cloud NAT for bastion-vpc outbound traffic, such as
# package updates.
resource "google_compute_router" "bastion_router" {
  project    = var.source_project_id
  name       = "bastion-router"
  region     = var.region
  network    = google_compute_network.bastion_vpc.id
  depends_on = [google_compute_network.bastion_vpc]
}

resource "google_compute_router_nat" "bastion_nat" {
  project                            = var.source_project_id
  name                               = "bastion-nat"
  router                             = google_compute_router.bastion_router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}

# In-VPC client VM in the source environment that continuously tests and
# observes the DNS cutover.
resource "google_service_account" "demo_client" {
  project      = var.source_project_id
  account_id   = "demo-client-sa"
  display_name = "DNS demo watcher VM SA"
  depends_on   = [google_project_service.required_apis]
}

resource "google_compute_instance" "demo_client" {
  project      = var.source_project_id
  name         = "demo-client"
  zone         = var.zone
  machine_type = var.demo_client_machine_type

  boot_disk {
    initialize_params {
      image = var.demo_client_image
    }
  }

  network_interface {
    network    = google_compute_network.bastion_vpc.name
    subnetwork = google_compute_subnetwork.bastion_subnet.name
  }

  shielded_instance_config {
    enable_secure_boot = true
  }

  service_account {
    email  = google_service_account.demo_client.email
    scopes = ["cloud-platform"]
  }

  metadata_startup_script = <<-EOT
    #!/bin/bash
    # Allow startup script to continue even if package index update fails (e.g. transient network issues)
    apt-get update -qq && apt-get install -y -qq curl dnsutils || true
    cat > /usr/local/bin/demo-watch.sh << 'SCRIPT'
    #!/bin/bash
    set -u
    FQDN="www.${trimsuffix(var.dns_domain, ".")}"

    while true; do
      IP=$(getent hosts "$FQDN" | awk '{print $1}' | head -1)
      if OUT=$(curl -sf -w " (%%{time_total}s)" --max-time 3 "http://$FQDN/"); then
        BODY=$(echo "$OUT" | tr -d '\n')
      else
        BODY="(no response)"
      fi
      echo "$(date +%T)  $FQDN -> $${IP:-no-answer}   $BODY"
      sleep 2
    done
    SCRIPT
    chmod +x /usr/local/bin/demo-watch.sh
    nohup /usr/local/bin/demo-watch.sh >> /var/log/demo-watch.log 2>&1 &
  EOT

  depends_on = [
    google_compute_network.bastion_vpc,
    google_compute_subnetwork.bastion_subnet,
    google_compute_router_nat.bastion_nat,
    google_compute_firewall.allow_iap_ssh
  ]
}

# Authoritative private Cloud DNS zone for the demo workload in the source project
resource "google_dns_managed_zone" "demo_zone" {
  project     = var.source_project_id
  name        = "vmware-demo-zone"
  dns_name    = var.dns_domain
  description = "Private DNS zone for VMware migration demo"
  visibility  = "private"

  private_visibility_config {
    networks {
      network_url = google_compute_network.bastion_vpc.id
    }
  }

  depends_on = [
    google_project_service.required_apis,
    google_compute_network.bastion_vpc
  ]
}

resource "google_dns_record_set" "demo_app" {
  project      = var.source_project_id
  managed_zone = google_dns_managed_zone.demo_zone.name
  name         = "www.${var.dns_domain}"
  type         = "A"
  ttl          = var.dns_record_ttl
  rrdatas      = [google_vmwareengine_external_address.web_app.external_ip]
}
