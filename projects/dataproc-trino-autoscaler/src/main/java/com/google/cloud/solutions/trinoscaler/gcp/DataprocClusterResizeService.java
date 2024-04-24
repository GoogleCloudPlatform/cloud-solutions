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

package com.google.cloud.solutions.trinoscaler.gcp;

import com.google.cloud.dataproc.v1.Cluster;
import com.google.cloud.dataproc.v1.ClusterConfig;
import com.google.cloud.dataproc.v1.ClusterControllerClient;
import com.google.cloud.dataproc.v1.InstanceGroupConfig;
import com.google.cloud.dataproc.v1.UpdateClusterRequest;
import com.google.cloud.solutions.trinoscaler.ClusterInformation;
import com.google.cloud.solutions.trinoscaler.ClusterMetrics;
import com.google.cloud.solutions.trinoscaler.proto.Clusters.RepairClusterRequest.NodePoolType;
import com.google.cloud.solutions.trinoscaler.proto.TrinoAutoscaler.ClusterScalingSpec;
import com.google.cloud.solutions.trinoscaler.proto.TrinoAutoscaler.WorkerScalingLogic;
import com.google.cloud.solutions.trinoscaler.scaler.ClusterResizeService;
import com.google.cloud.solutions.trinoscaler.scaler.ClusterScaleLogic;
import com.google.cloud.solutions.trinoscaler.scaler.ClusterScaleLogic.ClusterScaleLogicFactory;
import com.google.cloud.solutions.trinoscaler.scaler.ClusterScaleLogic.ResizeAction;
import com.google.cloud.solutions.trinoscaler.scaler.ResizeActionType;
import com.google.cloud.solutions.trinoscaler.trino.TrinoWorkerShutdownServiceFactory;
import com.google.common.flogger.GoogleLogger;
import com.google.common.flogger.StackSize;
import com.google.protobuf.FieldMask;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;

/** Dataproc specific implementation of a {@link ClusterResizeService}. */
public class DataprocClusterResizeService implements ClusterResizeService {

  private static final GoogleLogger logger = GoogleLogger.forEnclosingClass();

  private final ClusterScalingSpec clusterScalingSpec;
  private final ClusterControllerClient dataprocClusterControllerClient;
  private final TrinoWorkerShutdownServiceFactory trinoWorkerShutdownService;
  private final List<ClusterScaleLogicFactory> scaleLogicFactories;
  private final ExecutorService executorService;
  private final Duration coolOffDuration;
  private Instant lastClusterUpdateInstant;

  /** Simple all parameter constructor. */
  public DataprocClusterResizeService(
      ClusterScalingSpec clusterScalingSpec,
      ClusterControllerClient dataprocClusterControllerClient,
      TrinoWorkerShutdownServiceFactory trinoWorkerShutdownService,
      ExecutorService executorService,
      List<ClusterScaleLogicFactory> scaleLogicFactories) {
    this.clusterScalingSpec = clusterScalingSpec;
    this.dataprocClusterControllerClient = dataprocClusterControllerClient;
    this.trinoWorkerShutdownService = trinoWorkerShutdownService;
    this.executorService = executorService;
    this.scaleLogicFactories = scaleLogicFactories;
    this.coolOffDuration =
        Duration.parse(clusterScalingSpec.getTimingConfiguration().getCooldownDuration());
  }

  @Override
  public void resize(ClusterMetrics metrics) {

    if (lastClusterUpdateInstant != null
        && lastClusterUpdateInstant.plus(coolOffDuration).isAfter(Instant.now())) {
      logger.atInfo().log("NO_ACTION: Still in CoolOff Period");
      return;
    }

    var resizeAction = decideAction(metrics);
    try {
      switch (resizeAction.type()) {
        default:
        case NO_ACTION:
          logger.atInfo().log("Resize: NO_ACTION");
          return;

        case EXPAND:
          expandCluster(metrics.clusterInformation(), resizeAction);
          lastClusterUpdateInstant = Instant.now();
          return;

        case SHRINK:
          shrinkCluster(resizeAction);
          lastClusterUpdateInstant = Instant.now();
      }
    } catch (Exception exception) {
      logger.atSevere().withCause(exception).withStackTrace(StackSize.SMALL).log(
          "Error resizing cluster: Action: %s", resizeAction);
    }
  }

