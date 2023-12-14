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
import com.google.cloud.solutions.satools.common.utils.ServiceFactory;
import com.google.cloud.solutions.satools.perfbenchmark.UserAgentHeaderProvider;
import com.google.cloud.storage.Storage;
import com.google.cloud.storage.StorageOptions;

/** Factory bean that creates Google Cloud Storage client using provided credentials. */
public class StorageClientServiceFactory implements ServiceFactory<Storage, GoogleCredentials> {

  private final UserAgentHeaderProvider headerProvider;

  public StorageClientServiceFactory(UserAgentHeaderProvider headerProvider) {
    this.headerProvider = headerProvider;
  }

  @Override
  public Storage create() {
    return optionsMaker().getService();
  }

  @Override
  public Storage create(GoogleCredentials credentials) {
    return optionsMaker().toBuilder().setCredentials(credentials).build().getService();
  }

  protected StorageOptions optionsMaker() {
    return StorageOptions.newBuilder().setHeaderProvider(headerProvider).build();
  }
}
