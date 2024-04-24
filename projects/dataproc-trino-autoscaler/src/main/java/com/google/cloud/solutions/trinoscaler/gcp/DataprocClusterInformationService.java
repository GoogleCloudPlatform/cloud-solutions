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

import static com.google.common.base.Verify.verify;

import com.google.cloud.solutions.trinoscaler.ClusterInformation;
import com.google.cloud.solutions.trinoscaler.ClusterInformationService;
import com.google.cloud.solutions.trinoscaler.Factory;
import java.io.IOException;
import java.util.regex.Pattern;
import okhttp3.OkHttpClient;
import okhttp3.Request;

/**
 * Retrieves Dataproc cluster information stored as metadata on the cluster's master node using
 * Google Cloud <a href="https://cloud.google.com/compute/docs/metadata/overview">VM Metadata
 * service</a>.
 */
public class DataprocClusterInformationService implements ClusterInformationService {

  private static final Pattern ZONE_EXTRACT_PATTERN = Pattern.compile("([^/]+)$");

  private final SelfInstanceMetadataService instanceMetadataService;

  private final Factory<OkHttpClient> okHttpClientFactory;

  public DataprocClusterInformationService(Factory<OkHttpClient> okHttpClientFactory) {
    this.okHttpClientFactory = okHttpClientFactory;
    this.instanceMetadataService = new SelfInstanceMetadataService();
  }

  @Override
  public ClusterInformation retrieve() throws IOException {
    return ClusterInformation.create(
        instanceMetadataService.retrieveSingleValue("/project/project-id"),
        instanceMetadataService.retrieveInstanceLabel("dataproc-region"),
        extractZoneValue(instanceMetadataService.retrieveSingleValue("/instance/zone")),
        instanceMetadataService.retrieveInstanceLabel("dataproc-cluster-name"));
  }

  private static String extractZoneValue(String zoneString) {
    var matcher = ZONE_EXTRACT_PATTERN.matcher(zoneString);
    verify(matcher.find(), "Provided zoneString(%s) didn't match pattern", zoneString);
    return matcher.group(1);
  }

  /** Retrieves a given metadata from GCE metadata service. */
  private class SelfInstanceMetadataService {

    private static final String INTERNAL_METADATA_SERVICE_HOST =
        "http://metadata.google.internal/computeMetadata/v1";

    public String retrieveSingleValue(String key) throws IOException {

      try (var response =
          okHttpClientFactory
              .create()
              .newCall(
                  new Request.Builder()
                      .url(INTERNAL_METADATA_SERVICE_HOST + key)
                      .addHeader("Metadata-Flavor", "Google")
                      .get()
                      .build())
              .execute()) {

        return (response.body() != null) ? response.body().string() : "";
      }
    }

    public String retrieveInstanceLabel(String label) throws IOException {
      return retrieveSingleValue("/instance/attributes/" + label);
    }
  }
}
