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

import com.google.api.gax.rpc.ClientSettings;
import com.google.api.gax.rpc.FixedHeaderProvider;
import com.google.cloud.compute.v1.InstancesClient;
import com.google.cloud.dataproc.v1.ClusterControllerClient;
import com.google.cloud.monitoring.v3.QueryServiceClient;
import java.io.IOException;

/**
 * Factory for instantiating Google Cloud API Clients.
 *
 * <p>The interface is separated out to simplify injecting fake factory for testing.
 */
public interface GoogleCloudServicesFactory {

  InstancesClient gceInstancesClient() throws IOException;

  QueryServiceClient monitoringQueryServiceClient() throws IOException;

  ClusterControllerClient dataprocClusterControllerClient() throws IOException;

  /** Default implementation of adding custom user-agent to API clients for usage tracking. */
  default <T extends ClientSettings<T>, B extends ClientSettings.Builder<T, B>>
      ClientSettings.Builder<T, B> instrumentUserAgent(
          ClientSettings.Builder<T, B> settingsBuilder) {
    settingsBuilder.setHeaderProvider(
        FixedHeaderProvider.create("User-Agent", "cloud-solutions/trino-autoscaler-tool-v0.1"));
    return settingsBuilder;
  }
}
