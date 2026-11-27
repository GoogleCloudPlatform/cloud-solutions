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

"""Publishes declarative Workload Profiles to Google Cloud Storage."""

import os
import sys
from pathlib import Path
from urllib.parse import quote

from app.app_utils.profile_loader import PROFILES_ROOT, parse_gcs_uri
from deployment.auth import require_project_id, resolve_credentials
from google.auth.transport.requests import AuthorizedSession


def _list_remote_objects(
    session: AuthorizedSession, bucket: str, prefix: str
) -> list[str]:
    search_prefix = f"{prefix}/" if prefix else ""
    url = f"https://storage.googleapis.com/storage/v1/b/{bucket}/o"
    objects: list[str] = []
    page_token: str | None = None
    while True:
        params: dict[str, str] = {"prefix": search_prefix}
        if page_token:
            params["pageToken"] = page_token
        resp = session.get(url, params=params, timeout=15)
        resp.raise_for_status()
        payload = resp.json()
        for item in payload.get("items") or []:
            name = item.get("name", "")
            if name:
                objects.append(name)
        page_token = payload.get("nextPageToken")
        if not page_token:
            break
    return objects


def sync_profiles(
    gcs_uri: str | None = None,
    runtime_project: str | None = None,
    prune: bool = False,
    profiles_root: Path | None = None,
) -> int:
    """Uploads local non-underscore profile bundles to Cloud Storage."""
    proj = require_project_id(runtime_project)
    staging_bucket = os.getenv(
        "AGENT_ENGINE_STAGING_BUCKET",
        f"gs://{proj}-gcp-sre-advisor-staging",
    ).strip()
    target_uri = (
        gcs_uri or os.getenv("PROFILES_GCS_URI") or f"{staging_bucket}/profiles"
    ).strip()

    parsed = parse_gcs_uri(target_uri)
    if not parsed:
        raise ValueError(f"Invalid PROFILES_GCS_URI: {target_uri}")
    bucket, prefix = parsed

    creds = resolve_credentials(proj)
    session = AuthorizedSession(creds)

    root_dir = profiles_root or PROFILES_ROOT
    local_profile_names: set[str] = set()
    uploaded = 0

    if root_dir.exists():
        for profile_dir in sorted(root_dir.iterdir()):
            if not profile_dir.is_dir() or profile_dir.name.startswith("_"):
                continue
            if not (profile_dir / "profile.yaml").exists():
                continue
            local_profile_names.add(profile_dir.name)
            for filename in ("profile.yaml", "context.md"):
                fpath = profile_dir / filename
                if not fpath.exists():
                    continue
                obj_name = (
                    f"{prefix}/{profile_dir.name}/{filename}"
                    if prefix
                    else f"{profile_dir.name}/{filename}"
                )
                encoded_obj = quote(obj_name, safe="")
                upload_url = (
                    f"https://storage.googleapis.com/upload/storage/v1/"
                    f"b/{bucket}/o?uploadType=media&name={encoded_obj}"
                )
                resp = session.post(
                    upload_url,
                    data=fpath.read_bytes(),
                    headers={"Content-Type": "text/plain; charset=utf-8"},
                    timeout=15,
                )
                resp.raise_for_status()
                uploaded += 1
                print(f"Uploaded gs://{bucket}/{obj_name}")

    if prune:
        search_prefix = f"{prefix}/" if prefix else ""
        for obj_name in _list_remote_objects(session, bucket, prefix):
            rel = obj_name[len(search_prefix) :].strip("/")
            parts = rel.split("/", 1)
            remote_profile = parts[0] if parts else ""
            if not remote_profile or remote_profile.startswith("_"):
                continue
            if remote_profile not in local_profile_names:
                encoded_del = quote(obj_name, safe="")
                del_url = (
                    f"https://storage.googleapis.com/storage/v1/"
                    f"b/{bucket}/o/{encoded_del}"
                )
                del_resp = session.delete(del_url, timeout=15)
                if del_resp.status_code not in (200, 204, 404):
                    del_resp.raise_for_status()
                print(f"Pruned gs://{bucket}/{obj_name}")

    return uploaded


if __name__ == "__main__":
    uri_arg = sys.argv[1] if len(sys.argv) > 1 else None
    sync_profiles(uri_arg)
