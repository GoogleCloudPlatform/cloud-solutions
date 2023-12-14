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
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;

import com.google.cloud.ByteArray;
import com.google.cloud.bigquery.Field;
import com.google.cloud.bigquery.FieldList;
import com.google.cloud.bigquery.FieldValue;
import com.google.cloud.bigquery.FieldValueList;
import com.google.cloud.bigquery.LegacySQLTypeName;
import com.google.cloud.solutions.satools.common.objectifyextensions.testing.LocalDatastoreExtension;
import com.google.cloud.solutions.satools.common.objectifyextensions.testing.ObjectifyExtension;
import com.google.cloud.solutions.satools.common.testing.TestResourceLoader;
import com.google.cloud.solutions.satools.common.testing.stubs.PatchyStub;
import com.google.cloud.solutions.satools.common.testing.stubs.bigquery.QueryResultCallableFactory;
import com.google.cloud.solutions.satools.common.testing.stubs.bigquery.TableResultsConverter;
import com.google.cloud.solutions.satools.common.utils.ProtoUtils;
import com.google.cloud.solutions.satools.perfbenchmark.entity.BenchmarkJobEntity;
import com.google.cloud.solutions.satools.perfbenchmark.entity.BenchmarkJobStatus;
import com.google.cloud.solutions.satools.perfbenchmark.gcp.PubsubPushEvent;
import com.google.cloudbuild.v1.Build;
import com.google.gson.Gson;
import com.google.protobuf.util.Timestamps;
import com.google.solutions.satools.perfbenchmark.proto.Benchmark;
import com.google.solutions.satools.perfbenchmark.proto.Benchmark.BenchmarkJob;
import java.io.IOException;
import java.io.StringReader;
import java.time.Clock;
import java.util.List;
import java.util.function.Function;
import java.util.stream.Stream;
import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVRecord;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.junit.jupiter.SpringExtension;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders;
import org.springframework.test.web.servlet.result.MockMvcResultMatchers;

/** Checks all the Cloud Build controllers methods. */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Import(TestBeansConfiguration.class)
@ExtendWith({LocalDatastoreExtension.class, ObjectifyExtension.class, SpringExtension.class})
public class CloudBuildStatusControllerTest {

  @Autowired private MockMvc mockMvc;

  @Autowired private Clock testClock;
  @Autowired private PatchyStub patchyStub;

  @Autowired private BenchmarkJobDbService jobDbService;

  @BeforeEach
  public void clearPatchyStub() {
    patchyStub.clearAllFactories();
  }

