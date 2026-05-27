output "oracle_subnet_link" {
  value       = local.subnet_self_link
  description = "The self-link reference of the subnet"
}

output "oracle_subnet_name" {
  value       = local.subnet_name
  description = "The name reference of the subnet"
}

output "oracle_vpc_name" {
  value       = local.vpc_name
  description = "The name reference of the VPC network"
}
