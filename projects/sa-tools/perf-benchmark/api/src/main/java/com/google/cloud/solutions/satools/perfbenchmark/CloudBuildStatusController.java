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

import com.google.cloud.ByteArray;
import com.google.cloud.solutions.satools.common.utils.ProtoUtils;
import com.google.cloud.solutions.satools.perfbenchmark.entity.BenchmarkJobEntity;
import com.google.cloud.solutions.satools.perfbenchmark.entity.BenchmarkJobStatus;
import com.google.cloud.solutions.satools.perfbenchmark.gcp.PubsubPushEvent;
import com.google.cloudbuild.v1.Build;
import com.google.common.flogger.GoogleLogger;
import com.google.protobuf.util.Timestamps;
import com.google.solutions.satools.perfbenchmark.proto.Benchmark;
import java.time.Instant;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** Controller to handle Cloud Build status updates based on events coming through PubSub. */
@RestController
@RequestMapping("/buildstatus")
public class CloudBuildStatusController {

  private static final GoogleLogger logger = GoogleLogger.forEnclosingClass();

  @Autowired private CustomBenchmarkResultService resultService;

  @PostMapping
  void receiveBuildEvent(@RequestBody PubsubPushEvent requestBody) {

    if (requestBody.getMessage() == null) {
      logger.atInfo().log("empty push message");
      return;
    }

    var buildInfo =
        ProtoUtils.parseProtoJson(
            ByteArray.fromBase64(requestBody.getMessage().getData()).toStringUtf8(), Build.class);

    var statusExtractor = new JobStatusCreator(buildInfo);

    DatastoreService.ofy()
        .load()
        .type(BenchmarkJobEntity.class)
        .filter("cloudBuildJobId", buildInfo.getId())
        .stream()
        .findFirst()
        .ifPresent(
            jobEntity -> {
              var updatedStatus = statusExtractor.getUpdatedStatus(jobEntity);

              DatastoreService.ofy()
                  .transactNew(
                      () -> {
                        if (buildInfo.getStatus().equals(Build.Status.SUCCESS)) {
                          var result = resultService.retrieveResult(jobEntity);
                          DatastoreService.ofy().save().entity(jobEntity.withResult(result));
                        }

                        DatastoreService.ofy().save().entity(updatedStatus);
                      });
            });
  }

  /** Helper class to create BenchmarkJobStatus from Cloud Build status for the given JobId. */
  private record JobStatusCreator(Build buildInfo) {
    private BenchmarkJobStatus getUpdatedStatus(BenchmarkJobEntity jobEntity) {
      return switch (buildInfo.getStatus()) {
        case QUEUED -> new BenchmarkJobStatus(
            jobEntity,
            Benchmark.BenchmarkJobStatus.QUEUED,
            Instant.ofEpochMilli(Timestamps.toMillis(buildInfo.getStartTime())));
        case WORKING -> new BenchmarkJobStatus(
            jobEntity,
            Benchmark.BenchmarkJobStatus.RUNNING,
            Instant.ofEpochMilli(Timestamps.toMillis(buildInfo.getStartTime())));
        case SUCCESS -> new BenchmarkJobStatus(
            jobEntity,
            Benchmark.BenchmarkJobStatus.FINISHED,
            Instant.ofEpochMilli(Timestamps.toMillis(buildInfo.getFinishTime())));
        case FAILURE -> new BenchmarkJobStatus(
            jobEntity,
            Benchmark.BenchmarkJobStatus.FAILED,
            Instant.ofEpochMilli(Timestamps.toMillis(buildInfo.getFinishTime())));
        case INTERNAL_ERROR -> new BenchmarkJobStatus(
            jobEntity,
            Benchmark.BenchmarkJobStatus.INTERNAL_ERROR,
            Instant.ofEpochMilli(Timestamps.toMillis(buildInfo.getFinishTime())));
        case TIMEOUT -> new BenchmarkJobStatus(
            jobEntity,
            Benchmark.BenchmarkJobStatus.TIMEOUT,
            Instant.ofEpochMilli(Timestamps.toMillis(buildInfo.getFinishTime())));
        case CANCELLED -> new BenchmarkJobStatus(
            jobEntity,
            Benchmark.BenchmarkJobStatus.CANCELLED,
            Instant.ofEpochMilli(Timestamps.toMillis(buildInfo.getFinishTime())));
        case EXPIRED -> new BenchmarkJobStatus(
            jobEntity,
            Benchmark.BenchmarkJobStatus.EXPIRED,
            Instant.ofEpochMilli(Timestamps.toMillis(buildInfo.getFinishTime())));

        default -> null;
      };
    }
  }
}
