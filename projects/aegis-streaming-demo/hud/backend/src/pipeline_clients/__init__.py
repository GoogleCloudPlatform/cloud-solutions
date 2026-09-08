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

"""Pipeline Clients Package.

Pluggable controllers for Dataproc Serverless, Cloud Dataflow, and BigQuery
Continuous Queries.
"""

from pipeline_clients.base import BasePipelineClient
from pipeline_clients.continuous_query_client import (
    ContinuousQueryPipelineClient,
)
from pipeline_clients.dataflow_client import DataflowPipelineClient
from pipeline_clients.dataproc_client import DataprocPipelineClient
from pipeline_clients.factory import get_pipeline_client

__all__ = [
    "BasePipelineClient",
    "ContinuousQueryPipelineClient",
    "DataflowPipelineClient",
    "DataprocPipelineClient",
    "get_pipeline_client",
]
