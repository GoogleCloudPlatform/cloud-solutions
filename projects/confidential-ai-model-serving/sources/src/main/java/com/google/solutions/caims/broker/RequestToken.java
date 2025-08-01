//
// Copyright 2025 Google LLC
//
// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements.  See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership.  The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License.  You may obtain a copy of the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an
// "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
// KIND, either express or implied.  See the License for the
// specific language governing permissions and limitations
// under the License.
//

package com.google.solutions.caims.broker;

import com.google.solutions.caims.workload.AttestationToken;
import org.jetbrains.annotations.NotNull;

/**
 * Token that entitles a client to perform a request to a specific workload instance. <br>
 * Instead of letting the broker mint a new kind of token, we're reusing the workload instance's
 * attestation token as request token. This has two advantages:
 *
 * <ol>
 *   <li>Assuming the workload image is public (which it should be), a user can convince themselves
 *       that the attestation token incorporates no information that would identify the user.
 *   <li>The attestation token has a limited lifetime (1h) and is a JWT, and is can be verified
 *       using standard means.
 *   <li>Even if we let the broker mint a new kind of token, the broker would still have to present
 *       the attestation token to the client so that the client can verify its claims.
 * </ol>
 *
 * @param attestationToken attestation token of the workload instance.
 */
public record RequestToken(@NotNull AttestationToken attestationToken) {

  public RequestToken(@NotNull String token) {
    this(new AttestationToken(token));
  }
}
