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

import static com.google.cloud.solutions.trinoscaler.Utils.emptyOrImmutableList;

import com.google.auto.value.AutoValue;
import com.google.cloud.solutions.trinoscaler.ClusterMetrics;
import com.google.cloud.solutions.trinoscaler.proto.Clusters.RepairClusterRequest.NodePoolType;
import com.google.cloud.solutions.trinoscaler.proto.TrinoAutoscaler.ClusterScalingSpec;
import com.google.cloud.solutions.trinoscaler.proto.TrinoAutoscaler.ScalingAlgorithm;
import com.google.cloud.solutions.trinoscaler.proto.TrinoAutoscaler.WorkerScalingLogic;
import com.google.common.base.Preconditions;
import com.google.common.collect.ImmutableList;
import java.util.List;
import java.util.Optional;
import org.checkerframework.checker.nullness.qual.Nullable;

/**
 * A ClusterScaleLogic provides methods to compute nodes to add or remove.
 *
 * <p>An implementation class provides implementation to define the new nodes to add or specific
 * nodes to remove based on current {@link ClusterMetrics}
 */
public interface ClusterScaleLogic {

  /** Returns the {@link ScalingAlgorithm} implemented by the instance of ClusterScaleLogic. */
  ScalingAlgorithm scalingAlgorithm();

  /** Returns the number of workers the cluster should have based on scaling logic. */
  ResizeAction computeNewWorkers(ClusterMetrics clusterMetrics);

  /** Returns the reduced node count and specific nodes to shutdown. */
  ResizeAction computeShrinkWorkers(ClusterMetrics clusterMetrics);

  /** Factory for ClusterScaleLogic instances. */
  interface ClusterScaleLogicFactory {

    ScalingAlgorithm scalingAlgorithm();

    ClusterScaleLogic create(ClusterScalingSpec scalingSpec, WorkerScalingLogic workerScalingLogic);
  }

  /**
   * Model class to encapsulate the nodeGroups that need to be updated as part of the resize
   * operation.
   */
  @AutoValue
  abstract class ResizeAction {

    public abstract ResizeActionType type();

    public abstract ImmutableList<NodeGroup> nodeGroups();

    public Optional<NodeGroup> getNodeGroupType(NodePoolType type) {
      return nodeGroups().stream().filter(nodeGroup -> type.equals(nodeGroup.type())).findFirst();
    }

    public ResizeAction withNodeGroups(List<NodeGroup> nodeGroups) {
      return create(type(), nodeGroups);
    }

    public static ResizeAction noAction() {
      return create(ResizeActionType.NO_ACTION, null);
    }

    public static ResizeAction create(ResizeActionType type, @Nullable List<NodeGroup> nodeGroups) {
      return new AutoValue_ClusterScaleLogic_ResizeAction(type, emptyOrImmutableList(nodeGroups));
    }
  }

  /** Encapsulates the updates to a NodeGroup of workers. */
  @AutoValue
  abstract class NodeGroup {

    public abstract NodePoolType type();

    /** The updated count of workers when resize-action is {@code EXPAND}. */
    @Nullable
    public abstract Integer newWorkerCount();

    /**
     * The list of worker machine names to be removed from the node-pool for {@code SHRINK}
     * operation.
     */
    public abstract ImmutableList<String> shrinkWorkersList();

    public NodeGroup withNewWorkerCount(int newWorkerCount) {
      return create(type(), newWorkerCount, shrinkWorkersList());
    }

    /** Static helper function to instantiate the model object. */
    public static NodeGroup create(
        NodePoolType type, Integer newWorkerCount, List<String> shrinkWorkersList) {

      Preconditions.checkArgument(
          (newWorkerCount == null && shrinkWorkersList != null && !shrinkWorkersList.isEmpty())
              || (newWorkerCount != null
                  && (shrinkWorkersList == null || shrinkWorkersList.isEmpty())),
          "Only provide oneof newWorkerCount or shrinkWorkerList, found both or none");

      return new AutoValue_ClusterScaleLogic_NodeGroup(
          type, newWorkerCount, emptyOrImmutableList(shrinkWorkersList));
    }
  }
}
