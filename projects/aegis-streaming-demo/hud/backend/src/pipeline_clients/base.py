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

"""Base abstract class for stream processing pipeline controllers."""

from abc import ABC, abstractmethod
from typing import Any, Dict


class BasePipelineClient(ABC):
    """Abstract interface defining pipeline monitoring and control methods."""

    @property
    @abstractmethod
    def engine_name(self) -> str:
        """Returns the identifier name of the stream processing engine."""

    @abstractmethod
    def refresh_status_sync(
        self, project_id: str, region: str
    ) -> Dict[str, Any]:
        """Queries cloud service and updates in-memory status cache."""

    @abstractmethod
    def get_status(self, project_id: str, region: str) -> Dict[str, Any]:
        """Returns cached pipeline status for sub-millisecond API responses."""

    @abstractmethod
    def start_pipeline(self, project_id: str, region: str) -> Dict[str, Any]:
        """Submits or starts a new stream processing pipeline job."""

    @abstractmethod
    def stop_pipeline(self, project_id: str, region: str) -> Dict[str, Any]:
        """Stops or cancels active stream processing pipeline jobs."""
