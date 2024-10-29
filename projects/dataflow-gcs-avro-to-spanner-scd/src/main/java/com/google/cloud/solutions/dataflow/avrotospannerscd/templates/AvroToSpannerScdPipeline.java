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
package com.google.cloud.solutions.dataflow.avrotospannerscd.templates;

import static com.google.common.base.Preconditions.checkArgument;
import static com.google.common.base.Preconditions.checkNotNull;
import static com.google.common.base.Strings.isNullOrEmpty;

import com.google.cloud.solutions.dataflow.avrotospannerscd.transforms.AvroToStructFn;
import com.google.cloud.solutions.dataflow.avrotospannerscd.transforms.MakeBatchesTransform;
import com.google.cloud.solutions.dataflow.avrotospannerscd.transforms.SpannerScdMutationTransform;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.ClockFactory;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.ClockFactory.SystemUtcClockFactory;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.SpannerFactory;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.SpannerFactory.DefaultSpannerFactory;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.SpannerOptionsFactory.DefaultSpannerOptionsFactory;
import com.google.cloud.spanner.SpannerOptions;
import com.google.common.annotations.VisibleForTesting;
import com.google.common.collect.ImmutableList;
import org.apache.beam.sdk.Pipeline;
import org.apache.beam.sdk.extensions.avro.io.AvroIO;
import org.apache.beam.sdk.io.gcp.spanner.SpannerConfig;
import org.apache.beam.sdk.options.PipelineOptionsFactory;

/**
 * Represents an Apache Beam batch pipeline to insert data in Avro format into Spanner using the
 * requested SCD Type.
 *
 * <ul>
 *   <li>SCD Type 1: Insert new rows and update existing rows based on primary key.
 *   <li>SCD Type 2: Insert all rows. Mark existing rows as inactive by setting start and end dates.
 *   <li>All other SCD Types are not currently supported.
 * </ul>
 */
public class AvroToSpannerScdPipeline {
  private final Pipeline pipeline;
  private final AvroToSpannerScdOptions pipelineOptions;
  private final SpannerConfig spannerConfig;
  private final SpannerFactory spannerFactory;

  private final ClockFactory clockFactory;

  /**
   * Initializes the pipeline.
   *
   * @param pipeline the Apache Beam pipeline
   * @param pipelineOptions the Apache Beam pipeline options to configure the pipeline
   */
  @VisibleForTesting
  AvroToSpannerScdPipeline(
      Pipeline pipeline,
      AvroToSpannerScdOptions pipelineOptions,
      SpannerConfig spannerConfig,
      SpannerFactory spannerFactory,
      ClockFactory clockFactory) {
    this.pipeline = pipeline;
    this.pipelineOptions = pipelineOptions;
    this.spannerConfig = spannerConfig;
    this.spannerFactory = spannerFactory;
    this.clockFactory = clockFactory;
  }

  /**
   * Main entry point for executing the pipeline.
   *
   * @param args The command-line arguments to the pipeline.
   */
  public static void main(String[] args) {
    AvroToSpannerScdOptions pipelineOptions =
        PipelineOptionsFactory.fromArgs(args).withValidation().as(AvroToSpannerScdOptions.class);
    validateOptions(pipelineOptions);

    SpannerConfig spannerConfig = makeSpannerConfig(pipelineOptions);

    new AvroToSpannerScdPipeline(
            Pipeline.create(pipelineOptions),
            pipelineOptions,
            spannerConfig,
            makeSpannerFactory(spannerConfig),
            SystemUtcClockFactory.create())
        .makePipeline()
        .run(pipelineOptions);
  }

