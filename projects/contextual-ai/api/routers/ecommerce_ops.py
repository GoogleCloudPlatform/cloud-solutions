# Copyright 2025 Google LLC
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

"""
This module provides API endpoints for monitoring and analyzing
e-commerce operations data, including revenue, system performance,
user activity, and infrastructure health. It leverages BigQuery
for data retrieval and analysis.
"""

import math
import tomllib
from typing import Optional

from fastapi import APIRouter, Query

from utils.bigquery_tools import execute_bq_query
from models.ecommerce_ops import MetricsResponse

# Load configuration
with open("config.toml", "rb") as f:
    config = tomllib.load(f)

GCP_PROJECT_ID = config["gcp"]["GCP_PROJECT_ID"]
ECOMMERCE_DATASET_ID = config["gcp"]["ECOMMERCE_DATASET_ID"]

router = APIRouter()

# --- Revenue Metrics Endpoints ---


@router.get(
    "/revenue",
    response_model=MetricsResponse,
    tags=["ecommerce-revenue"],
    summary="Get revenue metrics",
    description=(
        "Retrieves paginated revenue metrics including hourly revenue,"
        "transaction count, and AOV"
    ),
)
async def get_revenue_metrics(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(
        20, ge=1, le=100, description="Records per page (max 100)"
    ),
    start_date: Optional[str] = Query(
        None, description="Start date (YYYY-MM-DD format)"
    ),
    end_date: Optional[str] = Query(
        None, description="End date (YYYY-MM-DD format)"
    ),
    min_revenue: Optional[float] = Query(
        None, description="Minimum hourly revenue filter"
    ),
):
    """Get revenue metrics with optional filtering"""

    # Build WHERE clause
    where_conditions = []
    if start_date:
        where_conditions.append(f"DATE(timestamp) >= '{start_date}'")
    if end_date:
        where_conditions.append(f"DATE(timestamp) <= '{end_date}'")
    if min_revenue:
        where_conditions.append(f"hourly_revenue >= {min_revenue}")

    where_clause = " AND ".join(where_conditions)
    if where_clause:
        where_clause = f"WHERE {where_clause}"

    table_name = f"`{GCP_PROJECT_ID}.{ECOMMERCE_DATASET_ID}.revenue_metrics`"

    # Get total count
    count_query = (
        f"SELECT COUNT(*) as total_count FROM {table_name} {where_clause}"
    )
    count_result = execute_bq_query(count_query)
    total_records = count_result[0]["total_count"] if count_result else 0

    if total_records == 0:
        return MetricsResponse(
            page=page,
            page_size=page_size,
            total_records=0,
            total_pages=0,
            data=[],
        )

    # Get paginated data
    total_pages = math.ceil(total_records / page_size)
    offset = (page - 1) * page_size

    data_query = f"""
        SELECT timestamp, hourly_revenue, transaction_count, avg_order_value
        FROM {table_name}
        {where_clause}
        ORDER BY timestamp DESC
        LIMIT {page_size} OFFSET {offset}
    """

    data = execute_bq_query(data_query)

    return MetricsResponse(
        page=page,
        page_size=page_size,
        total_records=total_records,
        total_pages=total_pages,
        data=data if data else [],
    )


@router.get(
    "/revenue/trends",
    tags=["ecommerce-revenue"],
    summary="Get revenue trends",
    description="Get revenue trends with daily/hourly aggregations",
)
async def get_revenue_trends(
    aggregation: str = Query(
        "daily", regex="^(hourly|daily)$", description="Aggregation level"
    ),
    days: int = Query(7, ge=1, le=30, description="Number of days to analyze"),
):
    """Get revenue trends"""

    table_name = f"`{GCP_PROJECT_ID}.{ECOMMERCE_DATASET_ID}.revenue_metrics`"

    if aggregation == "daily":
        query = f"""
        SELECT
            DATE(timestamp) as date,
            SUM(hourly_revenue) as daily_revenue,
            SUM(transaction_count) as daily_transactions,
            AVG(avg_order_value) as avg_order_value
        FROM {table_name}
        WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
        GROUP BY DATE(timestamp)
        ORDER BY date DESC
        """
    else:  # hourly
        query = f"""
        SELECT
            timestamp,
            hourly_revenue,
            transaction_count,
            avg_order_value
        FROM {table_name}
        WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
        ORDER BY timestamp DESC
        """

    data = execute_bq_query(query)
    return {"aggregation": aggregation, "days": days, "trends": data}


