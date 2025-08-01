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

package com.google.solutions.caims;

import com.google.api.client.util.GenericData;
import com.google.auth.oauth2.GoogleCredentials;
import com.google.crypto.tink.hybrid.HybridConfig;
import com.google.solutions.caims.broker.Broker;
import com.google.solutions.caims.broker.DiscoveryDaemon;
import com.google.solutions.caims.client.Client;
import com.google.solutions.caims.workload.ConfidentialSpace;
import com.google.solutions.caims.workload.MetadataClient;
import com.google.solutions.caims.workload.RegistrationDaemon;
import com.google.solutions.caims.workload.Workload;
import java.io.IOException;
import java.security.GeneralSecurityException;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;
import org.jetbrains.annotations.NotNull;

/**
 * Contains the application's main entry point. <br>
 * The application can be run in 3 different modes, client, broker, and workload.
 */
public class Program {
  static {
    //
    // Initialize Tink so that we can use HPKE.
    //
    try {
      HybridConfig.register();
    } catch (GeneralSecurityException e) {
      throw new RuntimeException("Initializing Tink failed", e);
    }
  }

  /** Entry point, typically invoked using maven or by running <c>java -jar</c>. */
  public static void main(String[] args) throws Exception {
    var action = Arrays.stream(args).findFirst().orElse("");

    switch (action) {
      case "client":
        {
          System.exit(runClient(Arrays.stream(args).skip(1).toList()));
        }
      case "broker":
        {
          startBroker();
          break;
        }
      case "workload":
        {
          startWorkload();
          break;
        }
      default:
        System.exit(showUsageInformation("Unrecognized action"));
    }
  }

  /** Show usage information for the command line app. */
  private static int showUsageInformation(String message) {
    System.err.println(message);
    System.err.println();
    System.err.println("Supported actions are:");
    System.err.println("  client:    Run client application");
    System.err.println("     --broker URL   URL of broker to use (required)");
    System.err.println("     --debug        Allow debug workloads (optional)");
    System.err.println("  broker:    Run broker (typically run in Cloud Run)");
    System.err.println("  workload:  Run workload server (typically run on a confidential VM)");
    return 1;
  }

  /**
   * Run the workload (in a trusted execution environment). The workload receives E2E-encrypted
   * inference requests from the broker and evaluates them.
   */
  private static void startWorkload() throws IOException, GeneralSecurityException {
    System.out.println("[INFO] Running as workload");

    var metadataClient = new MetadataClient();
    var projectMetadata = metadataClient.getProjectMetadata();
    var instanceMetadata = metadataClient.getInstanceMetadata();

    var server = new Workload(8080, 10);
    var daemon =
        new RegistrationDaemon(
            getBrokerEndpoint(projectMetadata, instanceMetadata),
            server,
            new ConfidentialSpace(),
            metadataClient);

    daemon.start();
    server.start();
  }

  /**
   * Run the broker (on Cloud Run). The broker helps the client find available workload instances
   * and forwards E2E-encrypted inference requests from the client to workload instances.
   */
  private static void startBroker() throws IOException, GeneralSecurityException {
    System.out.println("[INFO] Running as broker");

    var metadataClient = new MetadataClient();
    var projectMetadata = metadataClient.getProjectMetadata();
    var instanceMetadata = metadataClient.getInstanceMetadata();

    var broker =
        new Broker(
            getBrokerEndpoint(projectMetadata, instanceMetadata),
            Optional.ofNullable(System.getenv("PORT")).map(Integer::parseInt).orElse(8080),
            10,
            10);
    var discoveryDaemon =
        new DiscoveryDaemon(
            broker,
            GoogleCredentials.getApplicationDefault(),
            projectMetadata.get("projectId").toString());

    discoveryDaemon.start();
    broker.start();
  }

  /**
   * Run the client (on a local workstation). The client simulates a front-end app (or phone app)
   * which an end-user interacts with.
   */
  private static int runClient(List<String> args) throws Exception {
    System.out.println("[INFO] Running as client");

    //
    // Parse command line arguments.
    //
    boolean debug = false;
    String brokerUrl = null;
    for (int i = 0; i < args.size(); i++) {
      if ("--debug".equals(args.get(i))) {
        debug = true;
      } else if ("--broker".equals(args.get(i)) && i < args.size() - 1) {
        brokerUrl = args.get(i + 1);
        i++; // Skip the next argument, which is the URL.
      } else {
        return showUsageInformation("Unrecognized argument");
      }
    }

    if (brokerUrl == null) {
      return showUsageInformation("Missing broker URL");
    }

    return new Client(new Broker.Endpoint(brokerUrl), debug).run();
  }

  private static Broker.Endpoint getBrokerEndpoint(
      @NotNull GenericData projectMetadata, @NotNull GenericData instanceMetadata) {
    var zone = instanceMetadata.get("zone").toString();
    var region = zone.substring(zone.lastIndexOf('/') + 1, zone.length() - 2);
    var projectNumber = projectMetadata.get("numericProjectId").toString();
    return new Broker.Endpoint(projectNumber, region);
  }
}
