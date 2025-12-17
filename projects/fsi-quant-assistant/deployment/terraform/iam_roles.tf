# Copyright 2025 Google LLC
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

resource "google_project_iam_custom_role" "cloud_build_job_runner" {
  role_id     = "custom.cloudbuild.jobrunner"
  title       = "Cloud Build Job Invoker"
  description = "Allows SA to invoke run job"
  permissions = ["cloudbuild.builds.create"]
}
