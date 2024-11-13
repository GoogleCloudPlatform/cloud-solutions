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

import com.google.api.services.bigquery.model.TableRow;
import com.google.auto.value.AutoValue;
import com.google.common.collect.ImmutableList;
import com.google.protobuf.ByteString;
import java.io.Serializable;
import java.time.Instant;
import java.time.format.DateTimeFormatter;
import java.util.Base64;
import java.util.List;
import org.apache.beam.sdk.transforms.SerializableFunction;
import org.checkerframework.checker.nullness.qual.NonNull;
import org.checkerframework.checker.nullness.qual.Nullable;

/** Model to represent errors in parsing Proto message from Kafka. */
@AutoValue
public abstract class KafkaSchemaError implements Serializable {

  public abstract String topic();

  public abstract Instant timestamp();

  @Nullable
  public abstract ImmutableList<Integer> unknownFieldIds();

  @Nullable
  public abstract ByteString rawKey();

  @Nullable
  public abstract ByteString rawMessage();

  public static Builder builder() {
    return new AutoValue_KafkaSchemaError.Builder();
  }

  public static KafkaSchemaErrorToTableRowFn bigqueryFormatFunction() {
    return new KafkaSchemaErrorToTableRowFn();
  }

  @AutoValue.Builder
  public abstract static class Builder {

    public abstract Builder topic(String newTopic);

    public abstract Builder timestamp(Instant newTimestamp);

    /**
     * Sets the timestamp instant (in ISO-8601 format) by parsing through {@link
     * DateTimeFormatter#ISO_INSTANT}
     *
     * @param timestamp in String format for Instant.
     */
    public Builder timestamp(String timestamp) {
      return timestamp(Instant.parse(timestamp));
    }

    public abstract Builder unknownFieldIds(ImmutableList<Integer> newUnknownFieldIds);

    public Builder unknownFieldIds(List<Integer> newUnknownFieldIds) {
      return unknownFieldIds(ImmutableList.copyOf(newUnknownFieldIds));
    }

    public abstract Builder rawKey(ByteString newRawValue);

    public Builder rawKey(byte[] newRawKey) {
      return rawKey(ByteString.copyFrom(newRawKey));
    }

    public abstract Builder rawMessage(ByteString newRawValue);

    public Builder rawMessage(byte[] newRawValue) {
      return rawMessage(ByteString.copyFrom(newRawValue));
    }

    public abstract KafkaSchemaError build();
  }

  /** Converts the POJO to BigQuery TableRow for writing to BigQuery. */
  @NonNull
  public TableRow toTableRow() {
    var row = new TableRow().set("topic", topic()).set("timestamp", timestamp().toString());

    if (unknownFieldIds() != null && !unknownFieldIds().isEmpty()) {
      row.set("unknown_field_ids", unknownFieldIds());
    }

    var base64encoder = Base64.getEncoder();

    if (rawKey() != null) {
      row.set("raw_key", base64encoder.encodeToString(rawKey().toByteArray()));
    }

    if (rawMessage() != null) {
      row.set("raw_message", base64encoder.encodeToString(rawMessage().toByteArray()));
    }

    return row;
  }

  /** Formatting function for BigQueryIO. */
  public static class KafkaSchemaErrorToTableRowFn
      implements SerializableFunction<KafkaSchemaError, TableRow> {

    @Override
    public TableRow apply(KafkaSchemaError input) {
      if (input == null) {
        return null;
      }

      return input.toTableRow();
    }
  }
}
