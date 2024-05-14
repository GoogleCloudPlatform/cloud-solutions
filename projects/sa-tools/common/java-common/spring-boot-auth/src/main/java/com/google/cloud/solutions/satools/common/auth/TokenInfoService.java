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

/** A service that provides OAuth Token information for a given OAuth2 AccessToken. */
public interface TokenInfoService {

  /**
   * Returns the Token information for the given {@code accessToken} by retrieving it from OAuth
   * server.
   */
  TokenInfo retrieve(AccessToken accessToken);
}
