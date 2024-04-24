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

package com.google.cloud.solutions.trinoscaler.scaler;

import com.google.cloud.solutions.trinoscaler.ClusterMetrics;
import com.google.cloud.solutions.trinoscaler.proto.Clusters.RepairClusterRequest.NodePoolType;
import com.google.cloud.solutions.trinoscaler.proto.TrinoAutoscaler.ClusterScalingSpec;
import com.google.cloud.solutions.trinoscaler.proto.TrinoAutoscaler.ScalingAlgorithm;
import com.google.cloud.solutions.trinoscaler.proto.TrinoAutoscaler.WorkerScalingLogic;
import com.google.common.collect.ImmutableList;
import com.google.common.flogger.GoogleLogger;
import java.util.Comparator;
import java.util.stream.Collectors;

/**
 * Implementation that changes the worker count in steps for scaling needs based the provided
 * configuration.
 */
public class StepWorkerScaleLogic implements ClusterScaleLogic {

  private static final GoogleLogger logger = GoogleLogger.forEnclosingClass();

  private final ClusterScalingSpec scalingSpec;
  private final int workerStep;

  public StepWorkerScaleLogic(
      ClusterScalingSpec scalingSpec, WorkerScalingLogic workerScalingLogic) {
    this.scalingSpec = scalingSpec;
    this.workerStep = (int) workerScalingLogic.getValue();
  }

  public static ClusterScaleLogicFactory factory() {
    return new StepWorkerScaleLogicFactory();
  }

  @Override
  public ScalingAlgorithm scalingAlgorithm() {
    return ScalingAlgorithm.WORKER_UNITS;
  }

  @Override
  public ResizeAction computeNewWorkers(ClusterMetrics clusterMetrics) {

    var currentWorkerCount = clusterMetrics.workerMetrics().size();

    var newWorkerCount =
        Math.min(currentWorkerCount + workerStep, scalingSpec.getSecondaryPool().getMaxInstances());

    if (currentWorkerCount == newWorkerCount) {
      logger.atInfo().log("ScaleUP: NO_ACTION");
      return ResizeAction.noAction();
    }

    return ResizeAction.create(
        ResizeActionType.EXPAND,
        ImmutableList.of(
            NodeGroup.create(NodePoolType.SECONDARY_WORKER_POOL, newWorkerCount, null)));
  }

  @Override
  public ResizeAction computeShrinkWorkers(ClusterMetrics clusterMetrics) {

    var shrinkableWorkersCount =
        Math.min(
            workerStep,
            clusterMetrics.workerMetrics().size()
                - scalingSpec.getSecondaryPool().getMinInstances());

    logger.atInfo().log("Reducing workers: %s", shrinkableWorkersCount);

    var shrinkWorkers =
        clusterMetrics.workerMetrics().stream()
            .sorted(Comparator.comparing(ClusterMetrics.WorkerMetrics::avgCpuUtilization))
            .limit(shrinkableWorkersCount)
            .map(ClusterMetrics.WorkerMetrics::workerName)
            .collect(Collectors.toList());

    logger.atInfo().log("ShrinkWorkersNames: %s", shrinkWorkers);

    return shrinkWorkers.isEmpty()
        ? ResizeAction.noAction()
        : ResizeAction.create(
            ResizeActionType.SHRINK,
            ImmutableList.of(
                NodeGroup.create(NodePoolType.SECONDARY_WORKER_POOL, null, shrinkWorkers)));
  }

  static class StepWorkerScaleLogicFactory implements ClusterScaleLogicFactory {

    @Override
    public ScalingAlgorithm scalingAlgorithm() {
      return ScalingAlgorithm.WORKER_UNITS;
    }

    @Override
    public ClusterScaleLogic create(
        ClusterScalingSpec scalingSpec, WorkerScalingLogic workerScalingLogic) {

      return new StepWorkerScaleLogic(scalingSpec, workerScalingLogic);
    }
  }
}
