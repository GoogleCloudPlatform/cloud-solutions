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
import com.google.gson.FieldNamingPolicy;
import com.google.gson.GsonBuilder;
import java.util.List;
import org.springframework.http.converter.json.GsonHttpMessageConverter;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

/** Retrieves the OAuth token information from Google servers for the given Access Token. */
public final class GoogleTokenInfoService implements TokenInfoService {

  private static final String GOOGLE_TOKEN_INFO_ENDPOINT =
      "https://oauth2.googleapis.com/tokeninfo";

  private final String tokenInfoEndpoint;

  @VisibleForTesting
  GoogleTokenInfoService(String tokenInfoEndpoint) {
    this.tokenInfoEndpoint = tokenInfoEndpoint;
  }

  public GoogleTokenInfoService() {
    this(GOOGLE_TOKEN_INFO_ENDPOINT);
  }

  @Override
  public TokenInfo retrieve(AccessToken accessToken) {

    var restTemplate = new RestTemplate();
    restTemplate.setClientHttpRequestInitializers(
        List.of(new AccessTokenClientHttpRequestInitializer(accessToken)));
    restTemplate.setMessageConverters(
        List.of(
            new GsonHttpMessageConverter(
                new GsonBuilder()
                    .setFieldNamingPolicy(FieldNamingPolicy.LOWER_CASE_WITH_UNDERSCORES)
                    .create())));
    try {
      return restTemplate.getForObject(tokenInfoEndpoint, TokenInfo.class);
    } catch (RestClientException restClientException) {
      return TokenInfo.getDefaultInstance();
    }
  }
}
