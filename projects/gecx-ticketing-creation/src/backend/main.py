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

# pylint: disable=line-too-long
"""Module containing GECX main logic."""

import os
import re
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from src.backend.routes.loopback import auth as lb_auth
from src.backend.routes.loopback import chat as lb_chat
from src.backend.routes.loopback import signaling as lb_signaling
from src.backend.routes.loopback import tickets as lb_tickets

# Global template cache to avoid disk I/O on request
TEMPLATE_CACHE = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Lifespan event handler for application startup and shutdown."""
    # Load environment variables on startup
    load_dotenv()

    # Fail fast if required configurations are missing
    if not os.getenv("GCP_PROJECT_ID"):
        raise RuntimeError("GCP_PROJECT_ID environment variable is missing!")
    if not os.getenv("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY environment variable is missing!")

    template_file_path = os.path.join(
        "src", "frontend", "static", "loopback", "index.template.html"
    )
    static_file_path = os.path.join(
        "src", "frontend", "static", "loopback", "index.html"
    )

    source_path = (
        template_file_path
        if os.path.exists(template_file_path)
        else static_file_path
    )

    if os.path.exists(source_path):
        with open(source_path, "r", encoding="utf-8") as f:
            TEMPLATE_CACHE["loopback_template"] = f.read()
    else:
        TEMPLATE_CACHE["loopback_template"] = None
    yield
    TEMPLATE_CACHE.clear()


app = FastAPI(title="Cymbal Support BFF API", lifespan=lifespan)

# Include Partitioned Routers
app.include_router(lb_tickets.router, prefix="/api/loopback")
app.include_router(lb_auth.router, prefix="/api/loopback")
app.include_router(lb_signaling.router, prefix="/api")
app.include_router(lb_chat.router, prefix="/api")


# Serve Loopback Client Portal
@app.get("/")
def read_root():
    """Serves the loopback customer portal, replacing the project placeholder."""
    content = TEMPLATE_CACHE.get("loopback_template")

    if content is not None:
        project_id = os.getenv("GCP_PROJECT_ID", "")
        deployment_name = (
            f"projects/{project_id}/locations/us/apps/cymbal-support-agent/"
            "deployments/cymbal-support-agent-web"
        )

        updated_content = re.sub(
            r'(deploymentName:\s*["\'])(?:<<AGENT_DEPLOYMENT_NAME>>|projects/[^"\']+)(["\'])',
            rf"\g<1>{deployment_name}\g<2>",
            content,
        )
        return HTMLResponse(content=updated_content)

    return {
        "message": (
            "Loopback Customer portal is missing from the container. "
            "Looked for src/frontend/static/loopback/index.template.html "
            "and src/frontend/static/loopback/index.html"
        )
    }


# Serve other static files if directory exists
if os.path.exists("src/frontend/static"):
    app.mount(
        "/static", StaticFiles(directory="src/frontend/static"), name="static"
    )