  private static void validateOptions(AvroToSpannerScdOptions pipelineOptions) {
    checkArgument(
        pipelineOptions.getSpannerProjectId() == null
            || !isNullOrEmpty(pipelineOptions.getSpannerProjectId()),
        "When provided, Spanner project id must not be empty.");

    checkArgument(
        !pipelineOptions.getInstanceId().equals(""), "Spanner instance id must not be empty.");

    checkArgument(
        !pipelineOptions.getDatabaseId().equals(""), "Spanner database id must not be empty.");

    checkArgument(
        !isNullOrEmpty(pipelineOptions.getTableName()), "Spanner table name must not be empty.");

    checkArgument(
        pipelineOptions.getSpannerBatchSize() > 0,
        String.format(
            "Batch size must be greater than 0. Provided: %s.",
            pipelineOptions.getSpannerBatchSize()));

    checkArgument(
        !pipelineOptions.getPrimaryKeyColumnNames().isEmpty()
            && !pipelineOptions.getPrimaryKeyColumnNames().contains(""),
        "Spanner primary key column names must not be empty.");

    checkArgument(
        pipelineOptions.getOrderByColumnName() == null
            || !isNullOrEmpty(pipelineOptions.getOrderByColumnName()),
        "When provided, order by column name must not be empty.");

    switch (pipelineOptions.getScdType()) {
      case TYPE_1 -> {
        checkArgument(
            pipelineOptions.getStartDateColumnName() == null,
            "When using SCD Type 1, start date column name is not used.");
        checkArgument(
            pipelineOptions.getEndDateColumnName() == null,
            "When using SCD Type 1, end date column name is not used.");
      }
      case TYPE_2 -> {
        checkArgument(
            pipelineOptions.getStartDateColumnName() == null
                || !isNullOrEmpty(pipelineOptions.getStartDateColumnName()),
            "When provided, start date column name must not be empty.");
        checkNotNull(
            pipelineOptions.getEndDateColumnName(),
            "When using SCD Type 2, end date column name must be provided.");
        checkArgument(
            !isNullOrEmpty(pipelineOptions.getEndDateColumnName()),
            "When using SCD Type 2, end date column name must not be empty.");
      }
    }
  }

  private static SpannerConfig makeSpannerConfig(AvroToSpannerScdOptions pipelineOptions) {
    return SpannerConfig.create()
        .withProjectId(
            pipelineOptions.getSpannerProjectId() != null
                ? pipelineOptions.getSpannerProjectId()
                : SpannerOptions.getDefaultProjectId())
        .withInstanceId(pipelineOptions.getInstanceId())
        .withDatabaseId(pipelineOptions.getDatabaseId())
        .withRpcPriority(pipelineOptions.getSpannerPriority());
  }

  private static SpannerFactory makeSpannerFactory(SpannerConfig spannerConfig) {
    return new DefaultSpannerFactory(
        spannerConfig, new DefaultSpannerOptionsFactory(spannerConfig));
  }

  /**
   * Creates the Apache Beam pipeline that write data from Avro to Cloud Spanner using SCD Type 2.
   *
   * @return the pipeline to upsert data from GCS Avro to Cloud Spanner using the specified SCD
   *     Type.
   * @see org.apache.beam.sdk.Pipeline
   */
  @VisibleForTesting
  Pipeline makePipeline() {
    pipeline
        .apply(
            "ReadAvroRecordsAsStruct",
            AvroIO.parseGenericRecords(AvroToStructFn.create())
                .from(pipelineOptions.getInputFilePattern()))
        .apply(
            "BatchRowsIntoGroups",
            MakeBatchesTransform.builder()
                .setBatchSize(pipelineOptions.getSpannerBatchSize())
                .setPrimaryKeyColumns(
                    ImmutableList.copyOf(pipelineOptions.getPrimaryKeyColumnNames()))
                .setOrderByColumnName(pipelineOptions.getOrderByColumnName())
                .setEndDateColumnName(pipelineOptions.getEndDateColumnName())
                .setSortOrder(pipelineOptions.getSortOrder())
                .build())
        .apply(
            "WriteScdChangesToSpanner",
            SpannerScdMutationTransform.builder()
                .setScdType(pipelineOptions.getScdType())
                .setSpannerConfig(spannerConfig)
                .setTableName(pipelineOptions.getTableName())
                .setPrimaryKeyColumnNames(
                    ImmutableList.copyOf(pipelineOptions.getPrimaryKeyColumnNames()))
                .setStartDateColumnName(pipelineOptions.getStartDateColumnName())
                .setEndDateColumnName(pipelineOptions.getEndDateColumnName())
                .setSpannerFactory(spannerFactory)
                .setClockFactory(clockFactory)
                .build());

    return pipeline;
  }
}
