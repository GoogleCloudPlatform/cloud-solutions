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

data "azurerm_subscription" "current" {}

data "azuread_client_config" "current" {}

locals {
  vnet_cidr        = "10.20.0.0/16"
  vm_private_ip    = "10.20.1.10"
  lb_source_ranges = ["35.191.0.0/16", "130.211.0.0/22"]
  app_port         = 80

  cloud_init = join("\n", [
    "#cloud-config",
    yamlencode({
      write_files = [{
        path        = "/opt/sample-app/vm_setup.sh"
        encoding    = "b64"
        content     = filebase64("${path.module}/vm_setup.sh")
        permissions = "0755"
      }]
      runcmd = [["/opt/sample-app/vm_setup.sh"]]
    }),
  ])

  app_roles = {
    discovery = azurerm_role_definition.discovery.role_definition_resource_id
    m2vm      = azurerm_role_definition.m2vm.role_definition_resource_id
  }
}

# --- Source network and VM ---

resource "azurerm_resource_group" "source" {
  name     = "${var.prefix}-rg"
  location = var.location
}

resource "azurerm_virtual_network" "source" {
  name                = "${var.prefix}-vnet"
  address_space       = [local.vnet_cidr]
  location            = azurerm_resource_group.source.location
  resource_group_name = azurerm_resource_group.source.name
}

resource "azurerm_subnet" "source" {
  name                 = "${var.prefix}-subnet"
  resource_group_name  = azurerm_resource_group.source.name
  virtual_network_name = azurerm_virtual_network.source.name
  address_prefixes     = ["10.20.1.0/24"]
}

resource "azurerm_network_security_group" "source" {
  name                = "${var.prefix}-nsg"
  location            = azurerm_resource_group.source.location
  resource_group_name = azurerm_resource_group.source.name

  security_rule {
    name                       = "allow-lb-http"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = tostring(local.app_port)
    source_address_prefixes    = local.lb_source_ranges
    destination_address_prefix = local.vm_private_ip
  }

  # Block default VirtualNetwork inbound traffic except load balancer probes.
  security_rule {
    name                       = "deny-vnet-inbound"
    priority                   = 4096
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "*"
  }
}

resource "azurerm_subnet_network_security_group_association" "source" {
  subnet_id                 = azurerm_subnet.source.id
  network_security_group_id = azurerm_network_security_group.source.id
}

# Provides outbound internet access for first-boot package and container pulls
# without deploying an Azure NAT Gateway. Use Azure NAT Gateway in production.
resource "azurerm_public_ip" "source" {
  name                = "${var.prefix}-ip"
  location            = azurerm_resource_group.source.location
  resource_group_name = azurerm_resource_group.source.name
  allocation_method   = "Static"
  sku                 = "Standard"
}

resource "azurerm_network_interface" "source" {
  name                = "${var.prefix}-nic"
  location            = azurerm_resource_group.source.location
  resource_group_name = azurerm_resource_group.source.name

  ip_configuration {
    name                          = "primary"
    subnet_id                     = azurerm_subnet.source.id
    private_ip_address_allocation = "Static"
    private_ip_address            = local.vm_private_ip
    public_ip_address_id          = azurerm_public_ip.source.id
  }
}

resource "azurerm_linux_virtual_machine" "source" {
  name                            = "${var.prefix}-vm"
  computer_name                   = "web-01"
  location                        = azurerm_resource_group.source.location
  resource_group_name             = azurerm_resource_group.source.name
  size                            = var.vm_size
  admin_username                  = var.admin_username
  disable_password_authentication = true
  network_interface_ids           = [azurerm_network_interface.source.id]
  custom_data                     = base64encode(local.cloud_init)

  # Keep the Gen2 source a standard UEFI VM instead of Trusted Launch.
  secure_boot_enabled = false
  vtpm_enabled        = false

  admin_ssh_key {
    username   = var.admin_username
    public_key = var.ssh_public_key
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "StandardSSD_LRS"
    disk_size_gb         = 30
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = "latest"
  }

  tags = {
    app = "aspnetcore-sample"
  }
}

# Migrate to Virtual Machines reads snapshots over public SAS endpoints.
resource "azurerm_managed_disk" "data" {
  name                          = "${var.prefix}-data"
  location                      = azurerm_resource_group.source.location
  resource_group_name           = azurerm_resource_group.source.name
  storage_account_type          = "StandardSSD_LRS"
  create_option                 = "Empty"
  disk_size_gb                  = var.data_disk_size_gb
  network_access_policy         = "AllowAll"
  public_network_access_enabled = true
}

resource "azurerm_virtual_machine_data_disk_attachment" "data" {
  managed_disk_id    = azurerm_managed_disk.data.id
  virtual_machine_id = azurerm_linux_virtual_machine.source.id
  lun                = 0
  caching            = "ReadWrite"
}

# --- Entra ID app registrations and custom roles ---