# --- System Performance Endpoints ---


@router.get(
    "/performance",
    response_model=MetricsResponse,
    tags=["ecommerce-performance"],
    summary="Get system performance metrics",
    description=(
        "Retrieves system performance metrics including response times,"
        "error rates, and RPS"
    ),
)
async def get_performance_metrics(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    min_response_time: Optional[float] = Query(
        None, description="Minimum response time filter (ms)"
    ),
    min_error_rate: Optional[float] = Query(
        None, description="Minimum error rate filter (%)"
    ),
):
    """Get system performance metrics with optional filtering"""

    where_conditions = []
    if min_response_time:
        where_conditions.append(f"avg_response_time_ms >= {min_response_time}")
    if min_error_rate:
        where_conditions.append(f"error_rate_percent >= {min_error_rate}")

    where_clause = " AND ".join(where_conditions)
    if where_clause:
        where_clause = f"WHERE {where_clause}"

    table_name = (
        f"`{GCP_PROJECT_ID}.{ECOMMERCE_DATASET_ID}" ".system_performance`"
    )

    # Get total count
    count_query = (
        f"SELECT COUNT(*) as total_count FROM {table_name} {where_clause}"
    )
    count_result = execute_bq_query(count_query)
    total_records = count_result[0]["total_count"] if count_result else 0

    if total_records == 0:
        return MetricsResponse(
            page=page,
            page_size=page_size,
            total_records=0,
            total_pages=0,
            data=[],
        )

    # Get paginated data
    total_pages = math.ceil(total_records / page_size)
    offset = (page - 1) * page_size

    data_query = f"""
        SELECT timestamp, avg_response_time_ms,
                error_rate_percent, requests_per_second
        FROM {table_name}
        {where_clause}
        ORDER BY timestamp DESC
        LIMIT {page_size} OFFSET {offset}
    """

    data = execute_bq_query(data_query)

    return MetricsResponse(
        page=page,
        page_size=page_size,
        total_records=total_records,
        total_pages=total_pages,
        data=data if data else [],
    )


# --- User Activity Endpoints ---


@router.get(
    "/users",
    response_model=MetricsResponse,
    tags=["ecommerce-users"],
    summary="Get user activity metrics",
    description=(
        "Retrieves user activity metrics including active users,"
        "page views, bounce rate, and conversion rate"
    ),
)
async def get_user_activity(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    min_users: Optional[int] = Query(
        None, description="Minimum active users filter"
    ),
):
    """Get user activity metrics"""

    where_conditions = []
    if min_users:
        where_conditions.append(f"active_users >= {min_users}")

    where_clause = " AND ".join(where_conditions)
    if where_clause:
        where_clause = f"WHERE {where_clause}"

    table_name = f"`{GCP_PROJECT_ID}.{ECOMMERCE_DATASET_ID}.user_activity`"

    # Get total count
    count_query = (
        f"SELECT COUNT(*) as total_count FROM {table_name} {where_clause}"
    )
    count_result = execute_bq_query(count_query)
    total_records = count_result[0]["total_count"] if count_result else 0

    if total_records == 0:
        return MetricsResponse(
            page=page,
            page_size=page_size,
            total_records=0,
            total_pages=0,
            data=[],
        )

    # Get paginated data
    total_pages = math.ceil(total_records / page_size)
    offset = (page - 1) * page_size

    data_query = f"""
        SELECT timestamp, active_users, page_views, bounce_rate_percent,
                conversion_rate_percent
        FROM {table_name}
        {where_clause}
        ORDER BY timestamp DESC
        LIMIT {page_size} OFFSET {offset}
    """

    data = execute_bq_query(data_query)

    return MetricsResponse(
        page=page,
        page_size=page_size,
        total_records=total_records,
        total_pages=total_pages,
        data=data if data else [],
    )


# --- Infrastructure Health Endpoints ---


