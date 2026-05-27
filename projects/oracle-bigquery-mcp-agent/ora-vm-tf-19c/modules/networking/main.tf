# Read existing VPC details if create_vpc is false
data "google_compute_network" "existing_vpc" {
  count   = var.create_vpc ? 0 : 1
  name    = var.vpc_name
  project = var.project_id
}

# Provision new VPC network if create_vpc is true
resource "google_compute_network" "oracle_vpc" {
  count                   = var.create_vpc ? 1 : 0
  name                    = var.vpc_name
  auto_create_subnetworks = false
  project                 = var.project_id
}

# Read existing Subnetwork details if create_subnetwork is false
data "google_compute_subnetwork" "existing_subnet" {
  count   = var.create_subnetwork ? 0 : 1
  name    = var.subnetwork_name
  region  = var.region
  project = var.project_id
}

# Provision new Subnetwork if create_subnetwork is true
resource "google_compute_subnetwork" "oracle_subnet" {
  count                    = var.create_subnetwork ? 1 : 0
  name                     = var.subnetwork_name
  ip_cidr_range            = "10.0.1.0/24"
  region                   = var.region
  network                  = local.vpc_id
  project                  = var.project_id
  private_ip_google_access = true
}

# Consolidate network & subnet pointers
locals {
  vpc_id           = var.create_vpc ? google_compute_network.oracle_vpc[0].id : data.google_compute_network.existing_vpc[0].id
  vpc_name         = var.create_vpc ? google_compute_network.oracle_vpc[0].name : data.google_compute_network.existing_vpc[0].name
  subnet_self_link = var.create_subnetwork ? google_compute_subnetwork.oracle_subnet[0].self_link : data.google_compute_subnetwork.existing_subnet[0].self_link
  subnet_name      = var.create_subnetwork ? google_compute_subnetwork.oracle_subnet[0].name : data.google_compute_subnetwork.existing_subnet[0].name
  subnet_cidr      = var.create_subnetwork ? google_compute_subnetwork.oracle_subnet[0].ip_cidr_range : data.google_compute_subnetwork.existing_subnet[0].ip_cidr_range
}

resource "google_compute_firewall" "allow_ssh_sqlplus" {
  name    = "allow-ssh-sqlplus"
  network = local.vpc_name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["22", "1521"]
  }

  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["oracle-server"]
}

resource "google_compute_firewall" "allow_internal_sqlplus" {
  name    = "allow-internal-sqlplus"
  network = local.vpc_name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["1521"]
  }

  source_ranges = [local.subnet_cidr]
  target_tags   = ["oracle-server"]
}

resource "google_compute_router" "nat_router" {
  name    = "oracle-nat-router"
  network = local.vpc_id
  region  = var.region
  project = var.project_id
}

resource "google_compute_router_nat" "nat_gateway" {
  name                               = "oracle-nat-gateway"
  router                             = google_compute_router.nat_router.name
  region                             = var.region
  project                            = var.project_id
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}
