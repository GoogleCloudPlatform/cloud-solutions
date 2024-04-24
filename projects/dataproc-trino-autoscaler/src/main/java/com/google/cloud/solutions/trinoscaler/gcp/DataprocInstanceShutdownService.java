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

import com.google.auth.oauth2.AccessToken;
import com.google.cloud.compute.v1.GetInstanceRequest;
import com.google.cloud.compute.v1.InstancesClient;
import com.google.cloud.compute.v1.InstancesSetLabelsRequest;
import com.google.cloud.compute.v1.Items;
import com.google.cloud.compute.v1.SetLabelsInstanceRequest;
import com.google.cloud.compute.v1.SetMetadataInstanceRequest;
import com.google.cloud.solutions.trinoscaler.ClusterInformation;
import com.google.cloud.solutions.trinoscaler.Factory;
import com.google.cloud.solutions.trinoscaler.proto.Clusters.RepairClusterRequest;
import com.google.cloud.solutions.trinoscaler.proto.Clusters.RepairClusterRequest.NodePool;
import com.google.cloud.solutions.trinoscaler.proto.Clusters.RepairClusterRequest.NodePoolType;
import com.google.cloud.solutions.trinoscaler.proto.Clusters.RepairClusterRequest.RepairAction;
import com.google.cloud.solutions.trinoscaler.scaler.WorkerShutdownService;
import com.google.common.collect.Queues;
import com.google.common.flogger.GoogleLogger;
import com.google.protobuf.InvalidProtocolBufferException;
import com.google.protobuf.util.JsonFormat;
import java.io.IOException;
import java.util.ArrayList;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.ExecutionException;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;

/**
 * Dataproc specific implementation that first add the shutting-down metadata flag and then resizes
 * the Dataproc cluster to stop a specific worker machine.
 */
public class DataprocInstanceShutdownService implements WorkerShutdownService, Runnable {
  static final String TRINO_WORKER_SHUTTING_DOWN_LABEL_KEY = "trino-autoscaler-shuttingdown";

  private static final String ENDPOINT = "/v1/projects/%1$s/regions/%2$s/clusters/%3$s:repair";
  private static final String HOSTNAME = "https://dataproc.googleapis.com";

  private static final GoogleLogger logger = GoogleLogger.forEnclosingClass();

  private final ClusterInformation clusterInformation;
  private final Factory<InstancesClient> gceInstancesClientFactory;
  private final Factory<AccessToken> credentialsProvider;
  private final Factory<OkHttpClient> okHttpClientFactory;
  private final BlockingQueue<String> instanceTerminationQueue;

  /** Simple all parameter constructor. */
  public DataprocInstanceShutdownService(
      ClusterInformation clusterInformation,
      Factory<InstancesClient> gceInstancesClientFactory,
      Factory<AccessToken> credentialsProvider,
      Factory<OkHttpClient> okHttpClientFactory) {
    this.clusterInformation = clusterInformation;
    this.gceInstancesClientFactory = gceInstancesClientFactory;
    this.credentialsProvider = credentialsProvider;
    this.okHttpClientFactory = okHttpClientFactory;
    this.instanceTerminationQueue = Queues.newLinkedBlockingQueue();
  }

  @Override
  public void markWorkerForShutdown(String workerName) throws IOException {
    try (var gceInstancesClient = gceInstancesClientFactory.create()) {

      var instance =
          gceInstancesClient.get(
              GetInstanceRequest.newBuilder()
                  .setProject(clusterInformation.projectId())
                  .setZone(clusterInformation.zone())
                  .setInstance(workerName)
                  .build());

      logger.atInfo().log(
          "Applying GCE Tag for shutting-down: %s [finger=%s]",
          workerName, instance.getLabelFingerprint());

      gceInstancesClient.setLabelsAsync(
          SetLabelsInstanceRequest.newBuilder()
              .setProject(clusterInformation.projectId())
              .setZone(clusterInformation.zone())
              .setInstance(workerName)
              .setInstancesSetLabelsRequestResource(
                  InstancesSetLabelsRequest.newBuilder()
                      .setLabelFingerprint(instance.getLabelFingerprint())
                      .putAllLabels(instance.getLabelsMap())
                      .putLabels(TRINO_WORKER_SHUTTING_DOWN_LABEL_KEY, "true")
                      .build())
              .build());
      gceInstancesClient.setMetadataAsync(
          SetMetadataInstanceRequest.newBuilder()
              .setProject(clusterInformation.projectId())
              .setZone(clusterInformation.zone())
              .setInstance(workerName)
              .setMetadataResource(
                  instance.getMetadata().toBuilder()
                      .addItems(
                          Items.newBuilder()
                              .setKey(TRINO_WORKER_SHUTTING_DOWN_LABEL_KEY)
                              .setValue("true")
                              .build())
                      .build())
              .build());

      logger.atInfo().log("Applied GCE Tag for shutting-down: %s", workerName);
    }
  }

  @Override
  public void shutdownWorker(String workerName) {
    try {
      suspendGceInstance(workerName);
      instanceTerminationQueue.put(workerName);
      logger.atInfo().log("Added To Termination Queue: %s", workerName);
    } catch (IOException | ExecutionException | InterruptedException interruptedException) {
      var msg = "Unable to add worker for termination: " + workerName;
      logger.atSevere().withCause(interruptedException).log(msg);
      throw new RuntimeException(msg, interruptedException);
    }
  }

  private void suspendGceInstance(String workerName)
      throws IOException, ExecutionException, InterruptedException {

    try (var gceInstancesClient = gceInstancesClientFactory.create()) {
      var suspendOperation =
          gceInstancesClient.suspendAsync(
              clusterInformation.projectId(), clusterInformation.zone(), workerName);
      logger.atInfo().log(
          "suspending worker %s [operation: %s]", workerName, suspendOperation.getName());
    }
  }

  @Override
  public void run() {

    var instancesToDelete = new ArrayList<String>();
    instanceTerminationQueue.drainTo(instancesToDelete);

    if (instancesToDelete.isEmpty()) {
      logger.atInfo().log("No workers to terminate");
      return;
    }

    logger.atInfo().log("Terminating workers: %s", instancesToDelete);

    try {
      var dataprocInstanceDeleteRequest =
          new Request.Builder()
              .url(
                  HOSTNAME
                      + String.format(
                          ENDPOINT,
                          clusterInformation.projectId(),
                          clusterInformation.region(),
                          clusterInformation.name()))
              .post(
                  RequestBody.create(
                      JsonFormat.printer()
                          .print(
                              RepairClusterRequest.newBuilder()
                                  .addNodePools(
                                      NodePool.newBuilder()
                                          .addAllInstanceNames(instancesToDelete)
                                          .setId(NodePoolType.SECONDARY_WORKER_POOL)
                                          .setRepairAction(RepairAction.DELETE))
                                  .build()),
                      MediaType.get("application/json")))
              .addHeader("Authorization", "Bearer " + credentialsProvider.create().getTokenValue())
              .build();

      try (var response =
          okHttpClientFactory.create().newCall(dataprocInstanceDeleteRequest).execute()) {

        logger.atInfo().log(
            "Start Cluster repair delete for: %s %n Operation Id: %s",
            instancesToDelete, response.body().string());
      }

    } catch (InvalidProtocolBufferException invalidProtoException) {
      logger.atSevere().withCause(invalidProtoException).log("invalid proto during request");
    } catch (IOException ioException) {
      logger.atSevere().withCause(ioException).log(
          "Error cluster repair-delete: %s", instancesToDelete);
      instancesToDelete.forEach(instanceTerminationQueue::offer);
    }
  }
}
