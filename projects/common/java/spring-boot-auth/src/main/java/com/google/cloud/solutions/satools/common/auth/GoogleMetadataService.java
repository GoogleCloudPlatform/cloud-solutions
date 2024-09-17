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

package com.google.cloud.solutions.satools.common.auth;

import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.RestTemplate;

/** Provides Service Account information for the VM using Google Cloud VM Metadata servers. */
public class GoogleMetadataService implements ComputeMetadataService {

  public static final String METADATA_SERVICE_HOST = "http://metadata.google.internal";
  public static final String SERVICE_ACCOUNT_EMAIL_ENDPOINT =
      "/computeMetadata/v1/instance/service-accounts/default/email";

  private GoogleMetadataService() {}

  public static GoogleMetadataService create() {
    return new GoogleMetadataService();
  }

  @Override
  public String getServiceAccountEmail() {
    var restTemplate = new RestTemplate();
    HttpHeaders headers = new HttpHeaders();
    headers.set("Metadata-Flavor", "Google");
    HttpEntity<Void> requestEntity = new HttpEntity<>(headers);

    ResponseEntity<String> response =
        restTemplate.exchange(
            METADATA_SERVICE_HOST + SERVICE_ACCOUNT_EMAIL_ENDPOINT,
            HttpMethod.GET,
            requestEntity,
            String.class);

    return response.getBody();
  }
}
