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

"""A2A Agent Discovery Catalog and Agent Card Endpoints."""

import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from src.a2a.agent_card import AgentCard, create_workflow_agent_card
from src.config import get_settings

logger = logging.getLogger(__name__)

catalog_router = APIRouter()
_AGENT_REGISTRY: dict[str, AgentCard] = {}


def get_default_workflow_agent_card(server_url: str) -> AgentCard:
    """Build official A2A Agent Card for Oracle EBS Workflow AI Assistant."""
    return create_workflow_agent_card(server_url)


@catalog_router.get(
    "/agent.json",
    response_model=dict[str, Any],
    operation_id="get_agent_card_main",
)
@catalog_router.api_route(
    "/agent.json",
    methods=["POST", "OPTIONS"],
    response_model=dict[str, Any],
    include_in_schema=False,
)
@catalog_router.api_route(
    "/.well-known/agent.json",
    methods=["GET", "POST", "OPTIONS"],
    response_model=dict[str, Any],
    include_in_schema=False,
)
@catalog_router.api_route(
    "/agent-card.json",
    methods=["GET", "POST", "OPTIONS"],
    response_model=dict[str, Any],
    include_in_schema=False,
)
@catalog_router.api_route(
    "/.well-known/agent-card.json",
    methods=["GET", "POST", "OPTIONS"],
    response_model=dict[str, Any],
    include_in_schema=False,
)
@catalog_router.api_route(
    "/a2a/agent.json",
    methods=["GET", "POST", "OPTIONS"],
    response_model=dict[str, Any],
    include_in_schema=False,
)
@catalog_router.api_route(
    "/a2a/card",
    methods=["GET", "POST", "OPTIONS"],
    response_model=dict[str, Any],
    include_in_schema=False,
)
def get_agent_card(req: Request) -> dict[str, Any]:
    """Generate dynamic A2A Agent Card specification compliant with v0.3.0."""
    host = req.headers.get("x-forwarded-host") or req.headers.get("host") or ""
    if host and ".run.app" in host:
        server_url = f"https://{host}"
    else:
        server_url = os.environ.get(
            "A2A_SERVER_URL", get_settings().network.a2a_server_url
        )

    card = get_default_workflow_agent_card(server_url)
    return card.model_dump(by_alias=True)


@catalog_router.get("/agents/discover", response_model=dict[str, Any])
def discover_agents() -> dict[str, Any]:
    """Discover active enterprise workflow agents and capabilities."""
    settings = get_settings()
    return {
        "gateway": "Oracle EBS Workflow A2A Gateway",
        "registered_services": [
            {
                "name": "workflow_agent",
                "url": settings.network.workflow_agent_url,
                "endpoints": [
                    "/notifications",
                    "/verify-policy",
                    "/triage",
                    "/approve",
                    "/reject",
                    "/respond",
                ],
            }
        ],
    }


@catalog_router.post(
    "/register", response_model=AgentCard, status_code=status.HTTP_201_CREATED
)
def register_agent(agent: AgentCard) -> AgentCard:
    """Register or update an agent card in the discovery catalog."""
    _AGENT_REGISTRY[agent.name] = agent
    return agent


@catalog_router.get("/agents", response_model=list[AgentCard])
def list_agents() -> list[AgentCard]:
    """List all registered agents."""
    return list(_AGENT_REGISTRY.values())


@catalog_router.get("/agents/{agent_name}", response_model=AgentCard)
def get_agent(agent_name: str) -> AgentCard:
    """Lookup agent card by unique name."""
    if agent_name not in _AGENT_REGISTRY:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_name}' not registered in discovery catalog",
        )
    return _AGENT_REGISTRY[agent_name]


@catalog_router.delete(
    "/agents/{agent_name}", status_code=status.HTTP_204_NO_CONTENT
)
def deregister_agent(agent_name: str) -> None:
    """Deregister an agent from the discovery catalog."""
    if agent_name not in _AGENT_REGISTRY:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_name}' not registered in discovery catalog",
        )
    del _AGENT_REGISTRY[agent_name]


# Alias router for catalog router
router = catalog_router
