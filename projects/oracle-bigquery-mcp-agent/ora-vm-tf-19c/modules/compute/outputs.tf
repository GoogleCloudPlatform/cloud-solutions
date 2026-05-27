# Removed public IP output as VM is private

output "oracle_db_private_ip" {
  value       = google_compute_instance.oracle_vm.network_interface[0].network_ip
  description = "Internal Private IP Address of the Oracle database VM"
}


output "vm_instance_id" {
  value       = google_compute_instance.oracle_vm.id
  description = "The unique Google Cloud resource ID identifier of the provisioned Google Compute Engine Oracle virtual machine instance"
}