  @BeforeEach
  public void registerObjectifyClasses() {
    factory().register(BenchmarkJobEntity.class);
    factory().register(BenchmarkJobStatus.class);
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("testReceiveBuildEvent")
  void receiveBuildEvent_valid(
      String testCaseName,
      long jobId,
      String cloudBuildId,
      Build.Status buildStatus,
      Benchmark.BenchmarkJobStatus expectedStatus)
      throws Exception {

    assertThat(jobId).isGreaterThan(0);

    // Setup DB with a custom job and Cloud Build information.
    jobDbService.create(
        /* id= */ jobId,
        /* jobInformation= */ TestResourceLoader.classPath()
            .forProto(Benchmark.JobInformation.class)
            .loadJson("benchmarkjobs/create_job_request.json"),
        /* buildInfo= */ Build.newBuilder()
            .setId(cloudBuildId)
            .setLogUrl("test-build-log-url")
            .build());

    // Generate the BuildQueued PubSub Event
    var buildWithStatus =
        Build.newBuilder()
            .setId(cloudBuildId)
            .setStatus(buildStatus)
            .setStartTime(Timestamps.fromMillis(testClock.millis()))
            .setFinishTime(Timestamps.fromMillis(testClock.millis()))
            .build();

    var testBuildEventMessage =
        TestResourceLoader.classPath()
            .<PubsubPushEvent>loadAsJson(
                "benchmarkjobs/cloud_build_event.json", PubsubPushEvent.class);
    testBuildEventMessage
        .getMessage()
        // Set the message as BASE64 encoded JSON message
        .setData(ByteArray.copyFrom(ProtoUtils.toJson(buildWithStatus)).toBase64());

    var buildQueuedEventJson = new Gson().toJson(testBuildEventMessage);

    // Inject BigQuery Stub if BuildStatus=success
    if (buildStatus.equals(Build.Status.SUCCESS)) {
      setupBigQueryStubAndResults();
    }

    // Simulate PubSub Event push by making POST Call
    mockMvc
        .perform(post("/buildstatus").contentType("application/json").content(buildQueuedEventJson))
        .andExpect(MockMvcResultMatchers.status().isOk())
        .andDo(
            result1 ->
                // Verify that the DB has been updated and GET calls respond with correct status
                mockMvc
                    .perform(MockMvcRequestBuilders.get(String.format("/benchmarkjobs/%s", jobId)))
                    .andExpect(MockMvcResultMatchers.status().isOk())
                    .andExpect(
                        MockMvcResultMatchers.content()
                            .contentType("application/x-protobuf;charset=UTF-8"))
                    .andExpect(
                        result -> {
                          var benchmarkJob =
                              BenchmarkJob.parseFrom(result.getResponse().getContentAsByteArray());

                          assertThat(benchmarkJob.getRunInformationList())
                              .containsAtLeastElementsIn(
                                  List.of(
                                      Benchmark.BenchmarkJobRunInformation.newBuilder()
                                          .setStatus(expectedStatus)
                                          .setTimestamp(Timestamps.fromMillis(testClock.millis()))
                                          .build()));

                          // Check Result if SUCCESS
                          if (buildStatus.equals(Build.Status.SUCCESS)) {

                            assertThat(benchmarkJob.hasResult()).isTrue();
                            assertThat(benchmarkJob)
                                .isEqualTo(
                                    TestResourceLoader.classPath()
                                        .forProto(BenchmarkJob.class)
                                        .loadText("expected_benchmarkjob_success.textproto"));
                          }
                        }));
  }

  static Stream<Arguments> testReceiveBuildEvent() {
    return Stream.of(
        Arguments.of(
            /* testCaseName= */ "queued",
            /* jobId= */ 1L,
            /* cloudBuildId= */ "cloud-build-1",
            /* buildStatus= */ Build.Status.QUEUED,
            /* expectedStatus= */ Benchmark.BenchmarkJobStatus.QUEUED),
        Arguments.of(
            /* testCaseName= */ "working",
            /* jobId= */ 2L,
            /* cloudBuildId= */ "cloud-build-2",
            /* buildStatus= */ Build.Status.WORKING,
            /* expectedStatus= */ Benchmark.BenchmarkJobStatus.RUNNING),
        Arguments.of(
            /* testCaseName= */ "success",
            /* jobId= */ 2L,
            /* cloudBuildId= */ "cloud-build-success-id",
            /* buildStatus= */ Build.Status.SUCCESS,
            /* expectedStatus= */ Benchmark.BenchmarkJobStatus.FINISHED),
        Arguments.of(
            /* testCaseName= */ "failure",
            /* jobId= */ 3L,
            /* cloudBuildId= */ "cloud-build-3",
            /* buildStatus= */ Build.Status.FAILURE,
            /* expectedStatus= */ Benchmark.BenchmarkJobStatus.FAILED),
        Arguments.of(
            /* testCaseName= */ "internal_error",
            /* jobId= */ 4L,
            /* cloudBuildId= */ "cloud-build-4",
            /* buildStatus= */ Build.Status.INTERNAL_ERROR,
            /* expectedStatus= */ Benchmark.BenchmarkJobStatus.INTERNAL_ERROR),
        Arguments.of(
            /* testCaseName= */ "timeout",
            /* jobId= */ 1L,
            /* cloudBuildId= */ "cloud-build-1",
            /* buildStatus= */ Build.Status.TIMEOUT,
            /* expectedStatus= */ Benchmark.BenchmarkJobStatus.TIMEOUT),
        Arguments.of(
            /* testCaseName= */ "cancelled",
            /* jobId= */ 2L,
            /* cloudBuildId= */ "cloud-build-2",
            /* buildStatus= */ Build.Status.CANCELLED,
            /* expectedStatus= */ Benchmark.BenchmarkJobStatus.CANCELLED),
        Arguments.of(
            /* testCaseName= */ "expired",
            /* jobId= */ 2L,
            /* cloudBuildId= */ "cloud-build-2",
            /* buildStatus= */ Build.Status.EXPIRED,
            /* expectedStatus= */ Benchmark.BenchmarkJobStatus.EXPIRED));
  }

  void setupBigQueryStubAndResults() throws IOException {

    var values =
        CSVFormat.DEFAULT
            .withFirstRecordAsHeader()
            .parse(
                new StringReader(
                    TestResourceLoader.classPath().loadAsString("sample_metrics_results.csv")))
            .stream()
            .toList();

    patchyStub.addUnaryCallableFactory(
        new QueryResultCallableFactory(
            actual ->
                assertThat(actual.getQuery())
                    .isEqualTo(
                        TestResourceLoader.classPath().loadAsString("expected_results_query.sql")),
            TableResultsConverter.using(new CsvToFieldValueListFn()).apply(values)));
  }

  static class CsvToFieldValueListFn implements Function<CSVRecord, FieldValueList> {
    @Override
    public FieldValueList apply(CSVRecord row) {
      return FieldValueList.of(
          row.stream().map(col -> FieldValue.of(FieldValue.Attribute.PRIMITIVE, col)).toList(),
          FieldList.of(
              row.getParser().getHeaderNames().stream()
                  .map(header -> Field.of(header, LegacySQLTypeName.STRING))
                  .toList()));
    }
  }
}
