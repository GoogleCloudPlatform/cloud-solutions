#  Copyright 2024 Google LLC
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""Provides simplified utils to access secrets on Secret Manager."""

from google.cloud import secretmanager


def get_secret(secret_name: str) -> str:
    """Gets a secret from the Secrets Manager.

    Args:
        secret_name: Fully qualified name of the secret to get. Format:
            "projects/<projectId>/secrets/<secretId>/versions/<versionId>".

    Returns:
        Secret stored in Secret Manager under the qualified name.
    """
    client = secretmanager.SecretManagerServiceClient()
    secret_response = client.access_secret_version(name=secret_name)
    return secret_response.payload.data.decode('utf-8')
