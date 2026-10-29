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

"""Dataplex Knowledge Catalog glossary and aspect lookup client."""

import functools
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from google.api_core.exceptions import GoogleAPICallError
from google.cloud import dataplex_v1

logger = logging.getLogger(__name__)

_APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = (
    _APP_DIR / "data"
    if (_APP_DIR / "data").exists()
    else PROJECT_ROOT / "data"
)
GLOSSARY_JSON_PATH = _DATA_DIR / "policies" / "business_glossary.json"
POLICY_MD_PATH = _DATA_DIR / "policies" / "return_policy_v1.md"
U2G_TRIPLES_PATH = _DATA_DIR / "policies" / "u2g_policy_triples.json"

CACHE_TTL_SECONDS = 300.0
_CONTRACT_CACHE: dict[str, Any] = {"expires_at": 0.0, "contract": None}


@functools.lru_cache(maxsize=1)
def load_glossary_bundle() -> dict[str, Any]:
    """Loads and caches the local business_glossary.json bundle at startup."""
    with GLOSSARY_JSON_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@functools.lru_cache(maxsize=1)
def get_query_templates() -> dict[str, str]:
    """Returns cached externalized SQL and ISO GQL templates."""
    bundle = load_glossary_bundle()
    return dict(bundle.get("query_templates", {}))


@functools.lru_cache(maxsize=1)
def load_governance_artifacts() -> dict[str, Any]:
    """Loads and caches policy markdown and U2G triples from disk."""
    policy_md = POLICY_MD_PATH.read_text(encoding="utf-8")
    with U2G_TRIPLES_PATH.open("r", encoding="utf-8") as handle:
        u2g_triples = json.load(handle)
    return {
        "policy_document_markdown": policy_md,
        "u2g_triples": u2g_triples,
    }


def _extract_fallback_contract() -> dict[str, Any]:
    """Extracts the governed metric contract from business_glossary.json."""
    bundle = load_glossary_bundle()
    return {
        "catalog_term_id": str(
            bundle.get("catalog_term_id", "rolling-100d-refund-count")
        ),
        "secondary_term_id": str(
            bundle.get("secondary_term_id", "order-age-days")
        ),
        "tier_term_id": str(
            bundle.get("tier_term_id", "customer-loyalty-tier")
        ),
        "returned_status": str(bundle.get("returned_status", "Returned")),
        "eligible_order_status": str(
            bundle.get("eligible_order_status", "Complete")
        ),
        "rolling_window_days": int(bundle.get("rolling_window_days", 100)),
        "standard_tier": str(bundle.get("standard_tier", "STANDARD")),
        "vip_tier": str(bundle.get("vip_tier", "VIP")),
    }


def clear_catalog_cache() -> None:
    """Clears the in-memory Knowledge Catalog contract cache."""
    _CONTRACT_CACHE["expires_at"] = 0.0
    _CONTRACT_CACHE["contract"] = None


def _resolve_terms_from_dataplex(
    client: Any,
    glossary_name: str,
    contract: dict[str, Any],
) -> dict[str, Any]:
    """Resolves governed term IDs from the Dataplex Business Glossary API."""
    resolved = dict(contract)
    glossary = client.get_glossary(name=glossary_name, timeout=5.0)
    resolved_parent = str(getattr(glossary, "name", "") or glossary_name)
    list_terms_fn = getattr(client, "list_glossary_terms", None)
    if callable(list_terms_fn):
        live_term_ids: set[str] = set()
        for term in list_terms_fn(parent=resolved_parent, timeout=5.0):
            term_name = str(getattr(term, "name", "") or "")
            if "/terms/" in term_name:
                live_term_ids.add(term_name.rsplit("/terms/", 1)[-1])
            elif term_name:
                live_term_ids.add(term_name)
        for term_id in sorted(live_term_ids):
            if "refund-count" in term_id:
                resolved["catalog_term_id"] = term_id
            elif "order-age" in term_id:
                resolved["secondary_term_id"] = term_id
            elif "loyalty-tier" in term_id or "tier" in term_id:
                resolved["tier_term_id"] = term_id
    return resolved


def fetch_knowledge_catalog_aspect(
    dataplex_client: Any = None,
) -> dict[str, Any]:
    """Resolves the governed metric contract from Dataplex or JSON fallback."""
    now = time.monotonic()
    cached = _CONTRACT_CACHE.get("contract")
    expires_at = float(_CONTRACT_CACHE.get("expires_at", 0.0))
    if cached is not None and now < expires_at:
        return dict(cached)

    resolved_contract = _extract_fallback_contract()
    project_id = os.getenv("GCP_PROJECT_ID") or os.getenv(
        "GOOGLE_CLOUD_PROJECT"
    )
    glossary_id = os.getenv("DATAPLEX_GLOSSARY_ID", "soa-business-glossary")
    aspect_type_id = os.getenv(
        "DATAPLEX_ASPECT_TYPE_ID", "refund-metric-contract"
    )

    if project_id or dataplex_client is not None:
        try:
            client = (
                dataplex_client or dataplex_v1.BusinessGlossaryServiceClient()
            )
            resolved_project = project_id or "local-dev"
            glossary_name = (
                f"projects/{resolved_project}/locations/global/"
                f"glossaries/{glossary_id}"
            )
            resolved_contract = _resolve_terms_from_dataplex(
                client, glossary_name, resolved_contract
            )
            logger.info(
                "Resolved Dataplex Knowledge Catalog glossary %s (aspect=%s).",
                glossary_name,
                aspect_type_id,
            )
        except (GoogleAPICallError, ValueError, OSError, RuntimeError) as exc:
            logger.warning(
                "Dataplex API unavailable (%s); using JSON fallback.",
                exc,
            )

    _CONTRACT_CACHE["contract"] = dict(resolved_contract)
    _CONTRACT_CACHE["expires_at"] = now + CACHE_TTL_SECONDS
    return dict(resolved_contract)
