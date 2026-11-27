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

"""Shared credential resolution and gcloud CLI helpers for deployment."""

import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import google.auth
from dotenv import load_dotenv
from google.auth.credentials import Credentials as BaseCredentials
from google.oauth2.credentials import Credentials as OAuthCredentials

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def gcloud_cmd(*args: str) -> list[str]:
    """Builds a gcloud CLI command honoring CLOUDSDK_CORE_ACCOUNT."""
    cmd = ["gcloud"]
    acct = os.getenv("CLOUDSDK_CORE_ACCOUNT", "").strip()
    if acct:
        cmd.append(f"--account={acct}")
    cmd.extend(args)
    return cmd


def require_project_id(explicit_project: str | None = None) -> str:
    """Resolves a Google Cloud project ID from arguments or environment."""
    proj = (
        explicit_project
        or os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("RUNTIME_PROJECT_ID")
        or ""
    ).strip()
    if not proj:
        raise ValueError(
            "A Google Cloud project ID is required via --project or "
            "GOOGLE_CLOUD_PROJECT."
        )
    return proj


class GcloudAccountCredentials(BaseCredentials):
    """Google Auth credentials backed by gcloud print-access-token."""

    def __init__(self, account: str, quota_project_id: str):
        super().__init__()
        self._account = account
        self._quota_project_id = quota_project_id
        self.refresh(None)

    @property
    def quota_project_id(self) -> str:
        """Returns the quota project ID associated with these credentials."""
        return self._quota_project_id

    def refresh(self, _request) -> None:
        out = subprocess.check_output(
            [
                "gcloud",
                "auth",
                "print-access-token",
                f"--account={self._account}",
                "--quiet",
            ],
            text=True,
        ).strip()
        self.token = out
        self.expiry = datetime.now(UTC).replace(tzinfo=None) + timedelta(
            minutes=45
        )


def resolve_credentials(runtime_project: str):
    """Resolves credentials from account, token, or Application Default."""
    explicit_account = os.getenv("CLOUDSDK_CORE_ACCOUNT", "").strip()
    if explicit_account:
        return GcloudAccountCredentials(
            account=explicit_account, quota_project_id=runtime_project
        )

    explicit_token = os.getenv("GOOGLE_OAUTH_ACCESS_TOKEN", "").strip()
    if explicit_token:
        return OAuthCredentials(
            token=explicit_token, quota_project_id=runtime_project
        )

    creds, _ = google.auth.default(quota_project_id=runtime_project or None)
    return creds
