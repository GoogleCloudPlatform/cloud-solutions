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
    asset_id: str
    cpu_utilization: float
    temperature_c: float
    pressure_psi: float
    memory_utilization_pct: float
    status: str  # OK, WARNING, CRITICAL
    is_anomaly: bool
    timestamp: str


class TelemetryStreamPayload(BaseModel):
    timestamp: str
    assets: List[AssetState]


class InjectAnomalyRequest(BaseModel):
    asset_id: Optional[str] = Field(
        default=None,
        description="Target asset ID for anomaly injection (random if omitted)",
    )
    cpu_spike: Optional[float] = Field(default=96.5, ge=0.0, le=100.0)
    temp_spike: Optional[float] = Field(default=94.8, ge=0.0)
    pressure_spike: Optional[float] = Field(default=115.0, ge=0.0)


class RelieveAnomalyRequest(BaseModel):
    asset_id: str = Field(
        default="Asset-04",
        description="Target asset ID for anomaly relief/remediation",
    )


class AgentMitigateRequest(BaseModel):
    asset_id: str
    cpu_utilization: float
    temperature_c: float
    pressure_psi: float = 110.0
    memory_utilization_pct: float = 85.0
    status: str = "CRITICAL"
    event_type: str = "ANOMALY_DETECTED"
    additional_context: Optional[str] = None


class AgentApproveRequest(BaseModel):
    asset_id: str = Field(
        ..., description="Target asset ID whose mitigation plan was approved"
    )
    incident_id: Optional[str] = Field(
        default=None, description="Associated incident ID"
    )
    approved_by: Optional[str] = Field(
        default="Plant Operator (Console)",
        description="Operator identity who approved",
    )


class RunAnalyticsQueryRequest(BaseModel):
    query_id: str = Field(
        default="fleet_stress",
        description="ID of the pre-defined BigQuery query to run",
    )
