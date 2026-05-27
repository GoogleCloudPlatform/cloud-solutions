# Removed public IP output as VM is private

output "oracle_db_private_ip" {
  value       = module.compute.oracle_db_private_ip
  description = "Internal IP address of the Oracle DB VM Instance"
}

output "gcs_bucket_name" {
  value       = local.bucket_name
  description = "The GCS staging bucket name configured or fetched"
}

output "db_password_secret_id" {
  value       = google_secret_manager_secret.db_password_secret.id
  description = "The resource ID identifier of the database password Secret container"
}

output "oracle_db_zone" {
  value       = var.zone
  description = "The Google Cloud Zone where the Oracle database virtual machine is hosted"
}
