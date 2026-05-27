variable "project_id" {
  type        = string
  description = "The Google Cloud Project ID"
}

variable "zone" {
  type        = string
  default     = "us-central1-a"
  description = "The Google Cloud Zone where the GCE Oracle VM is hosted"
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "Google Cloud Region"
}

variable "vpc_name" {
  type        = string
  default     = "oracle-vpc"
  description = "The VPC name where Oracle is deployed"
}



variable "datastream_private_ip_range" {
  type        = string
  default     = "10.0.2.0/29"
  description = "Non-overlapping CIDR range for Datastream private connectivity subnet"
}



variable "oracle_db_user" {
  type        = string
  default     = "c##datastream"
  description = "Datastream database username in Oracle"
}



variable "oracle_vm_name" {
  type        = string
  default     = "oracle-db-19c"
  description = "The GCE VM instance name of the source Oracle Database"
}

variable "oracle_schema" {
  type        = string
  default     = "RB_INTEL_LEDGER_19C"
  description = "The target Oracle schema to replicate CDC transactions from"
}

variable "db_password" {
  type        = string
  sensitive   = true
  description = "Datastream database password in Oracle"
}
