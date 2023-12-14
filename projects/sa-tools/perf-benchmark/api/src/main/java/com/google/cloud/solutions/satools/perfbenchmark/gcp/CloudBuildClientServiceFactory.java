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

import com.google.auth.oauth2.GoogleCredentials;
import com.google.cloud.devtools.cloudbuild.v1.CloudBuildClient;
import com.google.cloud.devtools.cloudbuild.v1.CloudBuildSettings;
import com.google.cloud.solutions.satools.common.utils.ServiceFactory;
import com.google.cloud.solutions.satools.perfbenchmark.UserAgentHeaderProvider;
import java.io.IOException;

/** Factory bean to instantiate Cloud Build client for given credentials. */
public class CloudBuildClientServiceFactory
    implements ServiceFactory<CloudBuildClient, GoogleCredentials> {

  private final UserAgentHeaderProvider headerProvider;

  public CloudBuildClientServiceFactory(UserAgentHeaderProvider headerProvider) {
    this.headerProvider = headerProvider;
  }

  @Override
  public CloudBuildClient create() throws IOException {
    return CloudBuildClient.create(settingsMaker());
  }

  @Override
  public CloudBuildClient create(GoogleCredentials credentials) throws IOException {
    return CloudBuildClient.create(
        settingsMaker().toBuilder().setCredentialsProvider(() -> credentials).build());
  }

  protected CloudBuildSettings settingsMaker() throws IOException {
    return CloudBuildSettings.newBuilder().setHeaderProvider(headerProvider).build();
  }
}
