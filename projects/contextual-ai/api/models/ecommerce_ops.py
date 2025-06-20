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
Pydantic models for representing data related to Ecommerce Operations.

This module defines the data structures used for various metrics and analyses
within the Ecommerce Operations monitoring and analysis system.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any
from datetime import datetime

# --- Pydantic Models for Ecommerce Operations ---


class RevenueMetric(BaseModel):
    timestamp: datetime
    hourly_revenue: float = Field(
        ..., description="Revenue for the hour in USD"
    )
    transaction_count: int = Field(..., description="Number of transactions")
    avg_order_value: float = Field(
        ..., description="Average order value in USD"
    )


class SystemPerformance(BaseModel):
    timestamp: datetime
    avg_response_time_ms: float = Field(
        ..., description="Average response time in milliseconds"
    )
    error_rate_percent: float = Field(
        ..., description="Error rate as percentage"
    )
    requests_per_second: float = Field(..., description="Requests per second")


class UserActivity(BaseModel):
    timestamp: datetime
    active_users: int = Field(..., description="Number of active users")
    page_views: int = Field(..., description="Total page views")
    bounce_rate_percent: float = Field(
        ..., description="Bounce rate as percentage"
    )
    conversion_rate_percent: float = Field(
        ..., description="Conversion rate as percentage"
    )


class InfrastructureHealth(BaseModel):
    timestamp: datetime
    service_name: str = Field(..., description="Name of the service")
    cpu_percent: float = Field(..., description="CPU usage percentage")
    memory_percent: float = Field(..., description="Memory usage percentage")
    api_response_time_ms: float = Field(
        ..., description="API response time in milliseconds"
    )


class IncidentPeriod(BaseModel):
    start_time: datetime
    end_time: datetime
    incident_type: str = Field(..., description="Type of incident")
    severity: str = Field(
        ..., description="Severity level: low, medium, high, critical"
    )
    description: str = Field(..., description="Description of the incident")
    affected_services: List[str] = Field(
        ..., description="List of affected services"
    )
    business_impact: Dict[str, Any] = Field(
        ..., description="Business impact metrics"
    )


class MetricsResponse(BaseModel):
    page: int = Field(..., example=1, description="Current page number")
    page_size: int = Field(
        ..., example=20, description="Number of records per page"
    )
    total_records: int = Field(
        ..., example=721, description="Total number of records"
    )
    total_pages: int = Field(
        ..., example=37, description="Total number of pages"
    )
    data: List[Dict[str, Any]] = Field(
        ..., description="List of metric records"
    )


class CorrelationAnalysis(BaseModel):
    timestamp: datetime
    revenue_impact: float = Field(
        ..., description="Revenue impact during the period"
    )
    performance_metrics: Dict[str, float] = Field(
        ..., description="System performance metrics"
    )
    user_behavior: Dict[str, float] = Field(
        ..., description="User behavior metrics"
    )
    infrastructure_status: List[Dict[str, Any]] = Field(
        ..., description="Infrastructure health for all services"
    )


class IncidentSummary(BaseModel):
    incident_count: int = Field(
        ..., description="Total number of incidents detected"
    )
    incidents: List[IncidentPeriod] = Field(
        ..., description="List of detected incidents"
    )
    total_revenue_impact: float = Field(
        ..., description="Total revenue impact across all incidents"
    )
    most_affected_service: str = Field(
        ..., description="Service most affected by incidents"
    )
