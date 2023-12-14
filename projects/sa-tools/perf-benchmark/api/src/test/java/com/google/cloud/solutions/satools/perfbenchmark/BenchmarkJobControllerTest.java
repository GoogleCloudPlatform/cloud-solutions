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

import static com.google.cloud.solutions.satools.common.utils.ProtoUtils.parseProtoJson;
import static com.google.common.truth.Truth.assertThat;
import static com.googlecode.objectify.ObjectifyService.factory;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;

import com.google.cloud.solutions.satools.common.objectifyextensions.testing.LocalDatastoreExtension;
import com.google.cloud.solutions.satools.common.objectifyextensions.testing.ObjectifyExtension;
import com.google.cloud.solutions.satools.common.testing.AssertValidator;
import com.google.cloud.solutions.satools.common.testing.TestResourceLoader;
import com.google.cloud.solutions.satools.common.testing.ZipTruth;
import com.google.cloud.solutions.satools.common.testing.stubs.BaseOperationFuture.OperationData;
import com.google.cloud.solutions.satools.common.testing.stubs.PatchyStub;
import com.google.cloud.solutions.satools.common.testing.stubs.cloudbuild.ConstantGetBuildCallable;
import com.google.cloud.solutions.satools.common.testing.stubs.cloudbuild.VerifyingCreateBuildCallable;
import com.google.cloud.solutions.satools.common.testing.stubs.storage.CreateBlobRequest;
import com.google.cloud.solutions.satools.common.testing.stubs.storage.VerifyingCreateBlobStub;
import com.google.cloud.solutions.satools.common.utils.ProtoUtils;
import com.google.cloud.solutions.satools.common.utils.ZipGenerator.ZipFileContent;
import com.google.cloud.solutions.satools.perfbenchmark.entity.BenchmarkJobEntity;
import com.google.cloud.solutions.satools.perfbenchmark.entity.BenchmarkJobStatus;
import com.google.cloudbuild.v1.BuildOperationMetadata;
import com.google.cloudbuild.v1.CreateBuildRequest;
import com.google.cloudbuild.v1.Source;
import com.google.common.truth.extensions.proto.ProtoTruth;
import com.google.solutions.satools.perfbenchmark.proto.Benchmark.BenchmarkJob;
import com.google.solutions.satools.perfbenchmark.proto.Benchmark.JobInformation;
import java.io.IOException;
import org.checkerframework.checker.nullness.qual.Nullable;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.junit.jupiter.SpringExtension;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.result.MockMvcResultMatchers;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Import(TestBeansConfiguration.class)
@ExtendWith({LocalDatastoreExtension.class, ObjectifyExtension.class, SpringExtension.class})
final class BenchmarkJobControllerTest {

  @Autowired private MockMvc mockMvc;

  @Autowired private PatchyStub patchyStub;

  @BeforeEach
  public void clearPatchyStub() {
    patchyStub.clearAllFactories();
  }

  @BeforeEach
  public void registerObjectifyClasses() {
    factory().register(BenchmarkJobEntity.class);
    factory().register(BenchmarkJobStatus.class);
  }

