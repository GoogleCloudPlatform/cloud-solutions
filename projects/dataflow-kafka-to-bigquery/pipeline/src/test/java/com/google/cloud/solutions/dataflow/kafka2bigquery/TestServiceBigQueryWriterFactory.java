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

import org.apache.beam.sdk.io.gcp.bigquery.BigQueryIO.Write;
import org.apache.beam.sdk.io.gcp.bigquery.BigQueryServices;

/** Sets the provided BigQueryServices for enabling tests on the BigQuery writer. */
public final class TestServiceBigQueryWriterFactory implements BigQueryWriterFactory {

  private final BigQueryServices bigQueryServices;
  private final DefaultBigQueryWriterFactory defaultBigQueryWriterFactory;

  public TestServiceBigQueryWriterFactory(BigQueryServices bigQueryServices) {
    this.bigQueryServices = bigQueryServices;
    this.defaultBigQueryWriterFactory = new DefaultBigQueryWriterFactory();
  }

  public static TestServiceBigQueryWriterFactory create(BigQueryServices bigQueryServices) {
    return new TestServiceBigQueryWriterFactory(bigQueryServices);
  }

  @Override
  public <T> Write<T> get(Class<T> collectionClass) {
    return defaultBigQueryWriterFactory.get(collectionClass).withTestServices(bigQueryServices);
  }
}
