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

import static java.util.Objects.requireNonNull;

import com.google.auth.oauth2.AccessToken;
import com.google.auth.oauth2.GoogleCredentials;
import org.apache.commons.codec.digest.DigestUtils;

/**
 * Methods to abstract building OAuth Credentials for different systems including ones for Google,
 * e.g. {@code GoogleAppEngineDefaultServiceAccountCredentialService}
 */
public interface AccessTokenCredentialService {

  /** Returns the OAuth2 AccessToken with no expiry defined. */
  AccessToken getAccessToken();

  /** Provides Credential Object based on the access token. */
  GoogleCredentials getCredentials();

  /**
   * The principal's email address when "email" scope is present.
   *
   * <p>The {@code EmailAddress#email} will return empty string when "email" scope is not present on
   * the token.
   *
   * @return The principal's email address.
   */
  EmailAddress retrieveEmailAddress();

  /** Convenience record class to provide clean-text email and SHA256 hashed email address. */
  class EmailAddress {

    private final String email;

    public EmailAddress(String email) {
      this.email = requireNonNull(email, "email can't be null");
    }

    public String email() {
      return email;
    }

    public String sha256() {
      return DigestUtils.sha256Hex(email);
    }
  }
}
