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

package com.google.cloud.solutions.dataflow.kafka2bigquery.testing;

import java.io.Serializable;
import org.apache.beam.sdk.io.gcp.bigquery.BigQueryOptions;
import org.apache.beam.sdk.io.gcp.bigquery.BigQueryServices;

public class FakeBigQueryServices implements BigQueryServices, Serializable {

  private FakeDatasetService datasetService;

  public FakeBigQueryServices(FakeDatasetService datasetService) {
    this.datasetService = datasetService;
  }

  @Override
  public JobService getJobService(BigQueryOptions bqOptions) {
    throw new UnsupportedOperationException("JobService not available");
  }

  @Override
  public DatasetService getDatasetService(BigQueryOptions bqOptions) {
    return datasetService;
  }

  @Override
  public WriteStreamService getWriteStreamService(BigQueryOptions bqOptions) {
    throw new UnsupportedOperationException("WriteStreamService not available");
  }

  @Override
  public StorageClient getStorageClient(BigQueryOptions bqOptions) {
    throw new UnsupportedOperationException("StorageClient not available");
  }
}