  @Test
  public void create_jsonRequestResponse_valid() throws Exception {

    // Setup Cloud Build Stub
    var createJobRequest =
        TestResourceLoader.classPath()
            .forProto(JobInformation.class)
            .loadJson("benchmarkjobs/create_job_request.json");

    var createBuildRequest =
        TestResourceLoader.classPath()
            .forProto(CreateBuildRequest.class)
            .loadText("benchmarkjobs/create_cloud_build_job_request.textproto");

    var buildResponse =
        createBuildRequest.getBuild().toBuilder()
            .setId("some-build-id")
            .setLogUrl("some-build-id-log-url")
            .build();
    patchyStub.addUnaryCallableFactory(new ConstantGetBuildCallable(buildResponse));
    patchyStub.addOperationCallableFactory(
        new VerifyingCreateBuildCallable(
            OperationData.of(
                buildResponse, BuildOperationMetadata.newBuilder().setBuild(buildResponse).build()),
            new CreateBuildRequestValidator(
                createBuildRequest,
                "config_AEROSPIKE_[0-9A-Za-z]+.zip",
                "some-bucket/logs-[A-Za-z0-9]+\\.txt")));

    // Setup Storage Stub
    patchyStub.addUnaryCallableFactory(
        new VerifyingCreateBlobStub(
            /* providedResponse= */ null,
            new StorageBlobValidatorWithUuid(
                /* expectedBucketName= */ "some-bucket",
                /* blobNamePattern= */ "config_AEROSPIKE_[0-9A-Za-z]+.zip",
                ZipFileContent.of(
                    "config/AEROSPIKE.yml",
                    createJobRequest.getBenchmarkYamlBytes().toByteArray()))));

    // Perform Test
    mockMvc
        .perform(
            post("/benchmarkjobs")
                .contentType("application/json")
                .accept("application/json")
                .content(ProtoUtils.toJson(createJobRequest)))
        .andExpect(MockMvcResultMatchers.status().isOk())
        .andExpect(MockMvcResultMatchers.content().contentType("application/json"))
        .andExpect(
            result -> {
              var response =
                  parseProtoJson(result.getResponse().getContentAsString(), BenchmarkJob.class);
              ProtoTruth.assertThat(response)
                  .ignoringFields(BenchmarkJob.ID_FIELD_NUMBER)
                  .isEqualTo(
                      TestResourceLoader.classPath()
                          .forProto(BenchmarkJob.class)
                          .loadJson("benchmarkjobs/create_job_response.json"));

              assertThat(response.getId()).isGreaterThan(0);
            });
  }

  @Test
  public void create_protoRequestResponse_valid() throws Exception {

    // Setup Cloud Build Stub
    var createBuildRequest =
        TestResourceLoader.classPath()
            .forProto(CreateBuildRequest.class)
            .loadText("benchmarkjobs/create_cloud_build_job_request.textproto");

    var buildResponse =
        createBuildRequest.getBuild().toBuilder()
            .setId("some-build-id")
            .setLogUrl("some-build-id-log-url")
            .build();

    patchyStub.addOperationCallableFactory(
        new VerifyingCreateBuildCallable(
            OperationData.of(
                buildResponse, BuildOperationMetadata.newBuilder().setBuild(buildResponse).build()),
            new CreateBuildRequestValidator(
                createBuildRequest,
                "config_AEROSPIKE_[0-9A-Za-z]+.zip",
                "some-bucket/logs-[A-Za-z0-9]+\\.txt")));

    var createJobRequest =
        TestResourceLoader.classPath()
            .forProto(JobInformation.class)
            .loadJson("benchmarkjobs/create_job_request.json");

    // Setup Storage Stub
    patchyStub.addUnaryCallableFactory(
        new VerifyingCreateBlobStub(
            /* providedResponse= */ null,
            new StorageBlobValidatorWithUuid(
                /* expectedBucketName= */ "some-bucket",
                /* blobNamePattern= */ "config_AEROSPIKE_[0-9A-Za-z]+.zip",
                ZipFileContent.of(
                    "config/AEROSPIKE.yml",
                    createJobRequest.getBenchmarkYamlBytes().toByteArray()))));

    // Perform Test
    mockMvc
        .perform(
            post("/benchmarkjobs")
                .contentType("application/x-protobuf;charset=UTF-8")
                .content(createJobRequest.toByteArray()))
        .andExpect(MockMvcResultMatchers.status().isOk())
        .andExpect(
            MockMvcResultMatchers.content().contentType("application/x-protobuf;charset=UTF-8"))
        .andExpect(
            result -> {
              var responseProto =
                  BenchmarkJob.parseFrom(result.getResponse().getContentAsByteArray());
              ProtoTruth.assertThat(responseProto)
                  .ignoringFields(BenchmarkJob.ID_FIELD_NUMBER)
                  .isEqualTo(
                      TestResourceLoader.classPath()
                          .forProto(BenchmarkJob.class)
                          .loadJson("benchmarkjobs/create_job_response.json"));
            });
  }

