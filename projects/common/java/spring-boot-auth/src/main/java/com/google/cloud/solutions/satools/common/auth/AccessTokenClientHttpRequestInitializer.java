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

import com.google.auth.oauth2.AccessToken;
import com.google.common.annotations.VisibleForTesting;
import java.time.Clock;
import java.util.Date;
import org.springframework.http.HttpHeaders;
import org.springframework.http.client.ClientHttpRequest;
import org.springframework.http.client.ClientHttpRequestInitializer;

// this is a utility library, so asset tracking is not necessary
// cloud-solutions/not-tracked-v0.0.0

/** Appends the OAuth AccessToken as request header "AUTHORIZATION". */
public final class AccessTokenClientHttpRequestInitializer implements ClientHttpRequestInitializer {

  private final AccessToken accessToken;
  private final Clock clock;

  @VisibleForTesting
  AccessTokenClientHttpRequestInitializer(AccessToken accessToken, Clock clock) {
    this.accessToken = accessToken;
    this.clock = clock;
  }

  public AccessTokenClientHttpRequestInitializer(AccessToken accessToken) {
    this(accessToken, Clock.systemUTC());
  }

  @Override
  public void initialize(ClientHttpRequest request) {

    if (accessToken.getExpirationTime() != null
        && accessToken.getExpirationTime().before(Date.from(clock.instant()))) {
      throw new RuntimeException("AccessToken expired: " + accessToken.getExpirationTime());
    }

    request.getHeaders().set(HttpHeaders.AUTHORIZATION, "Bearer " + accessToken.getTokenValue());
  }
}
