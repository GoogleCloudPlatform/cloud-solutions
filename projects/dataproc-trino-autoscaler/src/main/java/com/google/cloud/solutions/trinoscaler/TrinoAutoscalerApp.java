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

import static com.google.cloud.solutions.trinoscaler.Utils.readFileAsPb;

import com.google.auth.oauth2.AccessToken;
import com.google.cloud.solutions.trinoscaler.gcp.ApplicationDefaultCredentialProvider;
import com.google.cloud.solutions.trinoscaler.gcp.DataprocClusterInformationService;
import com.google.cloud.solutions.trinoscaler.gcp.DataprocClusterInspectionService;
import com.google.cloud.solutions.trinoscaler.gcp.DataprocClusterResizeService;
import com.google.cloud.solutions.trinoscaler.gcp.DataprocInstanceShutdownService;
import com.google.cloud.solutions.trinoscaler.gcp.ProductionGoogleCloudServicesFactory;
import com.google.cloud.solutions.trinoscaler.proto.TrinoAutoscaler.ClusterScalingSpec;
import com.google.cloud.solutions.trinoscaler.scaler.StepWorkerScaleLogic;
import com.google.cloud.solutions.trinoscaler.trino.TrinoWorkerShutdownServiceFactory;
import com.google.common.annotations.VisibleForTesting;
import com.google.common.flogger.GoogleLogger;
import com.google.protobuf.TextFormat;
import java.io.IOException;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import okhttp3.OkHttpClient;

/** Autoscaling application that runs on the main thread to provide the scaling functionality. */
public class TrinoAutoscalerApp {
  private static final GoogleLogger logger = GoogleLogger.forEnclosingClass();

  private final ClusterInformation clusterInformation;
  private final GoogleCloudServicesFactory googleCloudServicesFactory;
  private final ClusterScalingSpec autoscaleSpec;
  private final Factory<OkHttpClient> okHttpClientFactory;
  private final Factory<AccessToken> credentialProvider;
  private final ScheduledExecutorService scheduledExecutorService;

  /** Simple all parameter constructor. */
  @VisibleForTesting
  TrinoAutoscalerApp(
      ClusterInformation clusterInformation,
      ClusterScalingSpec config,
      GoogleCloudServicesFactory googleCloudServicesFactory,
      Factory<OkHttpClient> okHttpClientFactory,
      Factory<AccessToken> credentialProvider,
      ScheduledExecutorService scheduledExecutorService) {
    this.clusterInformation = clusterInformation;
    this.autoscaleSpec = config;
    this.googleCloudServicesFactory = googleCloudServicesFactory;
    this.okHttpClientFactory = okHttpClientFactory;
    this.credentialProvider = credentialProvider;
    this.scheduledExecutorService = scheduledExecutorService;
  }

  /** The main tread loop that instantiates the application. */
  public static void main(String[] args) throws IOException, InterruptedException {

    if (args.length != 1) {
      logger.atSevere().log("Requires one argument <file-path-to-config-textpb>");
    }

    logger.atInfo().log("using configuration from: %s", args[0]);

    var clusterInformation = new DataprocClusterInformationService(OkHttpClient::new).retrieve();

    new TrinoAutoscalerApp(
            clusterInformation,
            readFileAsPb(ClusterScalingSpec.class, args[0]),
            ProductionGoogleCloudServicesFactory.create(clusterInformation),
            OkHttpClient::new,
            new ApplicationDefaultCredentialProvider(),
            Executors.newScheduledThreadPool(10))
        .run();
  }

  @VisibleForTesting
  void run() throws IOException, InterruptedException {
    logger.atInfo().log("Configuration:%n%s", TextFormat.printer().printToString(autoscaleSpec));

    logger.atInfo().log("ClusterDetails:%n%s", clusterInformation);

    var pollingDuration =
        Duration.parse(autoscaleSpec.getTimingConfiguration().getPollingDuration());
    logger.atInfo().log("Using Polling duration: %s", pollingDuration.toString());

    scheduledExecutorService.scheduleAtFixedRate(
        createClusterManager(),
        // Initial delay of 5 minutes before starting to check metrics
        /* initialDelay= */ 5,
        /* period= */ pollingDuration.toMinutes(),
        TimeUnit.MINUTES);

    scheduledExecutorService.awaitTermination(Long.MAX_VALUE, TimeUnit.DAYS);
    logger.atInfo().log("ENDING AUTOSCALER");
  }

  private ClusterManager createClusterManager() throws IOException {
    return new ClusterManager(autoscaleSpec, createInspectionService(), createResizeService());
  }

  private DataprocClusterResizeService createResizeService() throws IOException {

    var dataprocInstanceShutdownService =
        new DataprocInstanceShutdownService(
            clusterInformation,
            googleCloudServicesFactory::gceInstancesClient,
            credentialProvider,
            okHttpClientFactory);

    // Start a scheduled task for instance removal.
    scheduledExecutorService.scheduleAtFixedRate(
        dataprocInstanceShutdownService, 2, 2, TimeUnit.MINUTES);

    var trinoWorkerShutdownServiceFactory =
        new TrinoWorkerShutdownServiceFactory(
            okHttpClientFactory,
            () -> dataprocInstanceShutdownService,
            Duration.parse(
                autoscaleSpec.getTimingConfiguration().getTrinoGracefulShutdownDuration()));

    return new DataprocClusterResizeService(
        autoscaleSpec,
        googleCloudServicesFactory.dataprocClusterControllerClient(),
        trinoWorkerShutdownServiceFactory,
        scheduledExecutorService,
        List.of(StepWorkerScaleLogic.factory()));
  }

  private DataprocClusterInspectionService createInspectionService() throws IOException {
    return new DataprocClusterInspectionService(
        clusterInformation,
        googleCloudServicesFactory::monitoringQueryServiceClient,
        googleCloudServicesFactory::gceInstancesClient,
        Utils.readResourceAsString("cluster-avg-cpu.mql"));
  }
}