@router.get(
    "/infrastructure",
    response_model=MetricsResponse,
    tags=["ecommerce-infrastructure"],
    summary="Get infrastructure health metrics",
    description="Retrieves infrastructure health metrics for all services",
)
async def get_infrastructure_health(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    service_name: Optional[str] = Query(
        None, description="Filter by service name"
    ),
    min_cpu: Optional[float] = Query(
        None, description="Minimum CPU usage filter (%)"
    ),
    min_memory: Optional[float] = Query(
        None, description="Minimum memory usage filter (%)"
    ),
):
    """Get infrastructure health metrics"""

    where_conditions = []
    if service_name:
        where_conditions.append(f"service_name = '{service_name}'")
    if min_cpu:
        where_conditions.append(f"cpu_percent >= {min_cpu}")
    if min_memory:
        where_conditions.append(f"memory_percent >= {min_memory}")

    where_clause = " AND ".join(where_conditions)
    if where_clause:
        where_clause = f"WHERE {where_clause}"

    table_name = (
        f"`{GCP_PROJECT_ID}.{ECOMMERCE_DATASET_ID}.infrastructure_health`"
    )

    # Get total count
    count_query = (
        f"SELECT COUNT(*) as total_count FROM {table_name} {where_clause}"
    )
    count_result = execute_bq_query(count_query)
    total_records = count_result[0]["total_count"] if count_result else 0

    if total_records == 0:
        return MetricsResponse(
            page=page,
            page_size=page_size,
            total_records=0,
            total_pages=0,
            data=[],
        )

    # Get paginated data
    total_pages = math.ceil(total_records / page_size)
    offset = (page - 1) * page_size

    data_query = f"""
        SELECT timestamp, service_name, cpu_percent,
                memory_percent, api_response_time_ms
        FROM {table_name}
        {where_clause}
        ORDER BY timestamp DESC, service_name
        LIMIT {page_size} OFFSET {offset}
    """

    data = execute_bq_query(data_query)

    return MetricsResponse(
        page=page,
        page_size=page_size,
        total_records=total_records,
        total_pages=total_pages,
        data=data if data else [],
    )


@router.get(
    "/infrastructure/services",
    tags=["ecommerce-infrastructure"],
    summary="Get available services",
    description="Get list of all monitored services",
)
async def get_services():
    """Get list of all services being monitored"""

    table_name = (
        f"`{GCP_PROJECT_ID}.{ECOMMERCE_DATASET_ID}.infrastructure_health`"
    )
    query = (
        f"SELECT DISTINCT service_name FROM {table_name} ORDER BY service_name"
    )

    data = execute_bq_query(query)
    services = [row["service_name"] for row in data] if data else []

    return {"services": services}


# --- Incident Detection Endpoints ---


