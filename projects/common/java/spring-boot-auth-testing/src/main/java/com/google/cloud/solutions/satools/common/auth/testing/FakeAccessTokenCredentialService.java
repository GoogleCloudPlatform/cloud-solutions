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

package com.google.cloud.solutions.satools.common.auth.testing;

import com.google.auth.oauth2.AccessToken;
import com.google.auth.oauth2.GoogleCredentials;
import com.google.cloud.solutions.satools.common.auth.AccessTokenCredentialService;

/** Fake access token credential service for testing purposes. */
public class FakeAccessTokenCredentialService implements AccessTokenCredentialService {

  private final String fakeEmail;

  public FakeAccessTokenCredentialService(String fakeEmail) {
    this.fakeEmail = fakeEmail;
  }

  @Override
  public AccessToken getAccessToken() {
    return new AccessToken("", null);
  }

  @Override
  public GoogleCredentials getCredentials() {
    return GoogleCredentials.create(getAccessToken());
  }

  @Override
  public EmailAddress retrieveEmailAddress() {
    return new EmailAddress(fakeEmail);
  }
}
