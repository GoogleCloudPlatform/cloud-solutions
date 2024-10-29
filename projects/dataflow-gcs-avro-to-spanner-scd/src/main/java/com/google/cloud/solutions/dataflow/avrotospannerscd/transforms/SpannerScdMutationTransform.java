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
package com.google.cloud.solutions.dataflow.avrotospannerscd.transforms;

import static com.google.cloud.Timestamp.parseTimestamp;

import com.google.auto.value.AutoValue;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.ClockFactory;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.ClockFactory.SystemUtcClockFactory;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.SpannerFactory;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.SpannerFactory.DatabaseClientManager;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.StructHelper;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.StructHelper.NullValues;
import com.google.cloud.spanner.KeySet;
import com.google.cloud.spanner.Options;
import com.google.cloud.spanner.ReadOnlyTransaction;
import com.google.cloud.spanner.ResultSet;
import com.google.cloud.spanner.Statement;
import com.google.cloud.spanner.Struct;
import com.google.cloud.spanner.TransactionContext;
import com.google.cloud.spanner.Value;
import com.google.common.annotations.VisibleForTesting;
import com.google.common.collect.ImmutableList;
import java.time.Clock;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import javax.annotation.Nullable;
import org.apache.beam.sdk.io.gcp.spanner.SpannerConfig;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.PDone;
import org.checkerframework.checker.nullness.qual.NonNull;

/**
 * Writes batch rows into Spanner using the defined SCD Type.
 *
 * <ul>
 *   <li>SCD Type 1: if primary key(s) exist, updates the existing row; it inserts a new row
 *       otherwise.
 *   <li>SCD Type 2: if primary key(s) exist, updates the end timestamp to the current timestamp.
 *       Note: since end timestamp is part of the primary key, it requires delete and insert to
 *       achieve this. In all cases, it inserts a new row with the new data and null end timestamp.
 *       If start timestamp column is specified, it sets it to the current timestamp when inserting.
 * </ul>
 */
