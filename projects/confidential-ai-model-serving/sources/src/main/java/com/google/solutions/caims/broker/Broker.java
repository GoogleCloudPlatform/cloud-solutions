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

import com.google.api.client.http.ByteArrayContent;
import com.google.api.client.http.GenericUrl;
import com.google.api.client.http.HttpRequestFactory;
import com.google.api.client.http.javanet.NetHttpTransport;
import com.google.auth.oauth2.TokenVerifier;
import com.google.common.base.Preconditions;
import com.google.common.reflect.TypeToken;
import com.google.crypto.tink.subtle.Base64;
import com.google.solutions.caims.AbstractServer;
import com.google.solutions.caims.protocol.EncryptedMessage;
import com.google.solutions.caims.workload.AttestationToken;
import java.io.IOException;
import java.security.SecureRandom;
import java.util.Comparator;
import java.util.List;
import java.util.Set;
import org.jetbrains.annotations.NotNull;

/**
 * Intended to be run on Cloud Run, the broker lets clients discover available workload instances
 * and forwards E2E-encrypted requests to the appropriate instance.
 */
public class Broker extends AbstractServer {
  private static final SecureRandom RANDOM = new SecureRandom();
  private static final HttpRequestFactory HTTP_FACTORY =
      new NetHttpTransport().createRequestFactory();

  /** Public endpoint of this broker */
  private final @NotNull Broker.Endpoint endpoint;

  /** Current set of registrations, continuously updated by the daemon */
  private volatile Set<Registration> registrations = Set.of();

  /** Max number of request tokens returned to a client */
  private final int maxRequestTokens;

  public Broker(
      @NotNull Broker.Endpoint endpoint, int listenPort, int threadPoolSize, int maxRequestTokens)
      throws IOException {
    super(listenPort, threadPoolSize);

    this.endpoint = endpoint;
    this.maxRequestTokens = maxRequestTokens;

    //
    // Register HTTP endpoints.
    //
    this.mapGetJson("/", () -> getTokens());
    this.mapPostJson(
        "/forward",
        new TypeToken<List<WorkloadRequest>>() {}.getType(),
        (List<WorkloadRequest> request) -> forwardInferenceRequest(request));
  }

  /**
   * Take a random sample of registrations and return a token for each. Clients can then use one or
   * more of these tokens to make requests to the /forward endpoint.
   */
  private List<RequestToken> getTokens() {
    return this.registrations.stream()
        .sorted(Comparator.comparingDouble(x -> RANDOM.nextInt(32)))
        .limit(this.maxRequestTokens)
        .map(r -> new RequestToken(r.attestationToken))
        .toList();
  }

  /**
   * Dispatch an encrypted inference requests by forwarding it to an available workload instance.
   */
  private @NotNull WorkloadResponse forwardInferenceRequest(
      @NotNull List<WorkloadRequest> requests) {
    Preconditions.checkNotNull(requests, "requests");

    for (var request : requests) {
      //
      // Verify token to ensure the request is legitimate and to find out
      // which instance it belongs to.
      //
      // NB. Here, we don't care whether attestation are production or
      //     debug - this is up to the client to decide.
      //
      AttestationToken.Payload tokenPayload;
      try {
        tokenPayload =
            request.requestToken().attestationToken().verify(this.endpoint.toString(), false);
      } catch (TokenVerifier.VerificationException e) {
        //
        // Token invalid or expired, try next.
        //
        continue;
      }

      //
      // Verify that the corresponding instance is (still) registered. Instances
      // may come and go at any time, so it's possible that it's no longer available.
      //
      var registration =
          this.registrations.stream()
              .filter(
                  r ->
                      r.workloadInstance.equals(
                          new WorkloadInstanceId(
                              tokenPayload.projectId(),
                              tokenPayload.instanceZone(),
                              tokenPayload.instanceName())))
              .findFirst();
      if (registration.isEmpty()) {
        //
        // This instance is no longer registered, try next.
        //
        continue;
      }

      //
      // Forward request.
      //
      var url =
          new GenericUrl(
              String.format(
                  "http://%s.%s.c.%s.internal:8080/",
                  registration.get().workloadInstance.instanceName(),
                  registration.get().workloadInstance.zone(),
                  registration.get().workloadInstance.projectId()));

      System.out.printf(
          "[INFO] Forwarding inference request to %s (%d bytes)\n",
          url, request.encryptedMessage().cipherText().length);

      try {
        var response =
            HTTP_FACTORY
                .buildPostRequest(
                    url,
                    new ByteArrayContent(
                        "application/octet-stream", request.encryptedMessage().cipherText()))
                .setThrowExceptionOnExecuteError(true)
                .execute();

        try (var stream = response.getContent()) {
          //
          // We only need a response from one instance, and we got that. We
          // can therefore exit the loop and ignore any remaining requests.
          //
          return new WorkloadResponse(new EncryptedMessage(stream.readAllBytes()));
        }
      } catch (IOException e) {
        System.err.printf("[ERROR] Forwarding inference request failed: %s\n", e.getMessage());
        e.printStackTrace();
        throw new RuntimeException(e);
      }
    }

    throw new IllegalArgumentException(
        "None of the requested workload instance are available any more");
  }

  /** Replace registrations with the results of a recent discovery. */
  void refreshRegistrations(@NotNull Set<Registration> registrations) {
    this.registrations = registrations;
  }

  /** Endpoint of the broker, used as audience in tokens. */
  public record Endpoint(@NotNull String url) {
    public Endpoint(@NotNull String projectNumber, @NotNull String region) {
      this(String.format("https://broker-%s.%s.run.app/", projectNumber, region));
    }

    @Override
    public String toString() {
      return this.url;
    }
  }

  /** A registered node that is ready to handle requests. */
  public record Registration(
      @NotNull WorkloadInstanceId workloadInstance, @NotNull AttestationToken attestationToken) {}

  /**
   * Request to a particular workload.
   *
   * @param token Request token
   * @param message Encrypted message, base64-encoded
   */
  public record WorkloadRequest(@NotNull String token, @NotNull String message) {
    public WorkloadRequest(@NotNull RequestToken token, @NotNull EncryptedMessage message) {
      this(token.attestationToken().token(), Base64.encode(message.cipherText()));
    }

    @NotNull
    RequestToken requestToken() {
      return new RequestToken(this.token);
    }

    @NotNull
    EncryptedMessage encryptedMessage() {
      return new EncryptedMessage(Base64.decode(this.message));
    }
  }

  /**
   * Response from a workload.
   *
   * @param message Encrypted message, base64-encoded
   */
  public record WorkloadResponse(@NotNull String message) {
    public WorkloadResponse(EncryptedMessage message) {
      this(Base64.encode(message.cipherText()));
    }

    public @NotNull EncryptedMessage toEncryptedMessage() {
      return new EncryptedMessage(Base64.decode(this.message));
    }
  }
}
