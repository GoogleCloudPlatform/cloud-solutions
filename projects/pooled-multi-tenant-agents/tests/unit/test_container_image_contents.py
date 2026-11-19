# Copyright 2026 Google LLC
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

# pylint: disable=line-too-long

"""The container image contains everything the gateway imports or reads at startup.

Rebuilds the image's file layout from the Dockerfile's COPY lines in a temp directory and starts
`app.main` there. A deploy failed because `config/` (added with the layered platform config) was
never copied into the image; this catches that class of error in CI, without Docker.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _copy_sources() -> list[str]:
    sources = []
    for line in (REPO / "Dockerfile").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^COPY\s+(\S+)\s+\S+\s*$", line.strip())
        if m and m.group(1) != "requirements.txt":
            sources.append(m.group(1).rstrip("/"))
    return sources


def test_image_layout_imports_the_gateway_and_finds_its_config(
    tmp_path: Path,
) -> None:
    sources = _copy_sources()
    assert "runtime_service" in sources
    assert "tests" not in sources
    for src in sources:
        path = REPO / src
        if path.is_dir():
            shutil.copytree(
                path,
                tmp_path / src,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        else:
            shutil.copy2(path, tmp_path / src)
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("CYMBAL_", "RUN_LIVE"))
    }
    env["PYTHONPATH"] = str(tmp_path)
    probe = (
        "import app.main as m; from fastapi.testclient import TestClient; "
        "c = TestClient(m.app); r = c.get('/api/v1/health'); assert r.status_code == 200, r.text; "
        "[c.get(f'/diagrams/{d}.svg').raise_for_status() for d in "
        "('ws2_pooled_5hop_architecture', 'ws2_phase1_vs_phase2_modularity', "
        "'ws2_token_permission_flow')]; "
        "print(r.json()['environment'])"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.strip().splitlines()[-1] == "sandbox"


def test_cloud_build_upload_keeps_the_ui_diagrams() -> None:
    """`gcloud run deploy --source` honours .gcloudignore: the UI's diagrams must not be ignored."""
    lines = [
        ln.strip()
        for ln in (REPO / ".gcloudignore")
        .read_text(encoding="utf-8")
        .splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    assert (
        "docs/" not in lines
    ), "a bare 'docs/' excludes docs/assets and can't be re-included"
    if "docs/*" in lines:
        assert "!docs/assets/" in lines[lines.index("docs/*") :]


def test_dockerfile_runs_as_non_root_appuser() -> None:
    """Production container drops root privileges via non-root `appuser` (uid 10001)."""
    dockerfile = (REPO / "Dockerfile").read_text(encoding="utf-8")
    assert "--uid 10001" in dockerfile
    user_directives = [
        ln.strip()
        for ln in dockerfile.splitlines()
        if ln.strip().startswith("USER ")
    ]
    assert user_directives == ["USER appuser"]
