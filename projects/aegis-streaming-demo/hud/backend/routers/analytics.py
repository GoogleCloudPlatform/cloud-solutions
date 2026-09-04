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

"""Router for BigQuery analytics queries and fleet insights."""

import asyncio
import logging
import os
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from models import RunAnalyticsQueryRequest

logger = logging.getLogger("aegis-hud-backend")
router = APIRouter(tags=["Analytics"])

try:
    from google.cloud import bigquery

    BQ_AVAILABLE = True
except ImportError:
    BQ_AVAILABLE = False
    logger.warning("google-cloud-bigquery package not available.")


def get_predefined_queries(
    project_id: str, dataset_id: str
) -> List[Dict[str, Any]]:
    return [
        {
            "query_id": "fleet_stress",
            "title": "Fleet-Wide Thermal & Compute Stress Summary",
            "badge": "Real-Time Aggregations",
            "description": (
                "Aggregates 10-second tumbling window metrics across all 15 "
                "industrial assets to identify chronic thermal drift and "
                "compute saturation."
            ),
            "sql": f"""SELECT
  asset_id,
  COUNT(*) as total_readings,
  ROUND(AVG(cpu_utilization), 2) as avg_cpu_pct,
  ROUND(MAX(cpu_utilization), 2) as max_cpu_pct,
  ROUND(AVG(temperature_c), 2) as avg_temp_c,
  ROUND(MAX(temperature_c), 2) as max_temp_c,
  COUNTIF(status = 'CRITICAL' OR cpu_utilization > 85.0 OR temperature_c > 85.0) as critical_events
FROM `{project_id}.{dataset_id}.telemetry_events`
GROUP BY asset_id
ORDER BY critical_events DESC, max_temp_c DESC
LIMIT 10""",
            "columns": [
                "asset_id",
                "total_readings",
                "avg_cpu_pct",
                "max_cpu_pct",
                "avg_temp_c",
                "max_temp_c",
                "critical_events",
            ],
        },
        {
            "query_id": "thermal_spikes",
            "title": "High-Severity Thermal Spikes & Anomaly Windows",
            "badge": "Anomaly Detection",
            "description": (
                "Filters historical stream ingestion for severe thermal events "
                "exceeding safety thresholds (Temp > 80°C or CPU > 85%)."
            ),
            "sql": f"""SELECT
  asset_id,
  TIMESTAMP_TRUNC(timestamp, MINUTE) as window_minute,
  ROUND(MAX(temperature_c), 2) as peak_temp_c,
  ROUND(MAX(cpu_utilization), 2) as peak_cpu_pct,
  ANY_VALUE(status) as status
FROM `{project_id}.{dataset_id}.telemetry_events`
WHERE temperature_c > 80.0 OR cpu_utilization > 85.0
GROUP BY asset_id, window_minute
ORDER BY peak_temp_c DESC
LIMIT 15""",
            "columns": [
                "asset_id",
                "window_minute",
                "peak_temp_c",
                "peak_cpu_pct",
                "status",
            ],
        },
        {
            "query_id": "mitigation_roi",
            "title": "AI Co-Pilot Mitigation ROI & Token Accounting",
            "badge": "Financial Provenance",
            "description": (
                "Audits Gemini Enterprise Agent Platform (GEAP) reasoning "
                "token consumption versus prevented machinery downtime value."
            ),
            "sql": f"""SELECT
  asset_id,
  COUNT(*) as mitigation_events,
  SUM(tokens_used) as total_tokens_consumed,
  ROUND(SUM(cost_usd), 6) as total_gemini_cost_usd,
  ROUND(SUM(5000.0), 2) as total_downtime_saved_usd,
  ROUND(SUM(5000.0) / NULLIF(SUM(cost_usd), 0), 1) as roi_multiplier
FROM `{project_id}.{dataset_id}.rca_events`
GROUP BY asset_id
ORDER BY total_downtime_saved_usd DESC
LIMIT 10""",
            "columns": [
                "asset_id",
                "mitigation_events",
                "total_tokens_consumed",
                "total_gemini_cost_usd",
                "total_downtime_saved_usd",
                "roi_multiplier",
            ],
        },
    ]


