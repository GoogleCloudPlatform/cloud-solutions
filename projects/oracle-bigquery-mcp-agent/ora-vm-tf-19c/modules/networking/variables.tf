variable "project_id" {
  type        = string
  description = "The Google Cloud Project ID where the VPC network will be provisioned"
}

variable "region" {
  type        = string
  description = "The target Google Cloud Region for allocating subnetworks and routers"
}

variable "create_vpc" {
  type        = bool
  default     = true
  description = "Toggle to dynamically create a new VPC network"
}

variable "create_subnetwork" {
  type        = bool
  default     = true
  description = "Toggle to dynamically create a new Subnetwork"
}

variable "vpc_name" {
  type        = string
  default     = "oracle-vpc"
  description = "The VPC network name"
}

variable "subnetwork_name" {
  type        = string
  default     = "oracle-subnet"
  description = "The subnetwork name"
}
