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

import static com.google.common.base.Preconditions.checkNotNull;

import com.google.api.services.bigquery.model.TableRow;
import com.google.protobuf.Message;
import org.apache.beam.sdk.io.gcp.bigquery.BigQueryIO;
import org.apache.beam.sdk.io.gcp.bigquery.BigQueryIO.Write;

/**
 * Factory to build {@link org.apache.beam.sdk.io.gcp.bigquery.BigQueryIO.Write} objects based on
 * type.
 */
public class DefaultBigQueryWriterFactory implements BigQueryWriterFactory {

  @Override
  public <T> Write<T> get(Class<T> collectionClass) {
    checkNotNull(collectionClass, "PCollection Class can't be null");

    if (TableRow.class == collectionClass) {
      return (BigQueryIO.Write<T>) BigQueryIO.writeTableRows();
    } else if (Message.class.isAssignableFrom(collectionClass)) {
      return (BigQueryIO.Write<T>) BigQueryIO.writeProtos((Class<Message>) collectionClass);
    }

    return BigQueryIO.write();
  }
}
