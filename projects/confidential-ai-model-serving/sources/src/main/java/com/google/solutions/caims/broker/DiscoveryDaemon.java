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

import com.google.api.client.googleapis.javanet.GoogleNetHttpTransport;
import com.google.api.client.json.gson.GsonFactory;
import com.google.api.services.compute.Compute;
import com.google.auth.http.HttpCredentialsAdapter;
import com.google.auth.oauth2.GoogleCredentials;
import com.google.solutions.caims.UserAgent;
import com.google.solutions.caims.workload.AttestationToken;
import com.google.solutions.caims.workload.RegistrationDaemon;
import java.io.IOException;
import java.security.GeneralSecurityException;
import java.util.HashSet;
import java.util.Optional;
import org.jetbrains.annotations.NotNull;

/** Daemon that discovers workload servers and updates the {@see Broker}. */
public class DiscoveryDaemon extends Thread {
  private final @NotNull Broker broker;
  private final @NotNull Compute computeClient;
  private final @NotNull String projectId;

  public DiscoveryDaemon(
      @NotNull Broker broker, @NotNull GoogleCredentials credentials, @NotNull String projectId)
      throws GeneralSecurityException, IOException {
    this.broker = broker;
    this.projectId = projectId;

    this.computeClient =
        new Compute.Builder(
                GoogleNetHttpTransport.newTrustedTransport(),
                new GsonFactory(),
                new HttpCredentialsAdapter(credentials))
            .setApplicationName(UserAgent.VALUE)
            .build();

    setDaemon(true);
  }

  @SuppressWarnings("InfiniteLoopStatement")
  @Override
  public void run() {
    while (true) {
      try {
        //
        // Find all confidential space instances in the project.
        //
        var instances =
            this.computeClient
                .instances()
                .aggregatedList(this.projectId)
                .setReturnPartialSuccess(true)
                .setFilter("status=\"RUNNING\"")
                .execute();

        var confidentialSpaceInstances =
            instances.getItems().values().stream()
                .flatMap(i -> Optional.ofNullable(i.getInstances()).stream())
                .flatMap(i -> i.stream())
                .filter(
                    i ->
                        i.getMetadata().getItems().stream()
                            .anyMatch(m -> m.getKey().equals("tee-image-reference")))
                .toList();

        var registrations = new HashSet<Broker.Registration>();
        for (var instance : confidentialSpaceInstances) {
          var zoneId = instance.getZone().substring(instance.getZone().lastIndexOf('/') + 1);

          //
          // Read the instance's attestation token. This might fail if the instance
          // hasn't finished initializing yet or if it's an unrelated instance.
          //
          try {
            var attestationToken =
                new AttestationToken(
                    this.computeClient
                        .instances()
                        .getGuestAttributes(this.projectId, zoneId, instance.getName())
                        .setQueryPath(
                            String.format(
                                "%s/%s",
                                RegistrationDaemon.GUEST_ATTRIBUTE_NAMESPACE,
                                RegistrationDaemon.GUEST_ATTRIBUTE_NAME))
                        .execute()
                        .getQueryValue()
                        .getItems()
                        .stream()
                        .findFirst()
                        .map(v -> v.getValue())
                        .get());

            var registration =
                new Broker.Registration(
                    new WorkloadInstanceId(this.projectId, zoneId, instance.getName()),
                    attestationToken);
            System.out.printf(
                "[INFO] Discovered workload instance %s\n", registration.workloadInstance());
            registrations.add(registration);
          } catch (Exception e) {
            System.err.printf(
                "[INFO] Ignoring instance %s because it has not registered an attestation token"
                    + " (%s)\n",
                instance.getName(), e.getMessage());
          }
        }

        //
        // We've scanned all relevant instance and have an up-to-date view on
        // which instances are available.
        //
        this.broker.refreshRegistrations(registrations);
      } catch (IOException e) {
        System.err.printf("[ERROR] Instance discovery failed: %s\n", e.getMessage());
        e.printStackTrace();
      }

      //
      // Wait a bit and start over.
      //
      try {
        Thread.sleep(20 * 1000);
      } catch (InterruptedException ignored) {
      }
    }
  }
}
