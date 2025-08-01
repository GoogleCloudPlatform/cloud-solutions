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

import com.google.solutions.caims.AbstractServer;
import com.google.solutions.caims.protocol.EncryptedMessage;
import com.google.solutions.caims.protocol.Message;
import com.google.solutions.caims.protocol.RequestEncryptionKeyPair;
import java.io.IOException;
import java.security.GeneralSecurityException;
import org.jetbrains.annotations.NotNull;

/** Workload server, intended to run in a Confidential Space Trusted Execution Environment (TEE). */
public class Workload extends AbstractServer {
  /** The server's key pair, used for en/decrypting messages */
  private final @NotNull RequestEncryptionKeyPair keyPair;

  public @NotNull RequestEncryptionKeyPair.PublicKey publicKey() {
    return this.keyPair.publicKey();
  }

  public Workload(int listenPort, int threadPoolSize) throws GeneralSecurityException, IOException {
    super(listenPort, threadPoolSize);

    //
    // Generate a new key pair. The key pair remains valid for the lifetime
    // of the process. Clients use the pair's public key to encrypt their
    // requests.
    //
    this.keyPair = RequestEncryptionKeyPair.generate();

    //
    // Register HTTP endpoints.
    //
    this.mapPostEncrypted("/", request -> handleInferenceRequest(request));
  }

  private EncryptedMessage handleInferenceRequest(@NotNull EncryptedMessage encryptedRequest) {
    System.out.println("[INFO] Handling inference request...");
    try {
      //
      // Decrypt the request using the server's private key.
      //
      var request = encryptedRequest.decrypt(this.keyPair.privateKey());

      //
      // Handle the request, for example by forwarding the request to some LLM server
      // that's running in the same container.
      //
      // As an example, we generate a static fake response and send that back to the client,
      // encrypted it using the client's key.
      //
      var response = new Message(String.format("> %s\nThat's a good question.", request), null);

      var encryptedResponse =
          response.encrypt(
              request
                  .senderPublicKey()
                  .orElseThrow(
                      () ->
                          new IllegalArgumentException(
                              "The client did not provide its public key")));

      System.out.printf(
          "[INFO] Finished inference request (response size: %d bytes)\n",
          encryptedRequest.cipherText().length);

      return encryptedResponse;
    } catch (GeneralSecurityException | IOException e) {
      throw new RuntimeException(e);
    }
  }
}
