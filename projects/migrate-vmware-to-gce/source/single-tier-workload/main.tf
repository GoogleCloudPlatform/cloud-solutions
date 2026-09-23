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

data "terraform_remote_state" "source" {
  backend = "local"
  config = {
    path = var.source_state_path
  }
}

locals {
  project_id         = data.terraform_remote_state.source.outputs.project_id
  region             = data.terraform_remote_state.source.outputs.region
  zone               = data.terraform_remote_state.source.outputs.zone
  private_cloud_name = data.terraform_remote_state.source.outputs.private_cloud_name
  cluster_name       = data.terraform_remote_state.source.outputs.cluster_name
  vm_ip              = data.terraform_remote_state.source.outputs.web_app_internal_ip
  web_app_public_ip  = data.terraform_remote_state.source.outputs.web_app_public_ip

  # Derived from the segment CIDR declared in source/infra.
  gateway_ip = split("/", var.segment_gateway_cidr)[0]

  cloud_init = <<-EOT
    #cloud-config
    hostname: ${var.vm_name}
    ssh_pwauth: false
    write_files:
      # Static IP — no DHCP on the NSX segment.
      - path: /etc/netplan/99-static.yaml
        permissions: "0600"
        content: |
          network:
            version: 2
            ethernets:
              default:
                match:
                  name: e*
                addresses:
                  - ${local.vm_ip}/24
                routes:
                  - to: default
                    via: ${local.gateway_ip}
                nameservers:
                  addresses: [${join(", ", var.vm_dns_servers)}]
      # nginx site — staged here, copied into place after nginx installs.
      - path: /opt/demo/nginx-default
        content: |
          server {
            listen 80 default_server;
            location / {
              default_type application/json;
              return 200 '{"message": "Hello World"}\n';
            }
          }
    runcmd:
      # drop the image's DHCP netplan so it stops racing the static config
      - rm -f /etc/netplan/50-cloud-init.yaml
      - netplan apply
      # retry loop: one apt mirror hiccup must not silently kill the demo
      - |
        for i in 1 2 3 4 5; do
          apt-get update -o Acquire::Retries=3 &&
          DEBIAN_FRONTEND=noninteractive apt-get install -y nginx open-vm-tools && break
          echo "apt attempt $i failed; retrying in 15s" && sleep 15
        done
      - cp /opt/demo/nginx-default /etc/nginx/sites-available/default
      - systemctl restart nginx
  EOT
}

data "google_vmwareengine_private_cloud" "this" {
  project  = local.project_id
  location = local.zone
  name     = local.private_cloud_name
}

data "google_vmwareengine_nsx_credentials" "this" {
  parent = data.google_vmwareengine_private_cloud.this.id
}

data "google_vmwareengine_vcenter_credentials" "this" {
  parent = data.google_vmwareengine_private_cloud.this.id
}

# Look up pre-provisioned GCVE NSX-T gateways and zones
data "nsxt_policy_tier1_gateway" "tier1" {
  display_name = "Tier1"
}

data "nsxt_policy_transport_zone" "overlay" {
  display_name = "TZ-OVERLAY"
}

data "nsxt_policy_service" "http" {
  display_name = "HTTP"
}

# Workload segment
resource "nsxt_policy_segment" "workload" {
  display_name        = var.segment_name
  connectivity_path   = data.nsxt_policy_tier1_gateway.tier1.path
  transport_zone_path = data.nsxt_policy_transport_zone.overlay.path

  subnet {
    cidr = var.segment_gateway_cidr
  }
}

# Destination group: scoped to the demo workload VM
resource "nsxt_policy_group" "web_app" {
  display_name = "demo-web-app"
  criteria {
    ipaddress_expression {
      ip_addresses = [local.vm_ip]
    }
  }
}

# Allow HTTP through the Tier1 gateway, scoped to the workload VM.
resource "nsxt_policy_gateway_policy" "web" {
  display_name = "demo-web"
  category     = "LocalGatewayRules"

  rule {
    display_name       = "allow-http-webapp"
    action             = "ALLOW"
    services           = [data.nsxt_policy_service.http.path]
    destination_groups = [nsxt_policy_group.web_app.path]
    scope              = [data.nsxt_policy_tier1_gateway.tier1.path]
  }

  depends_on = [
    nsxt_policy_segment.workload,
    nsxt_policy_group.web_app
  ]
}

data "vsphere_datacenter" "dc" {
  name = var.datacenter_name
}

data "vsphere_compute_cluster" "cluster" {
  name          = local.cluster_name
  datacenter_id = data.vsphere_datacenter.dc.id
}

data "vsphere_datastore" "vsan" {
  name          = var.datastore_name
  datacenter_id = data.vsphere_datacenter.dc.id
}

# Wait for vCenter to synchronize the newly created NSX-T segment into its inventory
resource "time_sleep" "wait_for_vcenter_sync" {
  depends_on      = [nsxt_policy_segment.workload]
  create_duration = "45s"
}

data "vsphere_network" "workload" {
  name          = var.segment_name
  datacenter_id = data.vsphere_datacenter.dc.id
  depends_on    = [time_sleep.wait_for_vcenter_sync]
}

# Ubuntu image content library
resource "vsphere_content_library" "demo" {
  name            = "demo-library"
  storage_backing = [data.vsphere_datastore.vsan.id]
}

resource "vsphere_content_library_item" "ubuntu" {
  name        = "ubuntu-jammy-cloudimg"
  library_id  = vsphere_content_library.demo.id
  type        = "ovf"
  file_url    = var.ubuntu_ova_url
  description = "Ubuntu 22.04 cloud image."

  depends_on = [vsphere_content_library.demo]
}

# Wait for vCenter Content Library to finish streaming the Ubuntu OVA into vsanDatastore
resource "time_sleep" "wait_for_ova_import" {
  depends_on      = [vsphere_content_library_item.ubuntu]
  create_duration = "90s"
}

# Workload VM
resource "vsphere_virtual_machine" "web_app" {
  name             = var.vm_name
  folder           = var.vsphere_folder
  resource_pool_id = data.vsphere_compute_cluster.cluster.resource_pool_id
  datastore_id     = data.vsphere_datastore.vsan.id

  num_cpus = var.vm_cpus
  memory   = var.vm_memory_mb
  guest_id = var.vm_guest_id

  network_interface {
    network_id = data.vsphere_network.workload.id
  }

  cdrom {
    client_device = true
  }

  disk {
    label            = "disk0"
    size             = var.vm_disk_size_gb
    thin_provisioned = var.vm_disk_thin_provisioned
  }

  clone {
    template_uuid = vsphere_content_library_item.ubuntu.id
  }

  vapp {
    properties = {
      "instance-id" = var.vm_name
      "hostname"    = var.vm_name
      "user-data"   = base64encode(local.cloud_init)
    }
  }

  wait_for_guest_net_timeout = 0
  wait_for_guest_ip_timeout  = 0

  depends_on = [
    nsxt_policy_gateway_policy.web,
    time_sleep.wait_for_ova_import,
    data.vsphere_network.workload
  ]
}
