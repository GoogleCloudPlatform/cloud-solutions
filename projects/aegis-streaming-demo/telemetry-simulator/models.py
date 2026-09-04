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

"""Project Aegis - Telemetry Simulator Service Models.

Pydantic schemas for request payloads, responses, and asset telemetry data.
"""

from datetime import datetime, timezone
from typing import List

from pydantic import BaseModel, Field


class AssetState(BaseModel):
    """Represents the telemetry state for a single simulated asset."""

    asset_id: str = Field(
        ..., description="Unique asset identifier (e.g. Asset-01)"
    )
    cpu_utilization: float = Field(
        ..., description="CPU utilization percentage (0-100%)"
    )
    temperature_c: float = Field(
        ..., description="Operating temperature in degrees Celsius"
    )
    pressure_psi: float = Field(..., description="Operating pressure in PSI")
    memory_utilization_pct: float = Field(
        ..., description="Memory utilization percentage (0-100%)"
    )
    status: str = Field(
        ..., description="Operational status flag (OK, WARNING, CRITICAL)"
    )
    is_anomaly: bool = Field(
        default=False,
        description="Flag indicating if asset is in anomalous state",
    )
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp")


class StartStreamRequest(BaseModel):
    """Optional payload for start-stream to configure backpressure rate."""

    rate_msgs_per_sec: int = Field(
        default=100,
        ge=1,
        le=5000,
        description=(
            "Target message generation throughput in msgs/sec across fleet"
            " (default 100)"
        ),
    )


class StreamActionResponse(BaseModel):
    """Response returned by start-stream and stop-stream endpoints."""

    status: str = Field(
        ..., description="Current streaming status (running or stopped)"
    )
    running: bool = Field(
        ..., description="Boolean indicating if stream is active"
    )
    target_rate_msgs_per_sec: int = Field(
        default=100, description="Configured target throughput in msgs/sec"
    )
    message: str = Field(..., description="Descriptive status message")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class CreateAnomalyResponse(BaseModel):
    """Response returned when an anomaly is injected into a random asset."""

    status: str = Field(default="anomaly_created", description="Action status")
    message: str = Field(
        default="Thermal and compute anomaly injected into random fleet asset.",
        description="Descriptive message",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class FixAnomalyRequest(BaseModel):
    """Payload schema for fix-anomoly (called strictly by the Agent)."""

    asset_id: str = Field(
        ...,
        description="Target asset ID to normalize back to healthy baseline",
        json_schema_extra={"example": "Asset-04"},
    )


class FixAnomalyResponse(BaseModel):
    """Response returned when an asset's anomaly is normalized."""

    status: str = Field(
        default="normalized", description="Normalization status"
    )
    message: str = Field(..., description="Descriptive message")
    asset_id: str = Field(..., description="Identifier of the normalized asset")
    asset: AssetState = Field(
        ..., description="Normalized asset telemetry state"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class StreamStatusResponse(BaseModel):
    """Response returned by GET /api/stream-status with 5-minute metrics."""

    status: str = Field(
        ..., description="Current streaming status (running or stopped)"
    )
    running: bool = Field(
        ..., description="Boolean indicating if streaming loop is active"
    )
    target_rate_msgs_per_sec: int = Field(
        default=100, description="Configured target message rate in msgs/sec"
    )
    total_messages_last_5m: int = Field(
        ..., description="Total Kafka messages sent in the last 5 minutes"
    )
    rate_msgs_per_sec_5m: float = Field(
        ...,
        description="Message throughput rate (msgs/sec) over last 5 minutes",
    )
    rate_formatted: str = Field(
        ...,
        description="Formatted message rate string (e.g. '100.0 msgs/sec')",
    )
    active_anomalies: List[str] = Field(
        default_factory=list,
        description="List of asset IDs currently exhibiting anomalies",
    )
    assets_count: int = Field(
        default=15, description="Total number of simulated assets"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
