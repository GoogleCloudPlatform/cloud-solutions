# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

locals {
  prod_subnet_name      = "${var.prefix}-prod"
  test_subnet_name      = "${var.prefix}-test"
  test_clone_tag        = "test-clone"
  lb_address_name       = "${var.prefix}-lb-ip"
  enable_tunnels_and_lb = var.ssl_certificate_name != null
  backend_weights       = { azure = 100 - var.gce_weight, gce = var.gce_weight }
}

# --- Project APIs, org policy exception, and foundation ---

module "project" {
  source = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/project?ref=v59.2.0&depth=1"

  name          = var.project_id
  project_reuse = {}
  services = [
    "artifactregistry.googleapis.com",
    "cloudquotas.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
    "iap.googleapis.com",
    "logging.googleapis.com",
    "migrationcenter.googleapis.com",
    "monitoring.googleapis.com",
    "networkconnectivity.googleapis.com",
    "orgpolicy.googleapis.com",
    "servicecontrol.googleapis.com",
    "servicemanagement.googleapis.com",
    "vmmigration.googleapis.com",
  ]
  org_policies = var.vpn_peer_policy_enforced ? {
    "compute.restrictVpnPeerIPs" = {
      rules = [{ allow = { values = var.cross_cloud.azure_vpn_gateway_ips } }]
    }
  } : {}
  # Leave pre-existing Google-managed service agent bindings untouched on destroy.
  service_agents_config = {
    skip_iam = ["compute-system", "migcenter"]
  }
}

module "vpc" {
  source = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/net-vpc?ref=v59.2.0&depth=1"

  project_id   = module.project.project_id
  name         = "${var.prefix}-vpc"
  routing_mode = "GLOBAL"
  subnets = [
    {
      name          = local.prod_subnet_name
      region        = var.region
      ip_cidr_range = var.prod_subnet_cidr
      description   = "Subnet for the migrated VM."
    },
    {
      name          = local.test_subnet_name
      region        = var.region
      ip_cidr_range = var.test_subnet_cidr
      description   = "Isolated subnet for test clones."
    },
  ]
}

module "firewall" {
  source = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/net-vpc-firewall?ref=v59.2.0&depth=1"

  project_id = module.project.project_id
  network    = module.vpc.name
  default_rules_config = {
    disabled = true
  }
  ingress_rules = {
    "${var.prefix}-allow-iap-ssh" = {
      description   = "Allow SSH only through IAP TCP forwarding."
      source_ranges = ["35.235.240.0/20"]
      targets       = [var.network_tag]
      rules         = [{ protocol = "tcp", ports = [22] }]
    }
    "${var.prefix}-allow-lb" = {
      description   = "Allow load balancer health checks and proxied traffic."
      source_ranges = var.cross_cloud.lb_source_ranges
      targets       = [var.network_tag]
      rules         = [{ protocol = "tcp", ports = [var.cross_cloud.app_port] }]
    }
  }
  egress_rules = {
    "${var.prefix}-deny-test-clone-to-azure" = {
      description        = "Deny traffic from test clones to the Azure virtual network."
      deny               = true
      destination_ranges = [var.cross_cloud.azure_vnet_cidr]
      targets            = [local.test_clone_tag]
      rules              = [{ protocol = "all" }]
    }
  }
}

module "nat" {
  source = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/net-cloudnat?ref=v59.2.0&depth=1"

  project_id     = module.project.project_id
  region         = var.region
  name           = "${var.prefix}-nat"
  router_network = module.vpc.name
  logging_filter = "ERRORS_ONLY"
  config_source_subnetworks = {
    all = false
    subnetworks = [{
      self_link = module.vpc.subnet_self_links["${var.region}/${local.prod_subnet_name}"]
    }]
  }
}

module "vm_service_account" {
  source = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/iam-service-account?ref=v59.2.0&depth=1"

  project_id   = module.project.project_id
  name         = "${var.prefix}-vm"
  display_name = "Migrated VM"
  iam_project_roles = {
    (var.project_id) = [
      "roles/logging.logWriter",
      "roles/monitoring.metricWriter",
    ]
  }
}

resource "time_sleep" "m2vm_service_agent" {
  create_duration = "60s"
  depends_on      = [module.project]
}

resource "google_service_account_iam_member" "m2vm_service_agent" {
  service_account_id = module.vm_service_account.id
  role               = "roles/iam.serviceAccountUser"
  member             = module.project.service_agents["vmmigration"].iam_email
  depends_on         = [time_sleep.m2vm_service_agent]
}

resource "google_service_account_iam_member" "operator" {
  service_account_id = module.vm_service_account.id
  role               = "roles/iam.serviceAccountUser"
  member             = var.operator_member
}

module "artifact_registry" {
  source = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/artifact-registry?ref=v59.2.0&depth=1"

  project_id  = module.project.project_id
  location    = var.region
  name        = "${var.prefix}-images"
  description = "Copy of the sample app's container image."
  format = {
    docker = {
      standard = {}
    }
  }
}

# --- HA VPN, Cloud Router BGP, and Network Connectivity Center ---

module "vpn" {
  source = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/net-vpn-ha?ref=v59.2.0&depth=1"

