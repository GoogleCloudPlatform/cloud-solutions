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

package com.google.solutions.caims.workload;

import com.google.api.client.json.webtoken.JsonWebToken;
import com.google.auth.oauth2.TokenVerifier;
import com.google.solutions.caims.protocol.RequestEncryptionKeyPair;
import java.security.GeneralSecurityException;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import org.jetbrains.annotations.NotNull;

/** A token attesting the configuration of the TEE and its VM. */
public record AttestationToken(@NotNull String token) {
  /** Issuer used by the attestation provider */
  private static final String ATTESTATION_ISSUER = "https://confidentialcomputing.googleapis.com";

  /** URL to the public keys which attestations can be verified against */
  private static final String ATTESTATION_JWKS_URL =
      "https://www.googleapis.com/service_accounts/v1/metadata/jwk/signer@confidentialspace-sign.iam.gserviceaccount.com";

  /** Verify the authenticity of an attestation token and extract its claims. */
  public Payload verify(@NotNull String expectedAudience, boolean requireProduction)
      throws TokenVerifier.VerificationException {
    //
    // Perform a default verification on the JWT, which includes checking that
    // the token has been issued by the expected issuer, i.e. the Confidential
    // Space attestation provider.
    //
    // NB. The TokenVerifier class can't extract the JWKS URL from the OIDC
    //     provider's metadata document automatically, so we explicitly pass
    //     the JWKS URL.
    //
    var payload =
        new Payload(
            TokenVerifier.newBuilder()
                .setCertificatesLocation(ATTESTATION_JWKS_URL)
                .setIssuer(ATTESTATION_ISSUER)
                .setAudience(expectedAudience)
                .build()
                .verify(this.token)
                .getPayload());

    if (requireProduction && !payload.isProduction()) {
      throw new TokenVerifier.VerificationException(
          String.format(
              "The attested node '%s' is in debug mode and can't be trusted",
              payload.instanceName()));
    }

    return payload;
  }

  public record Payload(@NotNull JsonWebToken.Payload jsonPayload) {
    private @NotNull String submodClaim(@NotNull String section, @NotNull String claim) {
      if (this.jsonPayload.get("submods") instanceof Map<?, ?> submods
          && submods.get(section) instanceof Map<?, ?> gce
          && gce.get(claim) instanceof String instance) {
        return instance;
      } else {
        throw new IllegalStateException(
            String.format("The token does not contain a %s claim", claim));
      }
    }

    /**
     * Check if the attested node is in production mode. Debug nodes are accessible to operators and
     * therefore can't be trusted.
     */
    public boolean isProduction() {
      return this.jsonPayload.get("dbgstat").equals("disabled-since-boot");
    }

    /** Get the node's request encryption key. */
    public @NotNull RequestEncryptionKeyPair.PublicKey requestEncryptionKey()
        throws GeneralSecurityException, TokenVerifier.VerificationException {
      if (this.jsonPayload.get("eat_nonce") instanceof List<?> nonces) {
        return RequestEncryptionKeyPair.PublicKey.fromBase64(
            nonces.stream().map(Object::toString).collect(Collectors.joining("")));
      } else {
        throw new TokenVerifier.VerificationException(
            "The attestation token does not contain a request encryption key");
      }
    }

    /** Get the name of the attested instance. */
    public @NotNull String instanceName() {
      return submodClaim("gce", "instance_name");
    }

    /** Get the zone the attested instance resides in. */
    public @NotNull String instanceZone() {
      return submodClaim("gce", "zone");
    }

    /** Get the project the attested instance resides in. */
    public @NotNull String projectId() {
      return submodClaim("gce", "project_id");
    }

    /** Get the name of the approved operating system for the VM. */
    public @NotNull String operatingSystem() {
      return this.jsonPayload.get("swname").toString();
    }

    /** Get the name of the hardware model. */
    public @NotNull String hardwareModel() {
      return this.jsonPayload.get("hwmodel").toString();
    }

    /** Get the shortened image digest */
    public @NotNull String imageDigest() {
      return submodClaim("container", "image_digest")
          .substring("sha256:".length())
          .substring(0, 12);
    }
  }
}
