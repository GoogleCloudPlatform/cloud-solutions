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

import static com.google.common.truth.Truth.assertThat;
import static com.googlecode.objectify.ObjectifyService.factory;
import static com.googlecode.objectify.ObjectifyService.ofy;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.google.cloud.solutions.satools.common.auth.testing.FakeAccessTokenCredentialService;
import com.google.cloud.solutions.satools.common.objectifyextensions.testing.LocalDatastoreExtension;
import com.google.cloud.solutions.satools.common.objectifyextensions.testing.ObjectifyExtension;
import com.google.cloud.solutions.satools.common.testing.ProvidedMethodBinaryPredicate;
import com.google.cloud.solutions.satools.common.utils.ProtoUtils;
import com.google.cloud.solutions.satools.perfbenchmark.entity.BenchmarkJobEntity;
import com.google.cloud.solutions.satools.perfbenchmark.entity.BenchmarkJobStatus;
import com.google.cloudbuild.v1.Build;
import com.google.common.hash.Hashing;
import com.google.common.truth.Correspondence;
import com.google.common.truth.extensions.proto.ProtoTruth;
import com.google.solutions.satools.perfbenchmark.proto.Benchmark;
import com.google.solutions.satools.perfbenchmark.proto.Benchmark.BenchmarkJob;
import com.google.solutions.satools.perfbenchmark.proto.Benchmark.BenchmarkType;
import com.google.solutions.satools.perfbenchmark.proto.Benchmark.CloudProviderType;
import com.google.solutions.satools.perfbenchmark.proto.Benchmark.JobInformation;
import com.google.solutions.satools.perfbenchmark.proto.Benchmark.ListBenchmarkJobs;
import com.googlecode.objectify.Key;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.stream.IntStream;
import java.util.stream.LongStream;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

@ExtendWith({
  LocalDatastoreExtension.class,
  ObjectifyExtension.class,
})
final class BenchmarkJobDbServiceTest {

  private static final SecureRandom secureRandom = new SecureRandom();

  private Clock testClock;

  private BenchmarkJobDbService jobDbService;
  private BenchmarkJobDbService emptyEmailJobService;

  private BenchmarkJobDbService jobDbService2;

  private final String testUserEmail = "someone@example.com";

  @BeforeEach
  public void registerObjectifyClasses() {
    factory().register(BenchmarkJobEntity.class);
    factory().register(BenchmarkJobStatus.class);
  }

  @BeforeEach
  public void setupBeans() {
    testClock = Clock.fixed(Instant.now(), ZoneOffset.UTC);
    jobDbService =
        new BenchmarkJobDbService(new FakeAccessTokenCredentialService(testUserEmail), testClock);
    emptyEmailJobService =
        new BenchmarkJobDbService(new FakeAccessTokenCredentialService(""), testClock);
    jobDbService2 =
        new BenchmarkJobDbService(
            new FakeAccessTokenCredentialService("sometwo@example.com"), testClock);
  }

  @Test
  void createAndRetrieve_noBuildInfo_throwsException() {
    var testJobInformation = randomJobInformation();
    assertThrows(
        NullPointerException.class, () -> jobDbService.create(2L, testJobInformation, null));
  }

  @Test
  void createAndRetrieve_withBuildInfo_valid() {
    var testJobInformation = randomJobInformation();

    var job =
        jobDbService.create(
            3L,
            testJobInformation,
            Build.newBuilder().setId("some-build-id").setLogUrl("some-log-url").build());
    var savedEntity = ofy().load().type(BenchmarkJobEntity.class).id(job.getId()).now();

    var retrievedJob = jobDbService.retrieve(job.getId());

    ProtoTruth.assertThat(retrievedJob).isEqualTo(job);

    assertThat(savedEntity)
        .isEqualTo(
            new BenchmarkJobEntity(
                job.getId(),
                Hashing.sha256().hashString(testUserEmail, StandardCharsets.UTF_8).toString(),
                ProtoUtils.toJson(testJobInformation),
                testClock.instant(),
                "some-build-id",
                "some-log-url",
                null));

    assertThat(ofy().load().type(BenchmarkJobStatus.class).list())
        .containsExactly(
            new BenchmarkJobStatus(
                Key.create(BenchmarkJobEntity.class, job.getId()),
                Benchmark.BenchmarkJobStatus.CREATED.name(),
                testClock.instant()));
  }