  @Test
  public void get_jsonRequestResponse_valid() throws Exception {
    var createJobRequestJson =
        TestResourceLoader.classPath().loadAsString("benchmarkjobs/create_job_request.json");

    // Setup Cloud Build Stub
    var createBuildRequest =
        TestResourceLoader.classPath()
            .forProto(CreateBuildRequest.class)
            .loadText("benchmarkjobs/create_cloud_build_job_request.textproto");
    var buildResponse =
        createBuildRequest.getBuild().toBuilder()
            .setId("some-build-id")
            .setLogUrl("some-build-id-log-url")
            .build();
    patchyStub.addUnaryCallableFactory(new ConstantGetBuildCallable(buildResponse));
    patchyStub.addOperationCallableFactory(
        new VerifyingCreateBuildCallable(
            OperationData.of(
                buildResponse, BuildOperationMetadata.newBuilder().setBuild(buildResponse).build()),
            new CreateBuildRequestValidator(
                createBuildRequest,
                "config_AEROSPIKE_[0-9A-Za-z]+.zip",
                "some-bucket/logs-[A-Za-z0-9]+\\.txt")));

    // Setup Storage Stub
    patchyStub.addUnaryCallableFactory(
        new VerifyingCreateBlobStub(
            /* providedResponse= */ null,
            new StorageBlobValidatorWithUuid(
                /* expectedBucketName= */ "some-bucket",
                /* blobNamePattern= */ "config_AEROSPIKE_[0-9A-Za-z]+.zip",
                ZipFileContent.of(
                    "config/AEROSPIKE.yml",
                    parseProtoJson(createJobRequestJson, JobInformation.class)
                        .getBenchmarkYamlBytes()
                        .toByteArray()))));

    // Perform Test
    mockMvc
        .perform(
            post("/benchmarkjobs")
                .contentType("application/json")
                .accept("application/json")
                .content(createJobRequestJson))
        .andExpect(MockMvcResultMatchers.status().isOk())
        .andExpect(MockMvcResultMatchers.content().contentType("application/json"))
        .andDo(
            createResult -> {
              var createdBenchmarkJob =
                  parseProtoJson(
                      createResult.getResponse().getContentAsString(), BenchmarkJob.class);
              mockMvc
                  .perform(
                      get("/benchmarkjobs/" + createdBenchmarkJob.getId())
                          .accept("application/x-protobuf;charset=UTF-8"))
                  .andExpect(MockMvcResultMatchers.status().isOk())
                  .andExpect(
                      result ->
                          ProtoTruth.assertThat(
                                  BenchmarkJob.parseFrom(
                                      result.getResponse().getContentAsByteArray()))
                              .isEqualTo(createdBenchmarkJob));
            });
  }

  private record StorageBlobValidatorWithUuid(
      String expectedBucketName, String blobNamePattern, ZipFileContent singleFileContent)
      implements AssertValidator<CreateBlobRequest> {

    @Override
    public void validate(@Nullable CreateBlobRequest left) {
      try {
        var requestBlobInfo = left.blobInfo();
        assertThat(requestBlobInfo.getName()).matches(blobNamePattern);
        assertThat(requestBlobInfo.getBucket()).isEqualTo(expectedBucketName);
        assertThat(requestBlobInfo.getContentType()).isEqualTo("application/zip");

        ZipTruth.forBinary().assertThat(left.content()).containsExactly(singleFileContent);
      } catch (IOException exception) {
        throw new AssertionError(exception);
      }
    }
  }

  private record CreateBuildRequestValidator(
      CreateBuildRequest expected, String storageBlobNamePattern, String logsBucketPattern)
      implements AssertValidator<CreateBuildRequest> {
    @Override
    public void validate(@Nullable CreateBuildRequest actual) {
      assertThat(actual).isNotNull();
      assertThat(actual.getBuild().getSource().getStorageSource().getObject())
          .matches(storageBlobNamePattern);
      assertThat(actual.getBuild().getLogsBucket()).matches(logsBucketPattern);

      var updatedRequest =
          actual.toBuilder()
              .setBuild(
                  actual.getBuild().toBuilder()
                      .setSource(
                          Source.newBuilder()
                              .setStorageSource(
                                  actual.getBuild().getSource().getStorageSource().toBuilder()
                                      .clearObject()))
                      .clearLogsBucket())
              .build();

      assertThat(updatedRequest).isEqualTo(expected);
    }
  }
}