  project_id = module.project.project_id
  region     = var.region
  network    = module.vpc.self_link
  name       = "${var.prefix}-vpn"
  router_config = {
    name = "${var.prefix}-router"
    asn  = var.cross_cloud.cloud_router_asn
    custom_advertise = {
      all_subnets = false
      ip_ranges = merge(
        { (var.prod_subnet_cidr) = "Prod subnet" },
        { for cidr in var.cross_cloud.lb_source_ranges : cidr => "Load balancer and health checks" },
      )
    }
  }
  peer_gateways = local.enable_tunnels_and_lb ? {
    azure = {
      external = {
        name            = "${var.prefix}-azure-gw"
        description     = "Active-active Azure VPN gateway."
        redundancy_type = "TWO_IPS_REDUNDANCY"
        interfaces      = var.cross_cloud.azure_vpn_gateway_ips
      }
    }
  } : {}
  tunnels = local.enable_tunnels_and_lb ? {
    for i in [0, 1] : tostring(i) => {
      name                            = "${var.prefix}-tunnel-${i}"
      peer_gateway                    = "azure"
      peer_external_gateway_interface = i
      vpn_gateway_interface           = i
      peer_router_interface_name      = "${var.prefix}-if-${i}"
      bgp_session_range               = var.cross_cloud.cloud_router_bgp_ips[i]
      shared_secret                   = var.vpn_shared_key
      bgp_peer = {
        name    = "${var.prefix}-bgp-${i}"
        address = var.cross_cloud.azure_bgp_ips[i]
        asn     = var.cross_cloud.azure_bgp_asn
      }
    }
  } : {}
}

resource "google_network_connectivity_hub" "hub" {
  count = local.enable_tunnels_and_lb ? 1 : 0

  project     = module.project.project_id
  name        = "${var.prefix}-hub"
  description = "Hub for the connection to Azure."
}

resource "google_network_connectivity_spoke" "vpn" {
  count = local.enable_tunnels_and_lb ? 1 : 0

  project     = module.project.project_id
  name        = "${var.prefix}-vpn-spoke"
  location    = var.region
  hub         = google_network_connectivity_hub.hub[0].id
  description = "Both HA VPN tunnels to Azure."

  linked_vpn_tunnels {
    uris                       = values(module.vpn.tunnel_self_links)
    site_to_site_data_transfer = false
  }
}

# --- Global external Application Load Balancer, Cloud Armor, and weighted backends ---

module "lb_address" {
  source = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/net-address?ref=v59.2.0&depth=1"

  project_id = module.project.project_id
  global_addresses = {
    lb = {
      name        = local.lb_address_name
      description = "Load balancer static IP."
    }
  }
}

module "cloud_armor" {
  source = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/net-cloud-armor?ref=v59.2.0&depth=1"
  count  = local.enable_tunnels_and_lb ? 1 : 0

  project_id = module.project.project_id
  name       = "${var.prefix}-policy"
  rules = {
    for index, attack in ["sqli", "xss"] : attack => {
      priority = 1000 + index
      action   = "deny(403)"
      match = {
        expression = "evaluatePreconfiguredWaf('${attack}-v422-stable', {'sensitivity': 1})"
      }
    }
  }
}

module "load_balancer" {
  source = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/net-lb-app-ext?ref=v59.2.0&depth=1"
  count  = local.enable_tunnels_and_lb ? 1 : 0

  project_id          = module.project.project_id
  name                = "${var.prefix}-lb"
  use_classic_version = false
  protocol            = "HTTPS"
  forwarding_rules_config = {
    "" = {
      address = module.lb_address.global_addresses[local.lb_address_name].address
    }
  }
  ssl_certificates = {
    certificate_ids = [
      "projects/${module.project.project_id}/global/sslCertificates/${var.ssl_certificate_name}",
    ]
  }
  neg_configs = {
    azure = {
      hybrid = {
        network = module.vpc.self_link
        zone    = var.zone
        endpoints = {
          vm = {
            ip_address = var.cross_cloud.azure_vm_private_ip
            port       = var.cross_cloud.app_port
          }
        }
      }
    }
  }
  group_configs = {
    gce = {
      zone = var.zone
      instances = var.migrated_instance_name == "" ? [] : [
        "https://www.googleapis.com/compute/v1/projects/${module.project.project_id}/zones/${var.zone}/instances/${var.migrated_instance_name}",
      ]
      named_ports = { http = var.cross_cloud.app_port }
    }
  }
  backend_service_configs = {
    azure = {
      backends = [{
        group          = "azure"
        balancing_mode = "RATE"
        max_rate       = { per_endpoint = 100 }
      }]
      protocol        = "HTTP"
      security_policy = module.cloud_armor[0].id
    }
    gce = {
      backends        = [{ group = "gce" }]
      port_name       = "http"
      protocol        = "HTTP"
      security_policy = module.cloud_armor[0].id
    }
  }
  health_check_configs = {
    default = {
      check_interval_sec = 5
      healthy_threshold  = 2
      http = {
        port_specification = "USE_FIXED_PORT"
        port               = var.cross_cloud.app_port
        request_path       = var.health_check_path
      }
    }
  }
  urlmap_config = {
    default_route_action = {
      weighted_backend_services = {
        for backend, weight in local.backend_weights : backend => {
          weight        = weight
          header_action = { response_add = { "X-Served-By" = { value = backend } } }
        }
      }
    }
  }
}
