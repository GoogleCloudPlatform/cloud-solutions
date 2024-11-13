/*
 * Copyright 2024 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package com.google.cloud.solutions.dataflow.kafka2bigquery;

import static com.google.common.truth.Truth.assertThat;

import com.google.api.services.bigquery.model.TableRow;
import com.google.cloud.solutions.dataflow.kafka2bigquery.KafkaSchemaError.KafkaSchemaErrorToTableRowFn;
import java.util.List;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public final class KafkaSchemaErrorTest {

  @Test
  public void apply_null_null() {
    var testFn = new KafkaSchemaErrorToTableRowFn();

    assertThat(testFn.apply(null)).isNull();
  }

  @Test
  public void apply_timestamp_valid() {
    var testFn = new KafkaSchemaErrorToTableRowFn();
    assertThat(
            testFn.apply(
                KafkaSchemaError.builder()
                    .timestamp("2024-11-10T02:00:00.000Z")
                    .topic("testTopic")
                    .rawKey(new byte[] {1, 2})
                    .rawMessage(new byte[] {3, 4})
                    .unknownFieldIds(List.of(5, 6))
                    .build()))
        .isEqualTo(
            new TableRow()
                .set("topic", "testTopic")
                .set("timestamp", "2024-11-10T02:00:00Z")
                .set("unknown_field_ids", List.of(5, 6))
                .set("raw_key", "AQI=")
                .set("raw_message", "AwQ="));
  }

  @Test
  public void apply_nullUnknownFields_valid() {
    var testFn = new KafkaSchemaErrorToTableRowFn();
    assertThat(
            testFn.apply(
                KafkaSchemaError.builder()
                    .timestamp("2024-11-10T02:00:00.000Z")
                    .topic("testTopic")
                    .rawKey(new byte[] {1, 2})
                    .rawMessage(new byte[] {3, 4})
                    .build()))
        .isEqualTo(
            new TableRow()
                .set("topic", "testTopic")
                .set("timestamp", "2024-11-10T02:00:00Z")
                .set("raw_key", "AQI=")
                .set("raw_message", "AwQ="));
  }

  @Test
  public void apply_nullRawKeys_valid() {
    var testFn = new KafkaSchemaErrorToTableRowFn();
    assertThat(
            testFn.apply(
                KafkaSchemaError.builder()
                    .timestamp("2024-11-10T02:00:00.000Z")
                    .topic("testTopic")
                    .rawMessage(new byte[] {3, 4})
                    .unknownFieldIds(List.of(5, 6))
                    .build()))
        .isEqualTo(
            new TableRow()
                .set("topic", "testTopic")
                .set("timestamp", "2024-11-10T02:00:00Z")
                .set("unknown_field_ids", List.of(5, 6))
                .set("raw_message", "AwQ="));
  }

  @Test
  public void apply_nullRawMessage_valid() {
    var testFn = new KafkaSchemaErrorToTableRowFn();
    assertThat(
            testFn.apply(
                KafkaSchemaError.builder()
                    .timestamp("2024-11-10T02:00:00.000Z")
                    .topic("testTopic")
                    .rawKey(new byte[] {1, 2})
                    .unknownFieldIds(List.of(5, 6))
                    .build()))
        .isEqualTo(
            new TableRow()
                .set("topic", "testTopic")
                .set("timestamp", "2024-11-10T02:00:00Z")
                .set("unknown_field_ids", List.of(5, 6))
                .set("raw_key", "AQI="));
  }
}
