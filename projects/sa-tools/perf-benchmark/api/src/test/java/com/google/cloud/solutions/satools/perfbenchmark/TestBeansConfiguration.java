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

import com.google.auth.oauth2.GoogleCredentials;
import com.google.cloud.bigquery.BigQuery;
import com.google.cloud.devtools.cloudbuild.v1.CloudBuildClient;
import com.google.cloud.solutions.satools.common.auth.AccessTokenCredentialService;
import com.google.cloud.solutions.satools.common.auth.ComputeMetadataService;
import com.google.cloud.solutions.satools.common.auth.ImpersonatedCredentialService;
import com.google.cloud.solutions.satools.common.auth.testing.FakeAccessTokenCredentialService;
import com.google.cloud.solutions.satools.common.testing.stubs.PatchyStub;
import com.google.cloud.solutions.satools.common.testing.stubs.bigquery.PatchyBigQueryStub;
import com.google.cloud.solutions.satools.common.testing.stubs.cloudbuild.PatchyCloudBuildStub;
import com.google.cloud.solutions.satools.common.testing.stubs.storage.PatchyStorage;
import com.google.cloud.solutions.satools.perfbenchmark.gcp.BigQueryClientFactory;
import com.google.cloud.solutions.satools.perfbenchmark.gcp.CloudBuildClientServiceFactory;
import com.google.cloud.solutions.satools.perfbenchmark.gcp.StorageClientServiceFactory;
import com.google.cloud.storage.Storage;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;

/** Setup all Spring beans for test profile. */
@TestConfiguration
public class TestBeansConfiguration {

  @Bean
  public Clock testingFixedClockBean() {
    return Clock.fixed(Instant.parse("2023-02-06T16:21:07.365Z"), ZoneOffset.UTC);
  }

  @Bean
  public AccessTokenCredentialService fakeAccessTokenCredentialService() {
    return new FakeAccessTokenCredentialService("user1@example.com");
  }

  @Bean
  public PatchyStub patchyStub() {
    return new PatchyStub();
  }

  @Bean
  CloudBuildClientServiceFactory patchyCloudBuildServiceFactory(PatchyStub operationsStub) {
    return new CloudBuildClientServiceFactory(null) {
      @Override
      public CloudBuildClient create() {
        throw new UnsupportedOperationException();
      }

      @Override
      public CloudBuildClient create(GoogleCredentials credentials) {
        return CloudBuildClient.create(new PatchyCloudBuildStub(operationsStub));
      }
    };
  }

  @Bean
  StorageClientServiceFactory fakeStorageClientFactory(PatchyStub patchyStub) {
    return new StorageClientServiceFactory(null) {
      @Override
      public Storage create() {
        throw new UnsupportedOperationException();
      }

      @Override
      public Storage create(GoogleCredentials credentials) {
        return new PatchyStorage(patchyStub);
      }
    };
  }

  @Bean
  BigQueryClientFactory fakeBigQueryFactory(PatchyStub patchyStub) {

    return new BigQueryClientFactory(null) {

      @Override
      public BigQuery create() {
        return new PatchyBigQueryStub(patchyStub);
      }

      @Override
      public BigQuery create(GoogleCredentials credentials) {
        throw new UnsupportedOperationException();
      }
    };
  }

  @Bean
  public ImpersonatedCredentialService fakeImpersonationService(
      @Autowired AccessTokenCredentialService accessTokenCredentialService) {
    return accessTokenCredentialService::getCredentials;
  }

  @Bean
  ComputeMetadataService fakeComputeMetadataService() {
    return new ComputeMetadataService() {
      @Override
      public String getServiceAccountEmail() {
        return "fakeServiceAccount@google.com";
      }
    };
  }
}
