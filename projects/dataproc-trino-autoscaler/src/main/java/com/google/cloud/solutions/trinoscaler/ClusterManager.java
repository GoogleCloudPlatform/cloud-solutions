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

import com.google.cloud.solutions.trinoscaler.proto.TrinoAutoscaler.ClusterScalingSpec;
import com.google.cloud.solutions.trinoscaler.scaler.ClusterResizeService;
import com.google.common.flogger.GoogleLogger;
import com.google.common.flogger.StackSize;
import java.io.IOException;

/**
 * Provides core scaling workflow implementation.
 *
 * <p>ClusterManager retrieves worker cpu metrics to decide cluster EXPAND or SHRINK
 *
 * <p>For <b>SHRINK</b> operation Identifies the workers that need to be shut and waits for their
 * decommissioning.
 */
public class ClusterManager implements Runnable {

  private static final GoogleLogger logger = GoogleLogger.forEnclosingClass();
  private final ClusterInspectionService clusterInspectionService;
  private final ClusterResizeService clusterResizeService;

  private final ClusterScalingSpec config;

  /** Simple all parameter constructor. */
  public ClusterManager(
      ClusterScalingSpec config,
      ClusterInspectionService clusterInspectionService,
      ClusterResizeService clusterResizeService) {
    this.config = config;
    this.clusterInspectionService = clusterInspectionService;
    this.clusterResizeService = clusterResizeService;
  }

  @Override
  public void run() {
    try {
      logger.atInfo().log("Inspecting Cluster");
      var clusterMetrics = clusterInspectionService.inspectCluster();
      clusterResizeService.resize(clusterMetrics);
    } catch (IOException ioException) {
      logger.atSevere().withCause(ioException).withStackTrace(StackSize.SMALL).log(
          "error managing cluster");
    }
  }
}