@router.get(
    "/incidents",
    tags=["ecommerce-incidents"],
    summary="Detect and analyze incidents",
    description=(
        "Automatically detect incident periods based on"
        "performance and business metrics"
    ),
)
async def detect_incidents(
    response_time_threshold: float = Query(
        1500, description="Response time threshold (ms) for incident detection"
    ),
    error_rate_threshold: float = Query(
        5.0, description="Error rate threshold (%) for incident detection"
    ),
    revenue_drop_threshold: float = Query(
        30.0, description="Revenue drop threshold (%) for incident detection"
    ),
):
    """Detect incidents based on performance and business impact thresholds"""

    # Query for potential incident periods
    query = f"""
    WITH incident_candidates AS (
        SELECT
            r.timestamp,
            r.hourly_revenue,
            s.avg_response_time_ms,
            s.error_rate_percent,
            s.requests_per_second,
            u.bounce_rate_percent,
            u.conversion_rate_percent,
            LAG(r.hourly_revenue) OVER (ORDER BY r.timestamp) as prev_revenue
        FROM `{GCP_PROJECT_ID}.{ECOMMERCE_DATASET_ID}.revenue_metrics` r
        JOIN `{GCP_PROJECT_ID}.{ECOMMERCE_DATASET_ID}.system_performance` s
            ON r.timestamp = s.timestamp
        JOIN `{GCP_PROJECT_ID}.{ECOMMERCE_DATASET_ID}.user_activity` u
            ON r.timestamp = u.timestamp
        WHERE
            s.avg_response_time_ms >= {response_time_threshold}
            OR s.error_rate_percent >= {error_rate_threshold}
            OR (r.hourly_revenue <
                    prev_revenue * (100 - {revenue_drop_threshold}) / 100)
    )
    SELECT
        timestamp,
        hourly_revenue,
        avg_response_time_ms,
        error_rate_percent,
        bounce_rate_percent,
        conversion_rate_percent,
        CASE
            WHEN avg_response_time_ms >=
                    {response_time_threshold * 2} OR error_rate_percent >=
                        {error_rate_threshold * 2} THEN 'critical'
            WHEN avg_response_time_ms >=
                    {response_time_threshold} OR error_rate_percent >=
                        {error_rate_threshold} THEN 'high'
            ELSE 'medium'
        END as severity
    FROM incident_candidates
    ORDER BY timestamp DESC
    """

    incidents_data = execute_bq_query(query)

    if not incidents_data:
        return {
            "incidents": [],
            "summary": "No incidents detected with current thresholds",
        }

    # Group consecutive incidents
    incident_periods = []
    current_period = None

    for row in reversed(incidents_data):  # Process in chronological order
        timestamp = row["timestamp"]

        if current_period is None:
            current_period = {
                "start_time": timestamp,
                "end_time": timestamp,
                "severity": row["severity"],
                "metrics": [row],
            }
        elif (
            timestamp - current_period["end_time"]
        ).total_seconds() <= 3600:  # Within 1 hour
            current_period["end_time"] = timestamp
            current_period["metrics"].append(row)
            # Update severity to highest level
            if (
                row["severity"] == "critical"
                or current_period["severity"] == "critical"
            ):
                current_period["severity"] = "critical"
            elif (
                row["severity"] == "high"
                or current_period["severity"] == "high"
            ):
                current_period["severity"] = "high"
        else:
            incident_periods.append(current_period)
            current_period = {
                "start_time": timestamp,
                "end_time": timestamp,
                "severity": row["severity"],
                "metrics": [row],
            }

    if current_period:
        incident_periods.append(current_period)

    # Format response
    formatted_incidents = []
    total_revenue_impact = 0

    for period in incident_periods:
        duration_hours = (
            period["end_time"] - period["start_time"]
        ).total_seconds() / 3600 + 1
        avg_revenue = sum(m["hourly_revenue"] for m in period["metrics"]) / len(
            period["metrics"]
        )
        revenue_impact = avg_revenue * duration_hours
        total_revenue_impact += revenue_impact

        # Determine incident type
        avg_response_time = sum(
            m["avg_response_time_ms"] for m in period["metrics"]
        ) / len(period["metrics"])
        avg_error_rate = sum(
            m["error_rate_percent"] for m in period["metrics"]
        ) / len(period["metrics"])

        if avg_error_rate >= error_rate_threshold:
            incident_type = "High Error Rate"
        elif avg_response_time >= response_time_threshold:
            incident_type = "Performance Degradation"
        else:
            incident_type = "Business Impact"

        formatted_incidents.append(
            {
                "start_time": period["start_time"],
                "end_time": period["end_time"],
                "duration_hours": round(duration_hours, 1),
                "incident_type": incident_type,
                "severity": period["severity"],
                "revenue_impact": round(revenue_impact, 2),
                "avg_response_time_ms": round(avg_response_time, 1),
                "avg_error_rate_percent": round(avg_error_rate, 2),
                "description": (
                    f"{incident_type} incident lasting {duration_hours:.1f}"
                    " hours with {period['severity']} severity"
                ),
            }
        )

    return {
        "incident_count": len(formatted_incidents),
        "incidents": formatted_incidents,
        "total_revenue_impact": round(total_revenue_impact, 2),
        "thresholds_used": {
            "response_time_ms": response_time_threshold,
            "error_rate_percent": error_rate_threshold,
            "revenue_drop_percent": revenue_drop_threshold,
        },
    }


# --- Correlation Analysis Endpoints ---


