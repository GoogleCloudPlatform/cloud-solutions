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

package com.google.cloud.solutions.satools.perfbenchmark;

import com.google.cloud.solutions.satools.common.auth.AccessTokenCredentialService;
import com.google.cloud.solutions.satools.common.utils.ProtoUtils;
import com.google.cloud.solutions.satools.perfbenchmark.entity.BenchmarkJobEntity;
import com.google.cloud.solutions.satools.perfbenchmark.entity.BenchmarkJobResult;
import com.google.cloud.solutions.satools.perfbenchmark.entity.BenchmarkJobStatus;
import com.google.cloudbuild.v1.Build;
import com.google.protobuf.util.Timestamps;
import com.google.solutions.satools.perfbenchmark.proto.Benchmark;
import com.google.solutions.satools.perfbenchmark.proto.Benchmark.BenchmarkJob;
import com.google.solutions.satools.perfbenchmark.proto.Benchmark.BenchmarkJobRunInformation;
import com.google.solutions.satools.perfbenchmark.proto.Benchmark.JobInformation;
import com.google.solutions.satools.perfbenchmark.proto.Benchmark.ListBenchmarkJobs;
import com.google.solutions.satools.perfbenchmark.proto.Benchmark.Principal;
import java.time.Clock;
import java.time.Instant;
import java.util.Collection;
import java.util.List;
import java.util.function.Function;
import org.checkerframework.checker.nullness.qual.NonNull;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

/**
 * CRUD methods implementation for retrieving PKB Benchmark results from database.
 *
 * <p>The service uses the {@link AccessTokenCredentialService} to identify the logged-in user and
 * provides results limited to the user only.
 */
@Service
public class BenchmarkJobDbService {

  private final AccessTokenCredentialService accessTokenCredentialService;

  private final Clock clock;

  BenchmarkJobDbService(
      @Autowired AccessTokenCredentialService accessTokenCredentialService,
      @Autowired Clock clock) {
    this.accessTokenCredentialService = accessTokenCredentialService;
    this.clock = clock;
  }

  /**
   * Adds a new PKB Benchmark job information to the DB.
   *
   * @param id the reserved jobId for the PKB Job
   * @param jobInformation the details of the job including type of benchmark and other parameters
   * @param buildInfo the Cloud Build Job that is executing this PKB Benchmark job.
   * @return The BenchmarkJob stored in the database
   */
  public BenchmarkJob create(
      @NonNull Long id, @NonNull JobInformation jobInformation, @NonNull Build buildInfo) {

    var principal = accessTokenCredentialService.retrieveEmailAddress();

    if ("".equals(principal.email())) {
      throw new ResponseStatusException(HttpStatus.UNAUTHORIZED);
    }

    var timestamp = Instant.now(clock);

    var benchmarkJobEntity =
        BenchmarkJobEntity.getDefaultInstance()
            .withId(id)
            .withCreatorEmail(principal.sha256())
            .withJobInformationJson(ProtoUtils.toJson(jobInformation))
            .withCreated(timestamp)
            .withCloudBuildJobId(buildInfo.getId())
            .withCloudBuildLogUri(buildInfo.getLogUrl());

    var createdStatus =
        new BenchmarkJobStatus(benchmarkJobEntity, Benchmark.BenchmarkJobStatus.CREATED, timestamp);

    DatastoreService.ofy()
        .transact(
            () -> DatastoreService.ofy().save().entities(benchmarkJobEntity, createdStatus).now());
    return buildJobWithUserAndStatus(benchmarkJobEntity, List.of(createdStatus));
  }

  /** Retrieves detailed statuses of the BenchmarkJob using the jobId. */
  public BenchmarkJob retrieve(long id) {

    var benchmarkJob = getJobEntity(id);
    var statuses =
        DatastoreService.ofy()
            .load()
            .type(BenchmarkJobStatus.class)
            .ancestor(benchmarkJob)
            .chunkAll()
            .list();

    return buildJobWithUserAndStatus(benchmarkJob, statuses);
  }

  /** Updates the status of the Job as {@code CANCELLED}. */
  public BenchmarkJob cancel(long id) {
    var benchmarkJob = getJobEntity(id);

    var timestamp = Instant.now(clock);

    var cancellingStatus =
        new BenchmarkJobStatus(benchmarkJob, Benchmark.BenchmarkJobStatus.CANCELLING, timestamp);
    DatastoreService.ofy().save().entity(cancellingStatus).now();

    return retrieve(id);
  }

