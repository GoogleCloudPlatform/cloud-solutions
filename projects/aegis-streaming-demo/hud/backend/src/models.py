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

"""Pydantic data schemas for HUD backend models."""

from typing import List, Optional

from pydantic import BaseModel, Field


class AssetState(BaseModel):
    """Operational telemetry state and latency metrics for an asset."""

    asset_id: str
    cpu_utilization: float
    temperature_c: float
    pressure_psi: float
    memory_utilization_pct: float
    status: str  # OK, WARNING, CRITICAL
    is_anomaly: bool
    timestamp: str
    ingestion_timestamp_ms: Optional[int] = Field(
        default=None,
        description="Millisecond epoch timestamp when produced by simulator",
    )
    db_insert_timestamp_ms: Optional[int] = Field(
        default=None,
        description="Millisecond epoch timestamp when Spark wrote to Bigtable",
    )
    pipeline_latency_ms: Optional[int] = Field(
        default=None,
        description=(
            "End-to-end latency in ms "
            "(db_insert_timestamp_ms - ingestion_timestamp_ms)"
        ),
    )


class TelemetryStreamPayload(BaseModel):
    """SSE stream payload containing fleet-wide asset states."""

    timestamp: str
    assets: List[AssetState]


class InjectAnomalyRequest(BaseModel):
    """Request schema for injecting a synthetic anomaly into an asset."""

    asset_id: Optional[str] = Field(
        default=None,
        min_length=8,
        max_length=32,
        pattern=r"^Asset-\d{2}$",
        description="Target asset ID for anomaly injection (random if omitted)",
    )
    cpu_spike: Optional[float] = Field(default=96.5, ge=0.0, le=100.0)
    temp_spike: Optional[float] = Field(default=94.8, ge=0.0)
    pressure_spike: Optional[float] = Field(default=115.0, ge=0.0)


class RelieveAnomalyRequest(BaseModel):
    """Request schema for relieving an active anomaly on an asset."""

    asset_id: str = Field(
        default="Asset-04",
        min_length=8,
        max_length=32,
        pattern=r"^Asset-\d{2}$",
        description="Target asset ID for anomaly relief/remediation",
    )


class AgentMitigateRequest(BaseModel):
    """Request schema for triggering AI Agent Root Cause Analysis."""

    asset_id: str = Field(
        ...,
        min_length=8,
        max_length=32,
        pattern=r"^Asset-\d{2}$",
    )
    cpu_utilization: float = Field(..., ge=0.0, le=100.0)
    temperature_c: float
    pressure_psi: float = Field(default=110.0, ge=0.0)
    memory_utilization_pct: float = Field(default=85.0, ge=0.0, le=100.0)
    status: str = Field(default="CRITICAL", max_length=32)
    event_type: str = Field(default="ANOMALY_DETECTED", max_length=64)
    additional_context: Optional[str] = Field(default=None, max_length=1000)


class AgentApproveRequest(BaseModel):
    """Request schema for HITL operator approval of agent remediation."""

    asset_id: str = Field(
        ...,
        min_length=8,
        max_length=32,
        pattern=r"^Asset-\d{2}$",
        description="Target asset ID whose mitigation plan was approved",
    )
    incident_id: Optional[str] = Field(
        default=None, max_length=64, description="Associated incident ID"
    )
    approved_by: Optional[str] = Field(
        default="Plant Operator (Console)",
        max_length=128,
        description="Operator identity who approved",
    )


class RunAnalyticsQueryRequest(BaseModel):
    """Request schema for executing a pre-defined BigQuery analytics query."""

    query_id: str = Field(
        default="fleet_stress",
        max_length=64,
        description="ID of the pre-defined BigQuery query to run",
    )