  private void expandCluster(ClusterInformation clusterInfo, ResizeAction expandAction)
      throws ExecutionException, InterruptedException {

    var fieldUpdateMask = FieldMask.newBuilder();
    var clusterConfig = ClusterConfig.newBuilder();

    expandAction
        .getNodeGroupType(NodePoolType.SECONDARY_WORKER_POOL)
        .ifPresent(
            secondaryNodePool -> {
              fieldUpdateMask.addPaths("config.secondary_worker_config.num_instances");
              clusterConfig.setSecondaryWorkerConfig(
                  InstanceGroupConfig.newBuilder()
                      .setNumInstances(secondaryNodePool.newWorkerCount()));
            });

    var updateOperationName =
        dataprocClusterControllerClient
            .updateClusterAsync(
                UpdateClusterRequest.newBuilder()
                    .setProjectId(clusterInfo.projectId())
                    .setRegion(clusterInfo.region())
                    .setClusterName(clusterInfo.name())
                    .setUpdateMask(fieldUpdateMask)
                    .setCluster(Cluster.newBuilder().setConfig(clusterConfig))
                    .build())
            .getInitialFuture()
            .get()
            .getName();
    logger.atInfo().log(
        "Cluster EXPAND started Operation: "
            + updateOperationName
            + "\n"
            + expandAction.nodeGroups());
  }

  private void shrinkCluster(ResizeAction shrinkAction) {
    shrinkAction.nodeGroups().stream()
        .map(ClusterScaleLogic.NodeGroup::shrinkWorkersList)
        .flatMap(List::stream)
        .map(trinoWorkerShutdownService::createWorkerShutdownTask)
        .forEach(executorService::execute);
  }

  /**
   * Identifies {@link ResizeActionType} based on cluster-metrics and returns a {@link
   * ClusterScaleLogic.ResizeAction} based on the provided ClusterScaleLogic instance.
   */
  private ResizeAction decideAction(ClusterMetrics clusterMetrics) {

    if (clusterMetrics.avgCpuUtilization() == null || clusterMetrics.avgCpuUtilization() == 0.0) {
      logger.atInfo().log("Cluster: %s%nAction: NO_ACTION as metrics missing.");
      return ResizeAction.noAction();
    }

    int workersCount = clusterMetrics.workerMetrics().size();

    var cpuUtilizationAction =
        Math.signum(
            Math.floor(
                (clusterMetrics.avgCpuUtilization() - clusterScalingSpec.getCpuThresholdLow())
                    / (clusterScalingSpec.getCpuThresholdHigh()
                        - clusterScalingSpec.getCpuThresholdLow())));

    if (cpuUtilizationAction == 1
        && workersCount < clusterScalingSpec.getSecondaryPool().getMaxInstances()) {
      return getScaleLogic(clusterScalingSpec.getClusterExpandLogic())
          .computeNewWorkers(clusterMetrics);

    } else if (cpuUtilizationAction == -1
        && workersCount > clusterScalingSpec.getSecondaryPool().getMinInstances()) {
      return getScaleLogic(clusterScalingSpec.getClusterShrinkLogic())
          .computeShrinkWorkers(clusterMetrics);
    }

    return ResizeAction.noAction();
  }

  private ClusterScaleLogic getScaleLogic(WorkerScalingLogic scalingLogic) {
    return scaleLogicFactories.stream()
        .filter(logicFactory -> scalingLogic.getAlgo().equals(logicFactory.scalingAlgorithm()))
        .map(scalingLogicFactory -> scalingLogicFactory.create(clusterScalingSpec, scalingLogic))
        .findFirst()
        .orElseThrow();
  }
}