@AutoValue
public abstract class SpannerScdMutationTransform
    extends PTransform<PCollection<List<Struct>>, PDone> {

  private static final String TABLE_SCHEMA_QUERY_STRING =
      "SELECT COLUMN_NAME FROM `INFORMATION_SCHEMA`.`COLUMNS` WHERE TABLE_NAME = \"%s\"";

  abstract ScdType scdType();

  abstract SpannerConfig spannerConfig();

  abstract String tableName();

  @Nullable
  abstract ImmutableList<String> primaryKeyColumnNames();

  @Nullable
  abstract String startDateColumnName();

  @Nullable
  abstract String endDateColumnName();

  abstract SpannerFactory spannerFactory();

  abstract ClockFactory clockFactory();

  public enum ScdType {
    TYPE_1,
    TYPE_2,
  }

  @AutoValue.Builder
  public abstract static class Builder {

    public abstract Builder setScdType(ScdType value);

    public abstract Builder setSpannerConfig(SpannerConfig spannerConfig);

    public abstract Builder setTableName(String value);

    public abstract Builder setPrimaryKeyColumnNames(ImmutableList<String> value);

    public abstract Builder setStartDateColumnName(String value);

    public abstract Builder setEndDateColumnName(String value);

    public abstract Builder setSpannerFactory(SpannerFactory spannerFactory);

    public abstract Builder setClockFactory(ClockFactory clock);

    public abstract SpannerScdMutationTransform build();
  }

  public static Builder builder() {
    return new AutoValue_SpannerScdMutationTransform.Builder()
        .setClockFactory(SystemUtcClockFactory.create());
  }

  /** Writes data to Spanner using the required SCD Type. Pipeline is completed. */
  @Override
  @NonNull
  public PDone expand(PCollection<List<Struct>> input) {
    String scdTypeName = scdType().toString().toLowerCase().replace("_", "");
    String stepName =
        String.format(
            "WriteScd%sToSpanner",
            scdTypeName.substring(0, 1).toUpperCase() + scdTypeName.substring(1));
    input.apply(
        stepName,
        ParDo.of(
            SpannerScdMutationDoFn.builder()
                .setScdType(scdType())
                .setSpannerConfig(spannerConfig())
                .setTableName(tableName())
                .setTableColumnNames(getTableColumnNames())
                .setPrimaryKeyColumnNames(primaryKeyColumnNames())
                .setStartDateColumnName(startDateColumnName())
                .setEndDateColumnName(endDateColumnName())
                .setSpannerFactory(spannerFactory())
                .setClockFactory(clockFactory())
                .build()));
    return PDone.in(input.getPipeline());
  }

  private ImmutableList<String> getTableColumnNames() {
    ImmutableList.Builder<String> columnNamesBuilder = ImmutableList.builder();

    try (DatabaseClientManager databaseClientManager = spannerFactory().newDatabaseClientManager();
        ReadOnlyTransaction transaction =
            databaseClientManager.newDatabaseClient().readOnlyTransaction()) {

      ResultSet results =
          transaction.executeQuery(
              Statement.of(String.format(TABLE_SCHEMA_QUERY_STRING, tableName())));
      while (results.next()) {
        Struct rowStruct = results.getCurrentRowAsStruct();
        columnNamesBuilder.add(rowStruct.getString("COLUMN_NAME"));
      }
    }
    return columnNamesBuilder.build();
  }

  @AutoValue
  @VisibleForTesting
  abstract static class SpannerScdMutationDoFn extends DoFn<List<Struct>, Void> {

    abstract ScdType scdType();

    abstract SpannerConfig spannerConfig();

    abstract String tableName();

    abstract ImmutableList<String> tableColumnNames();

    @Nullable
    abstract ImmutableList<String> primaryKeyColumnNames();

    @Nullable
    abstract String startDateColumnName();

    @Nullable
    abstract String endDateColumnName();

    abstract SpannerFactory spannerFactory();

    abstract ClockFactory clockFactory();

    private transient DatabaseClientManager databaseClientManager;
    private transient SpannerScdTypeRunner scdTypeRunner;

    @Setup
    public void setup() {
      databaseClientManager = spannerFactory().newDatabaseClientManager();
      scdTypeRunner = buildScdTypeRunner();
    }

    @Teardown
    public void teardown() {
      if (databaseClientManager != null && !databaseClientManager.isClosed()) {
        databaseClientManager.close();
      }
    }

    /**
     * Writes mutations for the current batch.
     *
     * <p>Creates all the required for mutations and buffers them as a single transaction.
     *
     * @param recordBatch
     */
    @ProcessElement
    public void writeBatchChanges(@Element List<Struct> recordBatch) {
      databaseClientManager
          .newDatabaseClient()
          .readWriteTransaction(Options.priority(spannerConfig().getRpcPriority().get()))
          .allowNestedTransaction()
          .run(
              transaction -> {
                scdTypeRunner.bufferMutations(transaction, recordBatch);
                return null;
              });
    }

    @AutoValue.Builder
    abstract static class Builder {

      public abstract Builder setScdType(ScdType value);

      public abstract Builder setSpannerConfig(SpannerConfig value);

      public abstract Builder setTableName(String value);

      public abstract Builder setTableColumnNames(ImmutableList<String> value);

      public abstract Builder setPrimaryKeyColumnNames(ImmutableList<String> value);

      public abstract Builder setStartDateColumnName(String value);

      public abstract Builder setEndDateColumnName(String value);

      public abstract Builder setSpannerFactory(SpannerFactory value);

      public abstract Builder setClockFactory(ClockFactory value);

      public abstract SpannerScdMutationDoFn build();
    }

    static SpannerScdMutationDoFn.Builder builder() {
      return new AutoValue_SpannerScdMutationTransform_SpannerScdMutationDoFn.Builder();
    }

    private SpannerScdTypeRunner buildScdTypeRunner() {
      return switch (scdType()) {
        case TYPE_1 -> new SpannerSpannerScdType1TypeRunner();
        case TYPE_2 -> new SpannerSpannerScdType2TypeRunner();
      };
    }

    interface SpannerScdTypeRunner {
      /**
       * Buffers the required mutations for the batch of records within the transaction.
       *
       * <p>Takes a transaction context and adds the required mutations for the given SCD Type for
       * all the records in the batch.
       *
       * @param transactionContext Transaction where mutations will be executed.
       * @param recordBatch Batch of records for which mutations will be created.
       */
      Void bufferMutations(TransactionContext transactionContext, List<Struct> recordBatch);
    }

    /**
     * Runs SCD Type 1 mutations to Spanner.
     *
     * <p>If primary key(s) exist, updates the existing row; it inserts a new row otherwise.
     */
    private class SpannerSpannerScdType1TypeRunner implements SpannerScdTypeRunner {
      /**
       * Buffers the mutations required for the batch of records for SCD Type 1.
       *
       * <p>Only upsert is required for each of the records.
       */
      @Nullable
      @Override
      public Void bufferMutations(TransactionContext transaction, List<Struct> recordBatch) {
        recordBatch.forEach(
            record ->
                transaction.buffer(
                    StructHelper.of(record)
                        .mutationCreator(tableName(), primaryKeyColumnNames())
                        .createUpsertMutation()));
        return null;
      }
    }

    /**
     * Runs SCD Type 2 mutations to Spanner.
     *
     * <p>If primary key(s) exist, updates the end timestamp to the current timestamp. Note: since
     * end timestamp is part of the primary key, it requires delete and insert to achieve this.
     *
     * <p>In all cases, it inserts a new row with the new data and null end timestamp. If start
     * timestamp column is specified, it sets it to the current timestamp when inserting.
     */
    private class SpannerSpannerScdType2TypeRunner implements SpannerScdTypeRunner {
      /**
       * Buffers the mutations required for the batch of records for SCD Type 2.
       *
       * <p>Update (insert and delete) of existing (old) data is required if the row exists. Insert
       * of new data is required for all cases.
       */
      @Override
      public Void bufferMutations(TransactionContext transaction, List<Struct> recordBatch) {
        var existingRows = getMatchingRecords(recordBatch, transaction);
        int recordTimeOffset = 0;
        Clock clock = clockFactory().getClock();
        for (Struct record : recordBatch) {
          var recordKey =
              StructHelper.of(record)
                  .withUpdatedFieldValue(
                      endDateColumnName(), Value.timestamp(NullValues.NULL_TIMESTAMP))
                  .keyMaker(primaryKeyColumnNames())
                  .createKey();

          // Add additional milliseconds to avoid two records from having exactly the same
          // timestamp.
          // Since end time is usually a primary key, having the same end time for two records with
          // the same otherwise primary key would result in a failure.
          var currentTimestamp =
              parseTimestamp(
                  DateTimeFormatter.ISO_INSTANT.format(
                      clock.instant().plusMillis(recordTimeOffset++)));

          if (existingRows.containsKey(recordKey)) {
            Struct existingRow = existingRows.get(recordKey);
            transaction.buffer(
                StructHelper.of(existingRow)
                    .mutationCreator(tableName(), primaryKeyColumnNames())
                    .createDeleteMutation());

            Struct updatedRecord = createUpdatedOldRecord(existingRow, currentTimestamp);
            transaction.buffer(
                StructHelper.of(updatedRecord)
                    .mutationCreator(tableName(), primaryKeyColumnNames())
                    .createInsertMutation());
          }

          Struct newRecord = createNewRecord(record, currentTimestamp);
          transaction.buffer(
              StructHelper.of(newRecord)
                  .mutationCreator(tableName(), primaryKeyColumnNames())
                  .createInsertMutation());
          existingRows.put(recordKey, newRecord);
        }
        return null;
      }

      /**
       * Gets the matching rows in the Spanner table for the given batch of records.
       *
       * @param transaction Transaction in which to operate the database read.
       * @return Map of the matching rows' Keys to the matching rows' Structs.
       */
      private Map<com.google.cloud.spanner.Key, Struct> getMatchingRecords(
          List<Struct> recordBatch, TransactionContext transaction) {
        KeySet.Builder keySetBuilder = KeySet.newBuilder();

        for (Struct record : recordBatch) {
          var recordQueryKey =
              StructHelper.of(record)
                  .withUpdatedFieldValue(
                      endDateColumnName(), Value.timestamp(NullValues.NULL_TIMESTAMP))
                  .keyMaker(primaryKeyColumnNames())
                  .createKey();
          keySetBuilder.addKey(recordQueryKey);
        }
        KeySet queryKeySet = keySetBuilder.build();

        ResultSet results = transaction.read(tableName(), queryKeySet, tableColumnNames());

        Map<com.google.cloud.spanner.Key, Struct> existingRows = new HashMap<>();
        while (results.next()) {
          Struct resultRow = results.getCurrentRowAsStruct();
          var resultKey = StructHelper.of(resultRow).keyMaker(primaryKeyColumnNames()).createKey();
          existingRows.put(resultKey, resultRow);
        }
        return existingRows;
      }

      private Struct createNewRecord(Struct record, com.google.cloud.Timestamp currentTimestamp) {
        StructHelper structHelper = StructHelper.of(record);
        if (startDateColumnName() != null) {
          structHelper =
              structHelper.withUpdatedFieldValue(
                  startDateColumnName(), Value.timestamp(currentTimestamp));
        }
        structHelper =
            structHelper.withUpdatedFieldValue(
                endDateColumnName(), Value.timestamp(NullValues.NULL_TIMESTAMP));
        return structHelper.struct();
      }

      private Struct createUpdatedOldRecord(
          Struct record, com.google.cloud.Timestamp currentTimestamp) {
        return StructHelper.of(record)
            .withUpdatedFieldValue(endDateColumnName(), Value.timestamp(currentTimestamp))
            .struct();
      }
    }
  }
}