  @Test
  void retrieveAll_valid() {

    var testSamplesSize = secureRandom.nextInt(5, 10);

    var testJobs =
        LongStream.rangeClosed(1, testSamplesSize)
            .boxed()
            .map(
                runId ->
                    jobDbService.create(
                        runId,
                        randomJobInformation(),
                        Build.newBuilder()
                            .setId("some-build-id-" + runId)
                            .setLogUrl("some-log-url-" + runId)
                            .build()))
            .toList();

    var expectedIds =
        IntStream.rangeClosed(1, testSamplesSize).boxed().map(id -> "some-build-id-" + id).toList();
    var expectedLogUrls =
        IntStream.rangeClosed(1, testSamplesSize).boxed().map(id -> "some-log-url-" + id).toList();

    var retrievedAllJobs = jobDbService.retrieveAllUserJobs();

    ProtoTruth.assertThat(retrievedAllJobs)
        .ignoringRepeatedFieldOrder()
        .isEqualTo(ListBenchmarkJobs.newBuilder().addAllJobs(testJobs).build());

    var entitiesInDatastore =
        ofy()
            .load()
            .type(BenchmarkJobEntity.class)
            .ids(testJobs.stream().map(BenchmarkJob::getId).toList());

    assertThat(entitiesInDatastore.values())
        .comparingElementsUsing(
            Correspondence.from(
                new ProvidedMethodBinaryPredicate<>(BenchmarkJobEntity::getCloudBuildJobId),
                "comparingBuildJobIds"))
        .containsExactlyElementsIn(expectedIds);

    assertThat(entitiesInDatastore.values())
        .comparingElementsUsing(
            Correspondence.from(
                new ProvidedMethodBinaryPredicate<>(BenchmarkJobEntity::getId), "comparingIds"))
        .containsExactlyElementsIn(LongStream.rangeClosed(1, testSamplesSize).boxed().toList());

    assertThat(entitiesInDatastore.values())
        .comparingElementsUsing(
            Correspondence.from(
                new ProvidedMethodBinaryPredicate<>(BenchmarkJobEntity::getCloudBuildLogUri),
                "comparing LogUrls"))
        .containsExactlyElementsIn(expectedLogUrls);
  }

  @Test
  void cancel_valid() {
    var job =
        jobDbService.create(
            5L,
            randomJobInformation(),
            Build.newBuilder()
                .setId("some-cancellable-build-id")
                .setLogUrl("some-cancellable-build-log-url")
                .build());
    jobDbService.cancel(job.getId());

    var jobKey = Key.create(BenchmarkJobEntity.class, job.getId());

    assertThat(ofy().load().type(BenchmarkJobStatus.class).ancestor(jobKey).list())
        .containsExactly(
            new BenchmarkJobStatus(
                jobKey, Benchmark.BenchmarkJobStatus.CREATED.name(), testClock.instant()),
            new BenchmarkJobStatus(
                jobKey, Benchmark.BenchmarkJobStatus.CANCELLING.name(), testClock.instant()));
  }

  @Test
  void create_emptyEmail_throwsException() {
    var exception =
        assertThrows(
            ResponseStatusException.class,
            () ->
                emptyEmailJobService.create(
                    -1L, randomJobInformation(), Build.getDefaultInstance()));
    assertThat(exception.getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
  }

  @Test
  void retrieve_emptyEmail_throwsException() {
    var exception =
        assertThrows(
            ResponseStatusException.class, () -> emptyEmailJobService.retrieveAllUserJobs());
    assertThat(exception.getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
  }

  @Test
  void retrieve_othersJobId_throwsException() {
    var createdJob =
        jobDbService.create(
            6L,
            randomJobInformation(),
            Build.newBuilder()
                .setId("some-org-build-id")
                .setLogUrl("some-org-build-log-url")
                .build());

    var exception =
        assertThrows(
            ResponseStatusException.class, () -> jobDbService2.retrieve(createdJob.getId()));
    assertThat(exception.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
  }

  @Test
  void cancel_othersJobId_throwsException() {
    var createdJob =
        jobDbService.create(
            7L,
            randomJobInformation(),
            Build.newBuilder()
                .setId("some-other-build-id")
                .setLogUrl("some-others-log-url")
                .build());

    var exception =
        assertThrows(ResponseStatusException.class, () -> jobDbService2.cancel(createdJob.getId()));
    assertThat(exception.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
  }

  private static JobInformation randomJobInformation() {

    var type = BenchmarkType.values()[secureRandom.nextInt(BenchmarkType.values().length - 1)];
    var cloudProvider =
        CloudProviderType.values()[secureRandom.nextInt(CloudProviderType.values().length - 1)];

    return JobInformation.newBuilder()
        .setBenchmarkYaml("Some Test Yaml")
        .setCloudProjectId("test-project")
        .setCloudProvider(cloudProvider)
        .setType(type)
        .build();
  }
}
