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

package com.google.cloud.solutions.trinoscaler.gcp;

import com.google.cloud.compute.v1.InstancesClient;
import com.google.cloud.compute.v1.InstancesSettings;
import com.google.cloud.dataproc.v1.ClusterControllerClient;
import com.google.cloud.dataproc.v1.ClusterControllerSettings;
import com.google.cloud.monitoring.v3.QueryServiceClient;
import com.google.cloud.monitoring.v3.QueryServiceSettings;
import com.google.cloud.solutions.trinoscaler.ClusterInformation;
import com.google.cloud.solutions.trinoscaler.GoogleCloudServicesFactory;
import java.io.IOException;

/** Factory to instantiate Google Cloud API clients for use in production. */
public class ProductionGoogleCloudServicesFactory implements GoogleCloudServicesFactory {

  private final ClusterInformation clusterInformation;

  private ProductionGoogleCloudServicesFactory(ClusterInformation clusterInformation) {
    this.clusterInformation = clusterInformation;
  }

  public static GoogleCloudServicesFactory create(ClusterInformation clusterInformation) {
    return new ProductionGoogleCloudServicesFactory(clusterInformation);
  }

  @Override
  public InstancesClient gceInstancesClient() throws IOException {
    return InstancesClient.create(instrumentUserAgent(InstancesSettings.newBuilder()).build());
  }

  @Override
  public QueryServiceClient monitoringQueryServiceClient() throws IOException {
    return QueryServiceClient.create(
        instrumentUserAgent(QueryServiceSettings.newBuilder()).build());
  }

  @Override
  public ClusterControllerClient dataprocClusterControllerClient() throws IOException {
    return ClusterControllerClient.create(
        instrumentUserAgent(ClusterControllerSettings.newBuilder())
            .setEndpoint(clusterInformation.region() + "-dataproc.googleapis.com:443")
            .build());
  }
}