def generate_fallback_rows(query_id: str) -> List[Dict[str, Any]]:
    """Generate realistic fallback analytics rows if BigQuery is empty."""
    now = datetime.now(timezone.utc)
    if query_id == "fleet_stress":
        rows = []
        for i in range(1, 11):
            asset_id = f"Asset-{i:02d}"
            is_hot = i in [4, 7, 12]
            rows.append(
                {
                    "asset_id": asset_id,
                    "total_readings": random.randint(240, 1440),
                    "avg_cpu_pct": round(
                        (
                            random.uniform(75.0, 92.0)
                            if is_hot
                            else random.uniform(30.0, 50.0)
                        ),
                        2,
                    ),
                    "max_cpu_pct": round(
                        (
                            random.uniform(94.0, 99.8)
                            if is_hot
                            else random.uniform(55.0, 70.0)
                        ),
                        2,
                    ),
                    "avg_temp_c": round(
                        (
                            random.uniform(78.0, 89.0)
                            if is_hot
                            else random.uniform(48.0, 62.0)
                        ),
                        2,
                    ),
                    "max_temp_c": round(
                        (
                            random.uniform(92.0, 98.5)
                            if is_hot
                            else random.uniform(65.0, 74.0)
                        ),
                        2,
                    ),
                    "critical_events": (
                        random.randint(12, 45)
                        if is_hot
                        else random.randint(0, 2)
                    ),
                }
            )
        return sorted(rows, key=lambda r: r["critical_events"], reverse=True)
    if query_id == "thermal_spikes":
        rows = []
        for i in range(12):
            ts = now - timedelta(minutes=i * 3)
            asset_id = random.choice(
                ["Asset-04", "Asset-07", "Asset-12", "Asset-02"]
            )
            rows.append(
                {
                    "asset_id": asset_id,
                    "window_minute": ts.strftime("%Y-%m-%d %H:%M:%f")[:-3]
                    + " UTC",
                    "peak_temp_c": round(random.uniform(82.5, 96.8), 2),
                    "peak_cpu_pct": round(random.uniform(88.0, 99.4), 2),
                    "status": "CRITICAL",
                }
            )
        return sorted(rows, key=lambda r: r["peak_temp_c"], reverse=True)
    if query_id == "mitigation_roi":
        rows = []
        for i in [4, 7, 12, 2, 9, 5]:
            events = random.randint(3, 14)
            tokens = events * random.randint(410, 520)
            cost = round(tokens * 0.0000004, 6)
            saved = round(events * 5000.0, 2)
            roi = round(saved / max(cost, 0.000001), 1)
            rows.append(
                {
                    "asset_id": f"Asset-{i:02d}",
                    "mitigation_events": events,
                    "total_tokens_consumed": tokens,
                    "total_gemini_cost_usd": cost,
                    "total_downtime_saved_usd": saved,
                    "roi_multiplier": roi,
                }
            )
        return sorted(
            rows, key=lambda r: r["total_downtime_saved_usd"], reverse=True
        )
    return []


def _execute_bq_query(
    query_id: str, project_id: str, dataset_id: str
) -> Dict[str, Any]:
    queries = get_predefined_queries(project_id, dataset_id)
    target = next((q for q in queries if q["query_id"] == query_id), None)
    if not target:
        raise HTTPException(
            status_code=404, detail=f"Unknown query_id: {query_id}"
        )

    sql = target["sql"]
    columns = target["columns"]
    start_time = time.time()

    if not BQ_AVAILABLE or not project_id:
        logger.info(
            "BigQuery unavailable or project_id missing. Using fallback "
            "for %s.",
            query_id,
        )
        rows = generate_fallback_rows(query_id)
        return {
            "query_id": query_id,
            "title": target["title"],
            "badge": target["badge"],
            "sql": sql,
            "columns": columns,
            "rows": rows,
            "execution_time_ms": round((time.time() - start_time) * 1000, 1),
            "source": "SIMULATED_FALLBACK",
        }

    try:
        client = bigquery.Client(project=project_id)
        query_job = client.query(sql)
        results = list(query_job.result(timeout=10.0))

        rows = []
        for row in results:
            row_dict = {}
            for col in columns:
                val = row.get(col, None)
                if isinstance(val, datetime):
                    val = val.isoformat()
                row_dict[col] = val
            rows.append(row_dict)

        if not rows:
            logger.info(
                "BigQuery returned 0 rows for %s. Providing fallback rows.",
                query_id,
            )
            rows = generate_fallback_rows(query_id)
            source = "BIGQUERY_EMPTY_FALLBACK"
        else:
            source = "BIGQUERY_LIVE"

        return {
            "query_id": query_id,
            "title": target["title"],
            "badge": target["badge"],
            "sql": sql,
            "columns": columns,
            "rows": rows,
            "execution_time_ms": round((time.time() - start_time) * 1000, 1),
            "source": source,
        }
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning(
            "Error executing BigQuery SQL for %s: %s. Using fallback rows.",
            query_id,
            exc,
        )
        rows = generate_fallback_rows(query_id)
        return {
            "query_id": query_id,
            "title": target["title"],
            "badge": target["badge"],
            "sql": sql,
            "columns": columns,
            "rows": rows,
            "execution_time_ms": round((time.time() - start_time) * 1000, 1),
            "source": "SIMULATED_FALLBACK",
        }


@router.get("/api/analytics/queries")
def list_analytics_queries():
    project_id = os.getenv("GCP_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", ""))
    dataset_id = os.getenv("BIGQUERY_DATASET_ID", "analytics")
    return {"queries": get_predefined_queries(project_id, dataset_id)}


@router.post("/api/analytics/run")
async def run_analytics_query(request: RunAnalyticsQueryRequest):
    project_id = os.getenv("GCP_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", ""))
    dataset_id = os.getenv("BIGQUERY_DATASET_ID", "analytics")
    return await asyncio.to_thread(
        _execute_bq_query, request.query_id, project_id, dataset_id
    )
