/*
 * Copyright (C) 2024 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may not
 * use this file except in compliance with the License. You may obtain a copy of
 * the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations under
 * the License.
 */

package com.google.cloud.solutions.dataflow.avrotospannerscd.utils;

import com.google.cloud.spanner.DatabaseClient;
import com.google.cloud.spanner.DatabaseId;
import com.google.cloud.spanner.Spanner;
import java.io.Serializable;
import org.apache.beam.sdk.io.gcp.spanner.SpannerConfig;

/** Creates Spanner and DatabaseClient instances to access Spanner data. */
public interface SpannerFactory extends Serializable {

  DatabaseClientManager newDatabaseClientManager();

  /** Spanner DatabaseClient instance to access Spanner data. */
  interface DatabaseClientManager extends AutoCloseable {

    DatabaseClient newDatabaseClient();

    void close();

    boolean isClosed();
  }

  final class DefaultSpannerFactory implements SpannerFactory {
    private final SpannerConfig spannerConfig;
    private final SpannerOptionsFactory spannerOptionsFactory;

    public DefaultSpannerFactory(
        SpannerConfig spannerConfig, SpannerOptionsFactory spannerOptionsFactory) {
      this.spannerConfig = spannerConfig;
      this.spannerOptionsFactory = spannerOptionsFactory;
    }

    @Override
    public DatabaseClientManager newDatabaseClientManager() {
      return new DefaultDatabaseClientManager(createSpannerService(), spannerConfig);
    }

    private Spanner createSpannerService() {
      // This property sets the default timeout between 2 response packets in the client library.
      System.setProperty("com.google.cloud.spanner.watchdogTimeoutSeconds", "7200");
      return spannerOptionsFactory.getSpannerOptions().getService();
    }

    /** Spanner DatabaseClient instance to access Spanner data. */
    public static final class DefaultDatabaseClientManager implements DatabaseClientManager {

      private final transient Spanner spanner;
      private final SpannerConfig spannerConfig;

      /**
       * Initializes Spanner database client.
       *
       * @param spanner Spanner service to use for database management.
       * @param spannerConfig Spanner Configuration to use to create DatabaseClient.
       */
      DefaultDatabaseClientManager(Spanner spanner, SpannerConfig spannerConfig) {
        this.spanner = spanner;
        this.spannerConfig = spannerConfig;
      }

      /**
       * Gets or creates a Spanner Database client.
       *
       * <p>The client is configured using SpannerConfig variables and with additional retry logic.
       *
       * @return DatabaseClient to connect to Spanner.
       */
      @Override
      public DatabaseClient newDatabaseClient() {
        return spanner.getDatabaseClient(
            DatabaseId.of(
                spannerConfig.getProjectId().get(),
                spannerConfig.getInstanceId().get(),
                spannerConfig.getDatabaseId().get()));
      }

      /** Closes Spanner client. */
      @Override
      public void close() {
        spanner.close();
      }

      /** Returns whether the Spanner client is closed. */
      @Override
      public boolean isClosed() {
        return spanner.isClosed();
      }
    }
  }
}
