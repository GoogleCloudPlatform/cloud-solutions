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

package com.google.cloud.solutions.satools.perfbenchmark.gcp;

import autovalue.shaded.org.checkerframework.checker.nullness.qual.Nullable;
import com.google.api.gax.longrunning.OperationFuture;
import com.google.cloud.devtools.cloudbuild.v1.CloudBuildClient;
import com.google.cloud.solutions.satools.common.auth.AccessTokenCredentialService;
import com.google.cloud.solutions.satools.common.auth.ComputeMetadataService;
import com.google.cloud.solutions.satools.common.auth.ImpersonatedCredentialService;
import com.google.cloud.solutions.satools.common.utils.ZipGenerator;
import com.google.cloud.solutions.satools.perfbenchmark.CloudBuildJobService;
import com.google.cloud.solutions.satools.perfbenchmark.PerfkitRunnerConfig;
import com.google.cloud.storage.BlobId;
import com.google.cloud.storage.BlobInfo;
import com.google.cloudbuild.v1.Build;
import com.google.cloudbuild.v1.BuildOptions;
import com.google.cloudbuild.v1.BuildStep;
import com.google.cloudbuild.v1.CancelBuildRequest;
import com.google.cloudbuild.v1.CreateBuildRequest;
import com.google.cloudbuild.v1.GetBuildRequest;
import com.google.cloudbuild.v1.Source;
import com.google.cloudbuild.v1.StorageSource;
import com.google.common.flogger.GoogleLogger;
import com.google.protobuf.Message;
import com.google.protobuf.util.Durations;
import com.google.solutions.satools.perfbenchmark.proto.Benchmark.JobInformation;
import java.nio.charset.StandardCharsets;
import java.util.function.Function;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

/** Implementation of JobService to manage running Cloud Build Jobs on Google Cloud. */
@Service
public class GoogleCloudBuildJobService implements CloudBuildJobService {

  private static final GoogleLogger logger = GoogleLogger.forEnclosingClass();

  private final AccessTokenCredentialService accessTokenCredentialService;
  private final ImpersonatedCredentialService impersonatedCredentialService;
  private final CloudBuildClientServiceFactory cloudBuildClientFactory;
  private final StorageClientServiceFactory storageClientFactory;

  private final ComputeMetadataService metadataService;

  private final PerfkitRunnerConfig runnerConfig;

  /** Simple parameterized constructor. */
  public GoogleCloudBuildJobService(
      @Autowired AccessTokenCredentialService accessTokenCredentialService,
      @Autowired ImpersonatedCredentialService impersonatedCredentialService,
      @Autowired CloudBuildClientServiceFactory cloudBuildClientFactory,
      @Autowired StorageClientServiceFactory storageClientFactory,
      @Autowired ComputeMetadataService metadataService,
      @Autowired PerfkitRunnerConfig runnerConfig) {
    this.accessTokenCredentialService = accessTokenCredentialService;
    this.impersonatedCredentialService = impersonatedCredentialService;
    this.cloudBuildClientFactory = cloudBuildClientFactory;
    this.storageClientFactory = storageClientFactory;
    this.metadataService = metadataService;
    this.runnerConfig = runnerConfig;
  }

