# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""gcp utils helper functions"""

import google.auth
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import secretmanager


def get_default_project_id():
    """
    Gets the default GCP project ID from the environment.
    """
    try:
        # The default() function returns a tuple of (credentials, project_id)
        _, project_id = google.auth.default()
        return project_id
    except DefaultCredentialsError:
        # This error is raised if the library cannot find credentials
        print("🚨 Could not determine credentials.")
        print(
            "Please run 'gcloud auth application-default login' "
            "or configure your environment."
        )
        return None


def get_secret(
    secret_id: str, project_id: str = None, version_id: str = "latest"
) -> str:
    """
    Accesses a secret version from Google Cloud Secret Manager.
    """
    # Create the Secret Manager client
    client = secretmanager.SecretManagerServiceClient()

    # If project_id is not set, use the default project
    if not project_id:
        project_id = get_default_project_id()

    # Build the resource name of the secret version
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"

    # Access the secret version
    print(f"Accessing secret: {name}")
    response = client.access_secret_version(name=name)

    # Decode the secret payload. Secrets are stored as bytes.
    secret_value = response.payload.data.decode("UTF-8")

    return secret_value
