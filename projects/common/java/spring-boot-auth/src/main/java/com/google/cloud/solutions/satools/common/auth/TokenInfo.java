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

/**
 * Model for represting Google Token Information object as described in <a
 * href="https://developers.google.com/identity/protocols/oauth2/openid-connect#obtainuserinfo">Obtain
 * User Info</a>.
 */
public record TokenInfo(
    String aud,
    boolean emailVerified,
    int expiresIn,
    int exp,
    String azp,
    String scope,
    String email,
    String sub) {

  public static TokenInfo getDefaultInstance() {
    return new TokenInfo(null, false, 0, 0, null, null, "", null);
  }
}