  @Override
  @Nullable
  public Build create(JobInformation benchmarkJobInfo, String runUri) {
    try (var storageClient =
        storageClientFactory.create(impersonatedCredentialService.getImpersonatedCredentials())) {

      var zipFileName =
          String.format("config_%s_%s.zip", benchmarkJobInfo.getType().name(), runUri);
      var zipEntryName = String.format("config/%s.yml", benchmarkJobInfo.getType().name());

      // Stage the YAML file as a ZIP in GCS bucket as CloudBuild accepts only ZIP/TAR
      storageClient.create(
          BlobInfo.newBuilder(BlobId.of(runnerConfig.jobConfigGcsBucket(), zipFileName))
              .setContentType("application/zip")
              .build(),
          ZipGenerator.of(
                  zipEntryName,
                  benchmarkJobInfo.getBenchmarkYaml().getBytes(StandardCharsets.UTF_8))
              .makeZipFile());

      var buildConfig =
          Build.newBuilder()
              .setTimeout(Durations.fromMinutes(runnerConfig.buildTimeout().toMinutes()))
              .setOptions(
                  BuildOptions.newBuilder().setMachineType(BuildOptions.MachineType.E2_HIGHCPU_8))
              .setServiceAccount(
                  String.format(
                      "projects/-/serviceAccounts/%s", metadataService.getServiceAccountEmail()))
              .setLogsBucket(
                  String.format("%s/logs-%s.txt", runnerConfig.jobConfigGcsBucket(), runUri))
              .setSource(
                  Source.newBuilder()
                      .setStorageSource(
                          StorageSource.newBuilder()
                              .setBucket(runnerConfig.jobConfigGcsBucket())
                              .setObject(zipFileName)))
              .addSteps(
                  BuildStep.newBuilder()
                      .setName(runnerConfig.baseImage())
                      .setEntrypoint("${_PERFKIT_FOLDER}/pkb.py")
                      .addArgs("--benchmarks=" + benchmarkJobInfo.getType().name().toLowerCase())
                      .addArgs("--benchmark_config_file=" + zipEntryName)
                      .addArgs("--owner=${BUILD_ID}")
                      .addArgs("--bq_project=${_RESULT_BQ_PROJECT}")
                      .addArgs(
                          "--bigquery_table=${_RESULT_BQ_PROJECT}:"
                              + "${_RESULT_BQ_DATASET}.${_RESULT_BQ_TABLE}"))
              .putSubstitutions("_PERFKIT_FOLDER", runnerConfig.perfkitFolder())
              .putSubstitutions("_RESULT_BQ_PROJECT", runnerConfig.resultsBqProject())
              .putSubstitutions("_RESULT_BQ_DATASET", runnerConfig.resultsBqDataset())
              .putSubstitutions("_RESULT_BQ_TABLE", runnerConfig.resultsBqTable())
              .build();

      return execute(
              cloudBuildClient -> cloudBuildClient::createBuildAsync,
              OperationFuture::getMetadata,
              CreateBuildRequest.newBuilder()
                  .setProjectId(runnerConfig.projectId())
                  .setBuild(buildConfig)
                  .build())
          .get()
          .getBuild();
    } catch (Exception exception) {
      logger.atWarning().withCause(exception).log("error creating Benchmark job on cloud build.");
    }

    return null;
  }

  @Override
  @Nullable
  public Build get(String jobId) {
    return execute(
        buildClient -> buildClient::getBuild,
        Function.identity(),
        GetBuildRequest.newBuilder().setProjectId(runnerConfig.projectId()).setId(jobId).build());
  }

  @Override
  @Nullable
  public Build cancel(String jobId) {
    return execute(
        buildClient -> buildClient::cancelBuild,
        Function.identity(),
        CancelBuildRequest.newBuilder()
            .setProjectId(runnerConfig.projectId())
            .setId(jobId)
            .build());
  }

  /**
   * Utility method to execute CloudBuild gRPC methods with Exception logging and handling.
   *
   * @param buildFunction factory method to extract the cloud Build gRPC method to call from the
   *     client
   * @param input the generic input Request object to send to Cloud Build
   * @param <InputT> the input object's protobuf type
   * @param <OutputT> the output objects' protobuf type
   * @return the response object from Cloud Build
   */
  private <InputT extends Message, I, OutputT> OutputT execute(
      Function<CloudBuildClient, Function<InputT, I>> buildFunction,
      Function<I, OutputT> resultFunction,
      InputT input) {
    try (var buildClient =
        cloudBuildClientFactory.create(accessTokenCredentialService.getCredentials())) {
      return resultFunction.apply(buildFunction.apply(buildClient).apply(input));
    } catch (Exception ioException) {
      logger.atWarning().withCause(ioException).log("error with cloudbuild - Input:%n%s", input);
    }
    return null;
  }
}