# Migrate to Virtual Machines requires subscription-level permissions to
# validate the Azure source and manage its temporary m2vm-* snapshot resource
# group. Use a dedicated subscription for this role.
resource "azurerm_role_definition" "m2vm" {
  name        = "${var.prefix} Migrate to Virtual Machines (${data.azurerm_subscription.current.subscription_id})"
  scope       = data.azurerm_subscription.current.id
  description = "Azure permissions for Migrate to Virtual Machines."

  permissions {
    actions = [
      "Microsoft.Resources/subscriptions/resourceGroups/write",
      "Microsoft.Resources/subscriptions/resourceGroups/read",
      "Microsoft.Resources/subscriptions/resourceGroups/delete",
      "Microsoft.Compute/virtualMachines/read",
      "Microsoft.Compute/virtualMachines/write",
      "Microsoft.Compute/virtualMachines/deallocate/action",
      "Microsoft.Compute/disks/read",
      "Microsoft.Compute/restorePointCollections/read",
      "Microsoft.Compute/restorePointCollections/write",
      "Microsoft.Compute/restorePointCollections/delete",
      "Microsoft.Compute/restorePointCollections/restorePoints/read",
      "Microsoft.Compute/restorePointCollections/restorePoints/write",
      "Microsoft.Compute/restorePointCollections/restorePoints/delete",
      "Microsoft.Compute/restorePointCollections/restorePoints/diskRestorePoints/read",
      "Microsoft.Compute/restorePointCollections/restorePoints/diskRestorePoints/beginGetAccess/action",
      "Microsoft.Compute/restorePointCollections/restorePoints/diskRestorePoints/endGetAccess/action",
      "Microsoft.Compute/snapshots/delete",
      "Microsoft.Compute/snapshots/write",
      "Microsoft.Compute/snapshots/read",
      "Microsoft.Compute/snapshots/beginGetAccess/action",
      "Microsoft.Compute/snapshots/endGetAccess/action",
    ]
  }

  assignable_scopes = [data.azurerm_subscription.current.id]
}

resource "azurerm_role_definition" "discovery" {
  name        = "${var.prefix} Migration Center discovery (${data.azurerm_subscription.current.subscription_id})"
  scope       = data.azurerm_subscription.current.id
  description = "Read-only Azure permissions for the Migration Center discovery client."

  permissions {
    actions = [
      "Microsoft.Compute/virtualMachines/read",
      "Microsoft.Compute/disks/read",
      "Microsoft.Insights/MetricDefinitions/read",
      "Microsoft.Insights/Metrics/Read",
      "Microsoft.Network/networkInterfaces/read",
    ]
  }

  assignable_scopes = [data.azurerm_subscription.current.id]
}

resource "azuread_application" "migration" {
  for_each = local.app_roles

  display_name = "${var.prefix}-${each.key}-${substr(data.azurerm_subscription.current.subscription_id, 0, 8)}"
  owners       = [data.azuread_client_config.current.object_id]
}

resource "azuread_service_principal" "migration" {
  for_each = azuread_application.migration

  client_id = each.value.client_id
  owners    = [data.azuread_client_config.current.object_id]
}

resource "azurerm_role_assignment" "migration" {
  for_each = local.app_roles

  scope              = data.azurerm_subscription.current.id
  role_definition_id = each.value
  principal_id       = azuread_service_principal.migration[each.key].object_id
  principal_type     = "ServicePrincipal"
}

# --- Active-active VPN gateway and connections ---

resource "azurerm_subnet" "gateway" {
  name                 = "GatewaySubnet"
  resource_group_name  = azurerm_resource_group.source.name
  virtual_network_name = azurerm_virtual_network.source.name
  address_prefixes     = ["10.20.255.0/27"]
}

resource "azurerm_public_ip" "vpn_gateway" {
  count = 2

  name                = "${var.prefix}-vpn-gw-ip-${count.index}"
  location            = azurerm_resource_group.source.location
  resource_group_name = azurerm_resource_group.source.name
  allocation_method   = "Static"
  sku                 = "Standard"
}

resource "azurerm_virtual_network_gateway" "vpn" {
  name                = "${var.prefix}-vpn-gw"
  location            = azurerm_resource_group.source.location
  resource_group_name = azurerm_resource_group.source.name
  type                = "Vpn"
  vpn_type            = "RouteBased"
  sku                 = "VpnGw1AZ"
  generation          = "Generation1"
  active_active       = true
  bgp_enabled         = true

  dynamic "ip_configuration" {
    for_each = azurerm_public_ip.vpn_gateway

    content {
      name                          = "ipconfig-${ip_configuration.key}"
      public_ip_address_id          = ip_configuration.value.id
      private_ip_address_allocation = "Dynamic"
      subnet_id                     = azurerm_subnet.gateway.id
    }
  }

  bgp_settings {
    asn = var.azure_bgp_asn

    dynamic "peering_addresses" {
      for_each = var.azure_bgp_ips

      content {
        ip_configuration_name = "ipconfig-${peering_addresses.key}"
        apipa_addresses       = [peering_addresses.value]
      }
    }
  }
}

resource "azurerm_local_network_gateway" "ha_vpn" {
  count = var.ha_vpn_interface_ips != null ? 2 : 0

  name                = "${var.prefix}-ha-vpn-${count.index}"
  location            = azurerm_resource_group.source.location
  resource_group_name = azurerm_resource_group.source.name
  gateway_address     = var.ha_vpn_interface_ips[count.index]

  bgp_settings {
    asn                 = var.cloud_router_asn
    bgp_peering_address = split("/", var.cloud_router_bgp_ips[count.index])[0]
  }
}

resource "azurerm_virtual_network_gateway_connection" "ha_vpn" {
  count = var.ha_vpn_interface_ips != null ? 2 : 0

  name                       = "${var.prefix}-vpn-conn-${count.index}"
  location                   = azurerm_resource_group.source.location
  resource_group_name        = azurerm_resource_group.source.name
  type                       = "IPsec"
  virtual_network_gateway_id = azurerm_virtual_network_gateway.vpn.id
  local_network_gateway_id   = azurerm_local_network_gateway.ha_vpn[count.index].id
  connection_protocol        = "IKEv2"
  bgp_enabled                = true
  shared_key                 = var.vpn_shared_key
}
