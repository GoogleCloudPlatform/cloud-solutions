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

package com.google.cloud.dataflow;

import org.apache.beam.sdk.io.gcp.bigquery.BigQueryStorageApiInsertError;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.PDone;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * PTransform to process BigQuery inserts errors.
 *
 * <p>Current implementation is a demo one; it just emits a log message for every error. Not to be
 * used in production large scale pipelines.
 */
public class BigQueryFailedInsertProcessor
    extends PTransform<PCollection<BigQueryStorageApiInsertError>, PDone> {

  private static final long serialVersionUID = 1L;

  private static final Logger LOG = LoggerFactory.getLogger(BigQueryFailedInsertProcessor.class);

  @Override
  public PDone expand(PCollection<BigQueryStorageApiInsertError> input) {
    input.apply("Process BQ Errors", ParDo.of(new BigQueryFailedInsertProcessorFn()));
    return PDone.in(input.getPipeline());
  }

  static class BigQueryFailedInsertProcessorFn extends DoFn<BigQueryStorageApiInsertError, Void> {

    private static final long serialVersionUID = 1L;

    @ProcessElement
    public void process(@Element BigQueryStorageApiInsertError error) {
      LOG.error("Failed to insert record: " + error);
    }
  }
}
