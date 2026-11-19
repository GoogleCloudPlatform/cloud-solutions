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

"""Interactive architecture workbench UI, walkthrough page, SVG diagrams, and MP4 asset routes."""

from __future__ import annotations

from pathlib import Path

from app.ui.walkthrough_page import render_tuesday_walkthrough_html
from app.ui.workbench_page import render_workbench_html
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response

router = APIRouter()

_REPO_ROOT = Path(__file__).resolve().parents[3]


@router.get("/diagrams/{diagram_name}.svg")
async def get_architecture_svg(diagram_name: str) -> Response:
    """Serves official 4-color Google Cloud vector SVG architecture diagrams."""
    allowed = {
        "ws2_pooled_5hop_architecture",
        "ws2_phase1_vs_phase2_modularity",
        "ws2_token_permission_flow",
    }
    if diagram_name not in allowed:
        raise HTTPException(status_code=404, detail="Diagram not found")
    svg_path = _REPO_ROOT / "docs" / "assets" / f"{diagram_name}.svg"
    if not svg_path.exists():
        raise HTTPException(status_code=404, detail="SVG asset missing")
    return Response(
        content=svg_path.read_text(encoding="utf-8"),
        media_type="image/svg+xml",
    )


@router.get("/assets/cymbal_3b1b_walkthrough.mp4")
async def get_3b1b_walkthrough_video() -> Response:
    """Serves the 3Blue1Brown-style 1080p architectural animation video."""
    mp4_path = _REPO_ROOT / "docs" / "assets" / "cymbal_3b1b_walkthrough.mp4"
    if not mp4_path.exists():
        raise HTTPException(status_code=404, detail="Video asset missing")
    return Response(
        content=mp4_path.read_bytes(),
        media_type="video/mp4",
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=3600",
        },
    )


@router.get("/demos", response_class=HTMLResponse)
@router.get("/tuesday", response_class=HTMLResponse)
async def tuesday_demos_and_architecture_ui() -> str:
    """Serves the Interactive Demos, Architecture & 3B1B Video Walkthrough page."""
    return render_tuesday_walkthrough_html()


@router.get("/", response_class=HTMLResponse)
async def dashboard_ui() -> str:
    """Serves the Minimalist Architecture Diagram & 5-Hop Tracer UI."""
    return render_workbench_html()
