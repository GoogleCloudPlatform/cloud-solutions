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

import static com.google.common.truth.Truth.assertThat;

import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.SpannerFactory.DatabaseClientManager;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.SpannerFactory.DefaultSpannerFactory;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.SpannerOptionsFactory.DefaultSpannerOptionsFactory;
import com.google.cloud.spanner.DatabaseClient;
import org.apache.beam.sdk.io.gcp.spanner.SpannerConfig;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class SpannerFactoryTest {

  private SpannerConfig spannerConfig;
  private SpannerOptionsFactory spannerOptionsFactory;

  @Before
  public void setUp() {
    spannerConfig =
        SpannerConfig.create()
            .withProjectId("project-id")
            .withInstanceId("instance-id")
            .withDatabaseId("database-id");
    spannerOptionsFactory = new DefaultSpannerOptionsFactory(spannerConfig);
  }

  @Test
  public void testGetDatabaseClient() {
    DatabaseClientManager databaseClientManager =
        new DefaultSpannerFactory(spannerConfig, spannerOptionsFactory).newDatabaseClientManager();

    DatabaseClient databaseClient = databaseClientManager.newDatabaseClient();

    assertThat(databaseClient).isInstanceOf(DatabaseClient.class);
  }

  @Test
  public void testIsClosed_beforeClosing() {
    DatabaseClientManager databaseClientManager =
        new DefaultSpannerFactory(spannerConfig, spannerOptionsFactory).newDatabaseClientManager();

    assertThat(databaseClientManager.isClosed()).isFalse();
  }

  @Test
  public void testIsClosed_afterClosing() {
    DatabaseClientManager databaseClientManager =
        new DefaultSpannerFactory(spannerConfig, spannerOptionsFactory).newDatabaseClientManager();

    databaseClientManager.close();

    assertThat(databaseClientManager.isClosed()).isTrue();
  }
}
