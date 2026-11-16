# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

output "project_id" {
  description = "Google Cloud project ID hosting the migration demo resources."
  value       = data.google_project.target.project_id
}

output "region" {
  description = "Google Cloud region of the subnetwork and snapshot schedule."
  value       = google_compute_subnetwork.migration.region
}

output "zone" {
  description = "Google Cloud zone of the source Gen2 Compute Engine instance and disks."
  value       = google_compute_instance.source.zone
}

output "source_vm_name" {
  description = "Name of the baseline Gen2 Compute Engine instance."
  value       = google_compute_instance.source.name
}

output "boot_disk_source" {
  description = "Self-link of the boot Persistent Disk attached to the baseline Gen2 instance."
  value       = google_compute_instance.source.boot_disk[0].source
}

output "data_disk_name" {
  description = "Name of the attached pd-ssd data Persistent Disk."
  value       = google_compute_disk.app_data.name
}

output "snapshot_policy_name" {
  description = "Name of the daily snapshot schedule resource policy attached to the data disk."
  value       = google_compute_resource_policy.daily_snapshots.name
}

output "iap_ssh_command" {
  description = "gcloud SSH command using Identity-Aware Proxy tunneling to inspect the guest OS."
  value       = "gcloud compute ssh ${google_compute_instance.source.name} --project=${google_compute_instance.source.project} --zone=${google_compute_instance.source.zone} --tunnel-through-iap"
}

output "multi_disk_vm_name" {
  description = "Name of the second Gen2 Compute Engine instance with multiple attached Persistent Disks."
  value       = google_compute_instance.multi_disk_source.name
}

output "multi_disk_boot_source" {
  description = "Self-link of the boot Persistent Disk attached to the multi-disk Gen2 instance."
  value       = google_compute_instance.multi_disk_source.boot_disk[0].source
}

output "multi_disk_data_disk_names" {
  description = "Names of the attached data Persistent Disks on the multi-disk Gen2 instance."
  value = [
    google_compute_disk.multi_app_data.name,
    google_compute_disk.db_wal.name,
    google_compute_disk.analytics_spool.name,
  ]
}

output "multi_disk_iap_ssh_command" {
  description = "gcloud SSH command using Identity-Aware Proxy tunneling to inspect the multi-disk guest OS."
  value       = "gcloud compute ssh ${google_compute_instance.multi_disk_source.name} --project=${google_compute_instance.multi_disk_source.project} --zone=${google_compute_instance.multi_disk_source.zone} --tunnel-through-iap"
}