  /** Retrieves the entire BenchmarkJob with history of statuses. */
  public BenchmarkJobEntity getJobEntity(long id) {
    var benchmarkJob = DatastoreService.ofy().load().type(BenchmarkJobEntity.class).id(id).now();

    var principal = accessTokenCredentialService.retrieveEmailAddress();

    if (!benchmarkJob.getCreatorEmail().equals(principal.sha256())) {
      throw new ResponseStatusException(HttpStatus.FORBIDDEN);
    }

    return benchmarkJob;
  }

  /** Returns the list of all jobs for the logged-in user. */
  public ListBenchmarkJobs retrieveAllUserJobs() {

    var principal = accessTokenCredentialService.retrieveEmailAddress();

    if (principal.email().equals("")) {
      throw new ResponseStatusException(HttpStatus.UNAUTHORIZED);
    }

    var jobsList =
        DatastoreService.ofy()
            .load()
            .type(BenchmarkJobEntity.class)
            .filter("creatorEmail", principal.sha256())
            .stream()
            .map(
                job -> {
                  var statuses =
                      DatastoreService.ofy()
                          .load()
                          .type(BenchmarkJobStatus.class)
                          .ancestor(job)
                          .chunkAll()
                          .list();
                  return buildJobWithUserAndStatus(job, statuses);
                })
            .toList();

    return ListBenchmarkJobs.newBuilder().addAllJobs(jobsList).build();
  }

  private BenchmarkJob buildJobWithUserAndStatus(
      BenchmarkJobEntity benchmarkJob, List<BenchmarkJobStatus> statuses) {

    var principal = accessTokenCredentialService.retrieveEmailAddress();

    var benchmarJobBuilder = BenchmarkJob.newBuilder();

    if (benchmarkJob.getCloudBuildLogUri() != null) {
      benchmarJobBuilder = benchmarJobBuilder.setLogUri(benchmarkJob.getCloudBuildLogUri());
    }

    return benchmarJobBuilder
        .setJobInformation(
            ProtoUtils.parseProtoJson(
                benchmarkJob.getBenchmarkJobInformationJson(), Benchmark.JobInformation.class))
        // Fill ReadOnly fields
        .setPrincipal(Principal.newBuilder().setCreatorEmail(principal.email()))
        .setId(benchmarkJob.getId())
        .clearRunInformation()
        .addAllRunInformation(ConvertStatusFn.create().apply(statuses))
        .setResult(ConvertMetricResultsFn.create().apply(benchmarkJob.getResult()))
        .build();
  }

  private static class ConvertStatusFn
      implements Function<Collection<BenchmarkJobStatus>, List<BenchmarkJobRunInformation>> {
    private static ConvertStatusFn create() {
      return new ConvertStatusFn();
    }

    @Override
    public List<BenchmarkJobRunInformation> apply(Collection<BenchmarkJobStatus> statuses) {

      if (statuses == null) {
        return List.of();
      }

      return statuses.stream()
          .map(
              status ->
                  BenchmarkJobRunInformation.newBuilder()
                      .setTimestamp(Timestamps.fromMillis(status.getTimestamp().toEpochMilli()))
                      .setStatus(Benchmark.BenchmarkJobStatus.valueOf(status.getStatus()))
                      .build())
          .toList();
    }
  }

  private static class ConvertMetricResultsFn
      implements Function<BenchmarkJobResult, Benchmark.BenchmarkResult> {

    private static ConvertMetricResultsFn create() {
      return new ConvertMetricResultsFn();
    }

    @Override
    public Benchmark.BenchmarkResult apply(BenchmarkJobResult benchmarkJobResult) {

      if (benchmarkJobResult == null) {
        return Benchmark.BenchmarkResult.getDefaultInstance();
      }

      var metrics =
          benchmarkJobResult.getMetrics().stream()
              .map(
                  result ->
                      Benchmark.BenchmarkMetricResult.newBuilder()
                          .setTimestamp(Timestamps.fromMillis(result.getTimestamp().toEpochMilli()))
                          .setMetric(result.getMetric())
                          .setValue(result.getValue())
                          .addAllLabels(result.getLabels())
                          .build())
              .toList();

      return Benchmark.BenchmarkResult.newBuilder().addAllMetrics(metrics).build();
    }
  }
}
