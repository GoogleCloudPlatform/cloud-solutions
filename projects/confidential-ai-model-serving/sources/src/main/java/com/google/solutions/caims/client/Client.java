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

package com.google.solutions.caims.client;

import com.google.api.client.http.ByteArrayContent;
import com.google.api.client.http.GenericUrl;
import com.google.api.client.http.HttpRequestFactory;
import com.google.api.client.http.javanet.NetHttpTransport;
import com.google.api.client.json.JsonObjectParser;
import com.google.api.client.json.gson.GsonFactory;
import com.google.common.reflect.TypeToken;
import com.google.gson.Gson;
import com.google.solutions.caims.broker.Broker;
import com.google.solutions.caims.broker.RequestToken;
import com.google.solutions.caims.protocol.EncryptedMessage;
import com.google.solutions.caims.protocol.Message;
import com.google.solutions.caims.protocol.RequestEncryptionKeyPair;
import com.google.solutions.caims.workload.AttestationToken;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Comparator;
import java.util.LinkedList;
import java.util.List;
import org.jetbrains.annotations.NotNull;

/**
 * Example client simulates a (phone) app that lets users enter prompts and send them to workload
 * instances.
 */
public class Client {
  private static final SecureRandom RANDOM = new SecureRandom();
  private static final GsonFactory GSON_FACTORY = new GsonFactory();
  private static final Gson GSON = new Gson();
  private static final HttpRequestFactory HTTP_FACTORY =
      new NetHttpTransport().createRequestFactory();
  private final @NotNull Broker.Endpoint endpoint;
  private final boolean debug;

  public Client(@NotNull Broker.Endpoint endpoint, boolean debug) {
    this.endpoint = endpoint;
    this.debug = debug;
  }

  public int run() throws Exception {
    //
    // Get tokens from broker.
    //
    List<RequestToken> tokens = null;
    while (tokens == null || tokens.isEmpty()) {
      tokens = getTokens();
      if (tokens.isEmpty()) {
        System.err.println("[INFO] Waiting for workload instances to become available...");

        try {
          Thread.sleep(5000);
        } catch (InterruptedException ignored) {
        }
      }
    }

    System.out.println();
    System.out.println("Your prompts will be served by one of the following workload instances:");
    System.out.println();
    System.out.println(
        "Instance        Zone               Prod  Hardware        OS                 Image");
    System.out.println(
        "--------------- ------------------ ----- --------------- ------------------ ------------");

    //
    // Verify and inspect the tokens we got.
    //
    var workloadInstances = new LinkedList<WorkloadInstance>();
    for (var token : tokens) {
      //
      // Each token corresponds to a workload instance. Verify the token
      // and extract the public key of the workload instance.
      //
      var attestation = token.attestationToken().verify(this.endpoint.url(), !this.debug);

      System.out.printf(
          "%-15s %-18s %-5s %-15s %-18s %-12s\n",
          attestation.instanceName(),
          attestation.instanceZone(),
          attestation.isProduction(),
          attestation.hardwareModel(),
          attestation.operatingSystem(),
          attestation.imageDigest());

      workloadInstances.add(new WorkloadInstance(token, attestation));
    }

    System.out.println();

    try (var reader = new BufferedReader(new InputStreamReader(System.in))) {
      while (true) {
        //
        // Create a local, ephemeral key pair for encrypting messages. We use
        // each keypair for a single prompt only, that makes it more difficult
        // for the broker and workload to link two messages as coming from
        // the same client.
        //
        var keyPair = RequestEncryptionKeyPair.generate();

        //
        // Prompt for input.
        //
        System.out.print("Enter a question> ");
        var prompt = reader.readLine();
        if (prompt.isBlank()) {
          break;
        }

        //
        // Select a random subset of workload instances.
        //
        var requests = new LinkedList<Broker.WorkloadRequest>();
        for (var workloadInstance :
            workloadInstances.stream()
                .sorted(Comparator.comparingDouble(x -> RANDOM.nextInt(32)))
                .limit(5)
                .toList()) {
          //
          // Encrypt the prompt for the specific workload instance.
          //
          var message =
              new Message(prompt, keyPair.publicKey())
                  .encrypt(workloadInstance.attestation.requestEncryptionKey());

          requests.add(new Broker.WorkloadRequest(workloadInstance.requestToken, message));
        }

        //
        // Send the batch of requests to the broker.
        //
        var response = forward(requests);
        var clearTextResponse = response.decrypt(keyPair.privateKey()).toString();

        System.out.println(clearTextResponse);
        System.out.println();
      }
    }
    return 0;
  }

  private List<RequestToken> getTokens() throws IOException {
    var response =
        HTTP_FACTORY
            .buildGetRequest(new GenericUrl(this.endpoint.url()))
            .setParser(new JsonObjectParser(GSON_FACTORY))
            .execute();

    try (var reader = new InputStreamReader(response.getContent(), response.getContentCharset())) {
      return GSON.fromJson(reader, new TypeToken<List<RequestToken>>() {}.getType());
    }
  }

  private EncryptedMessage forward(List<Broker.WorkloadRequest> requests) throws IOException {
    var response =
        HTTP_FACTORY
            .buildPostRequest(
                new GenericUrl(this.endpoint.url() + "forward"),
                new ByteArrayContent(
                    "application/json", GSON.toJson(requests).getBytes(StandardCharsets.UTF_8)))
            .setParser(new JsonObjectParser(GSON_FACTORY))
            .execute();

    try (var reader = new InputStreamReader(response.getContent(), response.getContentCharset())) {
      return GSON.fromJson(reader, Broker.WorkloadResponse.class).toEncryptedMessage();
    }
  }

  /** Captures information about a workload instance that we can send requests to. */
  private record WorkloadInstance(
      @NotNull RequestToken requestToken, @NotNull AttestationToken.Payload attestation) {}
}
