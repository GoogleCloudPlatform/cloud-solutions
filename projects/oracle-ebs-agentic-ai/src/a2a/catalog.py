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

"""A2A Discovery & Registration Catalog module."""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from src.a2a.agent_card import AgentCard
from src.a2a.proxy import (
    _get_financial_agent_url,
    _get_inventory_agent_url,
    _get_supplier_agent_url,
)

logger = logging.getLogger(__name__)

# In-memory registry for agent discovery
_AGENT_REGISTRY: Dict[str, AgentCard] = {}

catalog_router = APIRouter()


def upload_agent_card_to_gcs(
    agent_card: Dict[str, Any],
    bucket_name: Optional[str] = None,
    object_name: str = "agent.json",
) -> Optional[str]:
    """Upload A2A Agent Card to GCS bucket for public discovery."""
    bucket_name = bucket_name or os.environ.get("AGENT_CARD_GCS_BUCKET", "")
    if not bucket_name:
        logger.info(
            "AGENT_CARD_GCS_BUCKET not set. Skipping Agent Card GCS upload."
        )
        return None

    try:
        url = (
            f"https://storage.googleapis.com/upload/storage/v1/b/"
            f"{bucket_name}/o?uploadType=media&name={object_name}"
        )
        headers = {"Content-Type": "application/json"}
        with httpx.Client(timeout=5.0) as client:
            meta_res = client.get(
                "http://metadata.google.internal/computeMetadata/v1/"
                "instance/service-accounts/default/token",
                headers={"Metadata-Flavor": "Google"},
            )
            if meta_res.status_code == 200:
                token = meta_res.json().get("access_token")
                if token:
                    headers["Authorization"] = f"Bearer {token}"
            res = client.post(
                url, content=json.dumps(agent_card, indent=2), headers=headers
            )
            if res.status_code == 200:
                gcs_uri = f"gs://{bucket_name}/{object_name}"
                logger.info("Successfully uploaded Agent Card to %s", gcs_uri)
                return gcs_uri
    except (httpx.HTTPError, OSError) as exc:
        logger.warning("Failed to upload Agent Card to GCS: %s", exc)
    return None


@catalog_router.api_route(
    "/agent.json",
    methods=["GET", "POST", "OPTIONS"],
    response_model=Dict[str, Any],
)
@catalog_router.api_route(
    "/.well-known/agent.json",
    methods=["GET", "POST", "OPTIONS"],
    response_model=Dict[str, Any],
)
@catalog_router.api_route(
    "/a2a/agent.json",
    methods=["GET", "POST", "OPTIONS"],
    response_model=Dict[str, Any],
)
@catalog_router.api_route(
    "/agent-card.json",
    methods=["GET", "POST", "OPTIONS"],
    response_model=Dict[str, Any],
)
@catalog_router.api_route(
    "/.well-known/agent-card.json",
    methods=["GET", "POST", "OPTIONS"],
    response_model=Dict[str, Any],
)
@catalog_router.api_route(
    "/a2a/v1/agent.json",
    methods=["GET", "POST", "OPTIONS"],
    response_model=Dict[str, Any],
)
def get_agent_card(req: Request) -> Dict[str, Any]:
    """Generate dynamic A2A Agent Card specification compliant with v0.3.0."""
    host = req.headers.get("x-forwarded-host") or req.headers.get("host") or ""
    server_url = (
        f"https://{host}"
        if host and "a.run.app" in host
        else os.environ.get("A2A_SERVER_URL", "http://127.0.0.1:8080")
    )
    card_data = {
        "name": "Oracle EBS Autonomous Assistant",
        "description": (
            "Autonomous Agent-to-Agent Gateway for Oracle EBS Inventory,"
            " AP/AR Financials, and Supplier Negotiation."
        ),
        "url": server_url,
        "version": "1.0.0",
        "protocolVersion": "0.3.0",
        "defaultInputModes": ["text/plain", "application/json"],
        "defaultOutputModes": [
            "application/json",
            "text/plain",
            "text/markdown",
        ],
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
        },
        "skills": [
            {
                "id": "inventory_management",
                "name": "Inventory Management",
                "description": (
                    "Checks on-hand quantities, safety stock thresholds, and"
                    " item details."
                ),
                "tags": ["inventory", "stock", "oracle_ebs"],
                "examples": [
                    "List items for Organization code AD1",
                    "Check stock for item AS54888 in Organization code V1",
                    "Check stock for item AS54888 in Organization 204",
                    "List items for organization V1",
                ],
            },
            {
                "id": "financial_operations",
                "name": "Financial Operations",
                "description": (
                    "Tracks AP invoice status, calculates DSO metrics, and"
                    " evaluates cash flow."
                ),
                "tags": ["financials", "invoices", "dso", "oracle_ebs"],
                "examples": [
                    "Inspect AP invoice status for invoice INV-2024-001",
                    "Calculate DSO metrics for the past 90 days",
                ],
            },
            {
                "id": "supplier_negotiation",
                "name": "Supplier Negotiation",
                "description": (
                    "Negotiates unit pricing, bulk restock discounts, and"
                    " delivery terms with vendors."
                ),
                "tags": [
                    "procurement",
                    "suppliers",
                    "purchasing",
                    "oracle_ebs",
                ],
                "examples": [
                    "Give me the items for supplier 515",
                    "Negotiate restock for 500 units of item AS54888 with"
                    " Acme Industrial",
                ],
            },
        ],
    }
    upload_agent_card_to_gcs(card_data)
    return card_data


