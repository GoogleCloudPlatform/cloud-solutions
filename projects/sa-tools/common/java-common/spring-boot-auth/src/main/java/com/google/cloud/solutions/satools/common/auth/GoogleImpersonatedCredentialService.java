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

import com.google.auth.oauth2.GoogleCredentials;
import com.google.auth.oauth2.ImpersonatedCredentials;
import java.time.Duration;
import java.util.List;

/**
 * Service that validates that the user can Impersonate the given Service Account.
 *
 * <p>Checks if the user as identified through the access token has
 * permissions to impersonate the given Service Account.
 */
public class GoogleImpersonatedCredentialService implements ImpersonatedCredentialService {
  private final AccessTokenCredentialService accessTokenCredentialService;
  private final GoogleMetadataService metadataService;

  public GoogleImpersonatedCredentialService(
      AccessTokenCredentialService accessTokenCredentialService,
      GoogleMetadataService metadataService) {
    this.accessTokenCredentialService = accessTokenCredentialService;
    this.metadataService = metadataService;
  }

  @Override
  public GoogleCredentials getImpersonatedCredentials() {
    return ImpersonatedCredentials.create(
        /*sourceCredential=*/ accessTokenCredentialService.getCredentials(),
        /*targetPrincipal=*/ metadataService.getServiceAccountEmail(),
        /*delegates=*/ null,
        /*scopes=*/ List.of("https://www.googleapis.com/auth/cloud-platform"),
        /*lifetime*/ (int) Duration.ofMinutes(2).toSeconds());
  }
}
