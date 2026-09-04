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

"""Tokenomics Module for Project Aegis Agent Service.

Integrates BigQuery Agent Analytics SDK pattern for tracking LLM token
consumption, execution latency, cost and ROI metrics.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    from google.cloud import bigquery

    HAVE_BIGQUERY = True
except ImportError:
    HAVE_BIGQUERY = False

logger = logging.getLogger("TokenomicsTracker")

# Cost metrics for gemini-2.5-flash (USD per token)
GEMINI_2_5_FLASH_INPUT_COST_PER_TOKEN = 0.000000075  # $0.075 / 1M tokens
GEMINI_2_5_FLASH_OUTPUT_COST_PER_TOKEN = 0.00000030  # $0.30 / 1M tokens


class TokenomicsTracker:
    """Tracks LLM token usage, calculates inference cost and ROI."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        dataset_id: str = "analytics",
        table_id: str = "rca_events",
        default_downtime_value_usd: float = 5000.0,
    ):
        self.project_id = (
            project_id
            or os.getenv("GCP_PROJECT")
            or os.getenv("GOOGLE_CLOUD_PROJECT")
            or "aegis-streaming-1001"
        )
        self.dataset_id = dataset_id
        self.table_id = table_id
        self.default_downtime_value_usd = default_downtime_value_usd
        self.bq_client = None

        if HAVE_BIGQUERY:
            try:
                self.bq_client = bigquery.Client(project=self.project_id)
                logger.info(
                    "[TokenomicsTracker] BigQuery client initialized: %s",
                    self.project_id,
                )
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.warning(
                    "[TokenomicsTracker] BigQuery client warning: %s", e
                )

    def calculate_cost_and_roi(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        prevented_downtime_usd: Optional[float] = None,
    ) -> Dict[str, float]:
        """Calculate total cost in USD and ROI multiplier."""
        input_cost = prompt_tokens * GEMINI_2_5_FLASH_INPUT_COST_PER_TOKEN
        output_cost = completion_tokens * GEMINI_2_5_FLASH_OUTPUT_COST_PER_TOKEN
        total_cost = input_cost + output_cost

        downtime_value = (
            prevented_downtime_usd
            if prevented_downtime_usd is not None
            else self.default_downtime_value_usd
        )
        roi_multiplier = downtime_value / max(total_cost, 0.000001)

        return {
            "cost_usd": round(total_cost, 8),
            "prevented_downtime_usd": round(downtime_value, 2),
            "roi_multiplier": round(roi_multiplier, 2),
        }

    def track_execution(
        self,
        incident_id: str,
        asset_id: str,
        severity: str,
        root_cause_summary: str,
        recommended_action: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        telemetry_snapshot: Optional[Dict[str, Any]] = None,
        resolved: bool = True,
        prevented_downtime_usd: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Track agent execution metrics and persist event log."""
        total_tokens = prompt_tokens + completion_tokens
        financials = self.calculate_cost_and_roi(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            prevented_downtime_usd=prevented_downtime_usd,
        )

        timestamp_iso = datetime.now(timezone.utc).isoformat()

        record = {
            "incident_id": incident_id,
            "asset_id": asset_id,
            "timestamp": timestamp_iso,
            "severity": severity,
            "root_cause_summary": root_cause_summary,
            "telemetry_snapshot": (
                json.dumps(telemetry_snapshot) if telemetry_snapshot else None
            ),
            "recommended_action": recommended_action,
            "resolved": resolved,
            "tokenomics": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "latency_ms": round(latency_ms, 2),
                "cost_usd": financials["cost_usd"],
                "prevented_downtime_usd": financials["prevented_downtime_usd"],
                "roi_multiplier": financials["roi_multiplier"],
            },
        }

        logged_bq = self.log_to_bigquery(record)
        if not logged_bq:
            self.log_to_cloud_logging(record)

        return record

    def log_to_bigquery(self, record: Dict[str, Any]) -> bool:
        """Stream tokenomics and RCA event directly to BigQuery."""
        if not self.bq_client:
            return False

        table_ref = f"{self.project_id}.{self.dataset_id}.{self.table_id}"

        tokens_count = 452
        cost_val = 0.00018
        if isinstance(record.get("tokenomics"), dict):
            tokens_count = int(record["tokenomics"].get("total_tokens", 452))
            cost_val = float(record["tokenomics"].get("cost_usd", 0.00018))

        bq_asset_id = record.get("asset_id")
        bq_row = {
            "event_id": record.get("incident_id")
            or record.get("event_id")
            or f"EVT-{bq_asset_id}",
            "asset_id": record["asset_id"],
            "timestamp": record["timestamp"],
            "root_cause": record.get("root_cause_summary")
            or record.get("root_cause", ""),
            "mitigation_plan": record.get("recommended_action")
            or record.get("mitigation_plan", ""),
            "tokens_used": tokens_count,
            "cost_usd": cost_val,
            "status": "MITIGATED" if record.get("resolved") else "IN_PROGRESS",
        }

        try:
            errors = self.bq_client.insert_rows_json(table_ref, [bq_row])
            if errors:
                logger.error(
                    "[TokenomicsTracker] BigQuery errors for '%s': %s",
                    table_ref,
                    errors,
                )
                return False
            logger.info(
                "[TokenomicsTracker] Logged incident %s to BigQuery.",
                record["incident_id"],
            )
            return True
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.warning(
                "[TokenomicsTracker] BigQuery streaming write failed: %s", e
            )
            return False

    def log_to_cloud_logging(self, record: Dict[str, Any]) -> None:
        """Log structured RCA and Tokenomics record to standard logging."""
        tok = record["tokenomics"]
        inc_id = record["incident_id"]
        a_id = record["asset_id"]
        t_tok = tok["total_tokens"]
        p_tok = tok["prompt_tokens"]
        c_tok = tok["completion_tokens"]
        lat = tok["latency_ms"]
        cost = tok["cost_usd"]
        roi = tok["roi_multiplier"]
        log_message = (
            f"[Tokenomics] Incident={inc_id} | Asset={a_id} | "
            f"Tokens={t_tok} (Prompt={p_tok}, Completion={c_tok}) | "
            f"Latency={lat}ms | Cost=${cost:.6f} | ROI={roi}x"
        )
        logger.info("%s", log_message)
        logger.debug("[Tokenomics Payload] %s", json.dumps(record))