@catalog_router.get("/agents/discover", response_model=Dict[str, Any])
def discover_agents() -> Dict[str, Any]:
    """Discover active enterprise agents & capabilities catalog."""
    return {
        "gateway": "Oracle EBS A2A Gateway",
        "registered_services": [
            {
                "name": "inventory_agent",
                "url": _get_inventory_agent_url(),
                "endpoints": ["/check-stock"],
            },
            {
                "name": "financial_agent",
                "url": _get_financial_agent_url(),
                "endpoints": ["/invoice-status", "/calculate-dso"],
            },
            {
                "name": "supplier_agent",
                "url": _get_supplier_agent_url(),
                "endpoints": ["/negotiate"],
            },
        ],
    }


@catalog_router.get(
    "/discover/{capability}", response_model=List[Dict[str, Any]]
)
def discover_agent_by_capability(capability: str) -> List[Dict[str, Any]]:
    """Discover active worker agent endpoints dynamically by capability."""
    workers = [
        {
            "name": "inventory_agent",
            "description": "Oracle EBS Inventory stock verification",
            "endpoints": ["/check-stock"],
            "capabilities": ["inventory", "stock", "warehouse", "check_stock"],
        },
        {
            "name": "financial_agent",
            "description": "Oracle EBS AP & AR Financial Operations",
            "endpoints": ["/invoice-status", "/calculate-dso"],
            "capabilities": ["invoice", "financials", "dso", "ap", "ar"],
        },
        {
            "name": "supplier_agent",
            "description": "Oracle EBS PO & Supplier Negotiation",
            "endpoints": ["/negotiate"],
            "capabilities": ["negotiation", "supplier", "purchasing", "po"],
        },
    ]
    matches = [
        w
        for w in workers
        if any(capability.lower() in c for c in w["capabilities"])
    ]
    return matches or [
        {
            "name": "a2a_gateway",
            "description": "Unified Gateway for Oracle EBS",
            "endpoints": ["/check-stock", "/invoice-status", "/negotiate"],
            "capabilities": [capability],
        }
    ]


@catalog_router.post(
    "/register", response_model=AgentCard, status_code=status.HTTP_201_CREATED
)
def register_agent(agent: AgentCard) -> AgentCard:
    """Register or update an agent card in the discovery catalog."""
    _AGENT_REGISTRY[agent.name] = agent
    return agent


@catalog_router.get("/agents", response_model=List[AgentCard])
def list_agents() -> List[AgentCard]:
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
    "/agents/{agent_name}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def deregister_agent(agent_name: str) -> None:
    """Deregister an agent from the discovery catalog."""
    if agent_name not in _AGENT_REGISTRY:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_name}' not registered in discovery catalog",
        )
    del _AGENT_REGISTRY[agent_name]
