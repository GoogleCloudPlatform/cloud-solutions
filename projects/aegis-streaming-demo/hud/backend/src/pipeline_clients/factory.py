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

"""Factory for instantiating stream processing pipeline controllers."""

import logging
import os
from typing import Dict, Optional

from pipeline_clients.base import BasePipelineClient
from pipeline_clients.continuous_query_client import (
    ContinuousQueryPipelineClient,
)
from pipeline_clients.dataflow_client import DataflowPipelineClient
from pipeline_clients.dataproc_client import DataprocPipelineClient

logger = logging.getLogger("aegis-hud-backend")

_CLIENT_INSTANCES: Dict[str, BasePipelineClient] = {}


def get_pipeline_client(
    engine: Optional[str] = None,
) -> BasePipelineClient:
    """Returns the BasePipelineClient matching PIPELINE_ENGINE or argument.

    Maintains singleton instance per engine to preserve cache state.
    """
    engine_name = (
        (engine or os.getenv("PIPELINE_ENGINE", "dataproc")).strip().lower()
    )

    if engine_name not in _CLIENT_INSTANCES:
        if engine_name in ["dataflow", "beam", "apache_beam"]:
            logger.info(
                "Initializing DataflowPipelineClient (engine=%s)", engine_name
            )
            _CLIENT_INSTANCES[engine_name] = DataflowPipelineClient()
        elif engine_name in [
            "bq_continuous",
            "continuous_query",
            "low_code",
            "bigquery_continuous",
        ]:
            logger.info(
                "Initializing ContinuousQueryPipelineClient (engine=%s)",
                engine_name,
            )
            _CLIENT_INSTANCES[engine_name] = ContinuousQueryPipelineClient()
        else:
            logger.info(
                "Initializing DataprocPipelineClient (engine=%s)", engine_name
            )
            _CLIENT_INSTANCES[engine_name] = DataprocPipelineClient()

    return _CLIENT_INSTANCES[engine_name]
