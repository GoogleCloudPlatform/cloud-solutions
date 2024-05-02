# Copyright 2024 Google LLC
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

# For more information about configuring this Cloud Pub/Sub topic as a dead-letter
# topic for the Cloud Pub/Sub subscription that Eventarc automatically creates
# for you, see https://cloud.google.com/eventarc/docs/retry-events.
# If you need to have Terraform manage the subscription and its configuration,
# you can import it as a resource in your Terraform state. For more information
# about importing Cloud Pub/Sub subscriptions in the Terraform state, see
# https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/pubsub_subscription#import
resource "google_pubsub_topic" "event_processing_dead_letter_topic" {
  count = var.provision_event_processing_dead_letter_topic ? 1 : 0

  name    = "event-processing-dead-letter-topic"
  project = data.google_project.project.project_id
}