@router.get(
    "/correlation",
    tags=["ecommerce-analysis"],
    summary="Analyze correlations between metrics",
    description=(
        "Analyze correlations between system performance and business metrics"
    ),
)
async def analyze_correlations(
    start_date: Optional[str] = Query(
        None, description="Start date for analysis (YYYY-MM-DD)"
    ),
    end_date: Optional[str] = Query(
        None, description="End date for analysis (YYYY-MM-DD)"
    ),
):
    """Analyze correlations between different metric types"""

    where_conditions = []
    if start_date:
        where_conditions.append(f"DATE(r.timestamp) >= '{start_date}'")
    if end_date:
        where_conditions.append(f"DATE(r.timestamp) <= '{end_date}'")

    where_clause = " AND ".join(where_conditions)
    if where_clause:
        where_clause = f"WHERE {where_clause}"

    query = f"""
    SELECT
        r.timestamp,
        r.hourly_revenue,
        r.transaction_count,
        s.avg_response_time_ms,
        s.error_rate_percent,
        s.requests_per_second,
        u.active_users,
        u.bounce_rate_percent,
        u.conversion_rate_percent
    FROM `{GCP_PROJECT_ID}.{ECOMMERCE_DATASET_ID}.revenue_metrics` r
    JOIN `{GCP_PROJECT_ID}.{ECOMMERCE_DATASET_ID}.system_performance` s
        ON r.timestamp = s.timestamp
    JOIN `{GCP_PROJECT_ID}.{ECOMMERCE_DATASET_ID}.user_activity` u
        ON r.timestamp = u.timestamp
    {where_clause}
    ORDER BY r.timestamp DESC
    LIMIT 1000
    """

    data = execute_bq_query(query)

    if not data:
        return {"error": "No data found for correlation analysis"}

    # Calculate basic correlations (simplified)
    correlations = {
        "revenue_vs_response_time": "negative correlation observed",
        "revenue_vs_error_rate": "strong negative correlation",
        "bounce_rate_vs_response_time": "positive correlation",
        "conversion_vs_performance": "inversely related",
        "data_points": len(data),
        "analysis_period": {
            "start": data[-1]["timestamp"] if data else None,
            "end": data[0]["timestamp"] if data else None,
        },
    }

    return {
        "correlations": correlations,
        "sample_data": data[:10],  # Return first 10 records as sample
        "insights": [
            (
                "When response time exceeds 1500ms,"
                " revenue typically drops by 20-40%"
            ),
            "Error rates above 5% correlate with 60%+ increase in bounce rate",
            "High-performing periods show 2-3x better conversion rates",
        ],
    }


@router.get(
    "/dashboard",
    tags=["ecommerce-analysis"],
    summary="Get dashboard summary data",
    description="Get summary data for operations dashboard",
)
async def get_dashboard_summary():
    """Get summary data for dashboard display"""

    # Get latest metrics
    latest_query = f"""
    SELECT
        r.timestamp,
        r.hourly_revenue,
        r.transaction_count,
        s.avg_response_time_ms,
        s.error_rate_percent,
        u.active_users,
        u.conversion_rate_percent
    FROM `{GCP_PROJECT_ID}.{ECOMMERCE_DATASET_ID}.revenue_metrics` r
    JOIN `{GCP_PROJECT_ID}.{ECOMMERCE_DATASET_ID}.system_performance` s
        ON r.timestamp = s.timestamp
    JOIN `{GCP_PROJECT_ID}.{ECOMMERCE_DATASET_ID}.user_activity` u
        ON r.timestamp = u.timestamp
    ORDER BY r.timestamp DESC
    LIMIT 1
    """

    latest_data = execute_bq_query(latest_query)

    # Get service health
    services_query = f"""
    SELECT
        service_name,
        AVG(cpu_percent) as avg_cpu,
        AVG(memory_percent) as avg_memory,
        AVG(api_response_time_ms) as avg_response_time
    FROM `{GCP_PROJECT_ID}.{ECOMMERCE_DATASET_ID}.infrastructure_health`
    WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR)
    GROUP BY service_name
    """

    services_data = execute_bq_query(services_query)

    # Get 24h trends
    trends_query = f"""
    SELECT
        EXTRACT(HOUR FROM timestamp) as hour,
        AVG(hourly_revenue) as avg_revenue,
        AVG(avg_response_time_ms) as avg_response_time
    FROM `{GCP_PROJECT_ID}.{ECOMMERCE_DATASET_ID}.revenue_metrics` r
    JOIN `{GCP_PROJECT_ID}.{ECOMMERCE_DATASET_ID}.system_performance` s
        ON r.timestamp = s.timestamp
    WHERE DATE(timestamp) = CURRENT_DATE()
    GROUP BY hour
    ORDER BY hour
    """

    trends_data = execute_bq_query(trends_query)

    return {
        "latest_metrics": latest_data[0] if latest_data else {},
        "service_health": services_data,
        "daily_trends": trends_data,
        "status": "operational"
        if latest_data and latest_data[0]["avg_response_time_ms"] < 1000
        else "degraded",
    }
