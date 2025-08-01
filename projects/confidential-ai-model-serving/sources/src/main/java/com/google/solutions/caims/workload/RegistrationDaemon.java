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

import com.google.solutions.caims.broker.Broker;
import org.jetbrains.annotations.NotNull;

/** Daemon that registers the workload server. */
public class RegistrationDaemon extends Thread {
  private static final int MINUTES = 60 * 1000;
  public static final String GUEST_ATTRIBUTE_NAMESPACE = "workload-server";
  public static final String GUEST_ATTRIBUTE_NAME = "token";

  private final @NotNull Broker.Endpoint brokerId;
  private final @NotNull Workload server;
  private final @NotNull ConfidentialSpace confidentialSpace;
  private final @NotNull MetadataClient metadataClient;

  public RegistrationDaemon(
      @NotNull Broker.Endpoint brokerId,
      @NotNull Workload server,
      @NotNull ConfidentialSpace confidentialSpace,
      @NotNull MetadataClient metadataClient) {
    this.brokerId = brokerId;
    this.server = server;
    this.confidentialSpace = confidentialSpace;
    this.metadataClient = metadataClient;

    setDaemon(true);
  }

  @SuppressWarnings("InfiniteLoopStatement")
  @Override
  public void run() {
    //
    // Register the server and keep refreshing the registration
    // every so often. The refresh is necessary because the attestation
    // token has a finite lifetime.
    //
    while (true) {
      System.out.println("[INFO] Refreshing server registration...");

      try {
        //
        // Get a fresh attestation tokens and publish it as guest attribute
        // so that the broker can discover and use the workload server.
        //
        var attestationToken =
            this.confidentialSpace.getAttestationToken(
                this.brokerId.toString(), this.server.publicKey());

        this.metadataClient.setGuestAttribute(
            GUEST_ATTRIBUTE_NAMESPACE, GUEST_ATTRIBUTE_NAME, attestationToken.token());
      } catch (Exception e) {
        System.err.printf("[ERROR] Server registration failed: %s\n", e.getMessage());
        e.printStackTrace();
      }

      //
      // Wait a bit and start over.
      //
      try {
        Thread.sleep(5 * MINUTES);
      } catch (InterruptedException ignored) {
      }
    }
  }
}
