# Copyright 2025 Google LLC

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Factory class for creating Metric instances based on the metric name."""

import enum
from typing import Any, Dict, Optional

from . import metrics


class MetricName(enum.Enum):
    """Enum for the names of the metrics."""

    SHOT_CHANGE = "shot_change"
    UVQ = "uvq"
    BLURRINESS = "blurriness"
    TEXT_ADHERENCE = "text_adherence"
    LOOP_DETECTION = "loop_detection"
    AIPLAN_ADHERENCE = "ai_plan_adherence"


class MetricFactory:
    """Factory class for creating Metric instances based on the metric name."""

    @classmethod
    def get_metric(
        cls,
        metric_name: str,
        _metric_flags: Optional[Dict[str, Any]] = None,
    ) -> metrics.Metrics:
        """Returns an instance of a Metric subclass.

        Args:
            metric_name: MetricName The name of the metric to create an
                instance of.
            _metric_flags: Optional dictionary containing flag values for
                metrics (currently unused).

        Returns:
            Metric: An instance of a Metric subclass (e.g., ShotChange).

        Raises:
            ValueError: If the metric_name does not correspond to any known
                Metric subclass.
        """
        if metric_name == MetricName.SHOT_CHANGE.value:
            return metrics.ShotChange()
        elif metric_name == MetricName.BLURRINESS.value:
            return metrics.Blurriness()
        elif metric_name == MetricName.LOOP_DETECTION.value:
            return metrics.LoopDetection()
        else:
            raise ValueError(f"Unknown metric: {metric_name}")
