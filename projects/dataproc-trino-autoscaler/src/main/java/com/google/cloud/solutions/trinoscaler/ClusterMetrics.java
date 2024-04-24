/*
 * Copyright 2023 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package com.google.cloud.solutions.trinoscaler;

import static com.google.cloud.solutions.trinoscaler.Utils.emptyOrImmutableList;

import com.google.auto.value.AutoValue;
import com.google.common.collect.ImmutableList;
import java.util.List;

/** Record class to encapsulate machine cluster CPU Utilization metrics. */
@AutoValue
public abstract class ClusterMetrics {

  public abstract ClusterInformation clusterInformation();

  public abstract Double avgCpuUtilization();

  public abstract ImmutableList<WorkerMetrics> workerMetrics();

  public static ClusterMetrics create(
      ClusterInformation clusterInformation,
      Double avgCpuUtilization,
      List<WorkerMetrics> workerMetrics) {
    return new AutoValue_ClusterMetrics(
        clusterInformation, avgCpuUtilization, emptyOrImmutableList(workerMetrics));
  }

  /** Record class for a single worker's CPU utilization metric. */
  @AutoValue
  public abstract static class WorkerMetrics {
    public abstract String workerName();

    public abstract Double avgCpuUtilization();

    public static WorkerMetrics create(String workerName, Double avgCpuUtilization) {
      return new AutoValue_ClusterMetrics_WorkerMetrics(workerName, avgCpuUtilization);
    }
  }
}
