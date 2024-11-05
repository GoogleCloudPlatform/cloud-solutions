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

import static org.apache.commons.lang3.StringUtils.isNotBlank;

import com.google.auth.http.AuthHttpConstants;
import com.google.auth.oauth2.AccessToken;
import com.google.auth.oauth2.GoogleCredentials;
import jakarta.servlet.http.HttpServletRequest;

/** Utility class to provide Google Credential creation methods. */
public class GoogleAccessTokenService implements AccessTokenCredentialService {

  private final TokenInfo tokenInfo;
  private final AccessToken accessToken;

  /** Simple parameterized constructor. */
  public GoogleAccessTokenService(HttpServletRequest request, TokenInfoService tokeninfoService) {

    var accessTokenString = extractBearerToken(request);

    if (accessTokenString != null) {
      this.tokenInfo = tokeninfoService.retrieve(new AccessToken(accessTokenString, null));
      this.accessToken =
          (!tokenInfo.equals(TokenInfo.getDefaultInstance()))
              ? AccessToken.newBuilder()
                  .setTokenValue(accessTokenString)
                  .setScopes(tokenInfo.scope())
                  .build()
              : AccessToken.newBuilder().setTokenValue("").build();
    } else {
      this.tokenInfo = TokenInfo.getDefaultInstance();
      this.accessToken = AccessToken.newBuilder().setTokenValue("").build();
    }
  }

  @Override
  public AccessToken getAccessToken() {
    return accessToken;
  }

  @Override
  public GoogleCredentials getCredentials() {
    return GoogleCredentials.create(accessToken);
  }

  @Override
  public EmailAddress retrieveEmailAddress() {
    if (accessToken.getTokenValue().equals("")) {
      return new EmailAddress("");
    }

    return new EmailAddress(tokenInfo.email());
  }

  private static String extractBearerToken(HttpServletRequest request) {
    var bearerAuth = request.getHeader(AuthHttpConstants.AUTHORIZATION);

    if (isNotBlank(bearerAuth) && bearerAuth.startsWith(AuthHttpConstants.BEARER)) {
      return bearerAuth.split(" ")[1];
    }

    return null;
  }
}
