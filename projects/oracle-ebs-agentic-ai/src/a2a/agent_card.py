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

"""AgentCard Pydantic model for A2A communication."""

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class AgentCard(BaseModel):
    """Schema representing an agent identity and registered capabilities."""

    name: str = Field(..., description="Unique agent identifier name")
    description: str = Field(
        ..., description="Description of agent responsibilities and domain"
    )
    endpoint_url: str = Field(
        ...,
        description="Endpoint for dispatching requests to this agent",
    )
    version: str = Field(
        default="1.0.0", description="Semantic version of the agent service"
    )
    capabilities: List[str] = Field(
        default_factory=list,
        description="List of capability tags supported by the agent",
    )
    endpoints: Dict[str, str] = Field(
        default_factory=dict, description="Mapping of route names to paths"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional custom metadata"
    )
