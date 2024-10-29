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

import static com.google.common.truth.Truth.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.google.api.gax.retrying.RetrySettings;
import com.google.cloud.Timestamp;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.ClockFactory;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.SpannerFactory;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.StructHelper.NullValues;
import com.google.cloud.spanner.DatabaseClient;
import com.google.cloud.spanner.Key;
import com.google.cloud.spanner.Mutation;
import com.google.cloud.spanner.Options.RpcPriority;
import com.google.cloud.spanner.ReadOnlyTransaction;
import com.google.cloud.spanner.ResultSet;
import com.google.cloud.spanner.Struct;
import com.google.cloud.spanner.TransactionContext;
import com.google.cloud.spanner.TransactionRunner;
import com.google.common.collect.ImmutableList;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import org.apache.beam.sdk.io.gcp.spanner.SpannerConfig;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.transforms.Create;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;

public final class SpannerScdMutationTransformTest {
  @Rule public final transient TestPipeline pipeline = TestPipeline.create();
  private final ClockFactory frozenClockFactory = new FrozenClockFactory();
  private SpannerConfig spannerConfig;

  @Before
  public void setUpSpanner() {
    TestMutationRegistry.init();
    spannerConfig =
        SpannerConfig.create()
            .withProjectId("test-project")
            .withInstanceId("test-instance")
            .withDatabaseId("test-database")
            .withRpcPriority(RpcPriority.HIGH)
            .withExecuteStreamingSqlRetrySettings(RetrySettings.newBuilder().build());
  }

  @Test
  public void processElement_scdType1_createsInsertOrUpdateMutation() {
    List<Struct> input =
        List.of(
            Struct.newBuilder().set("id").to(1).set("name").to("Nito").build(),
            Struct.newBuilder().set("id").to(2).set("name").to("Beam").build());
    TestSpannerFactory spannerFactory =
        new TestSpannerFactory(ImmutableList.of("id", "name"), ImmutableList.of());

    pipeline
        .apply(Create.of(ImmutableList.of(input)))
        .apply(
            SpannerScdMutationTransform.builder()
                .setScdType(SpannerScdMutationTransform.ScdType.TYPE_1)
                .setSpannerConfig(spannerConfig)
                .setTableName("tableName")
                .setPrimaryKeyColumnNames(ImmutableList.of("id"))
                .setStartDateColumnName(null)
                .setEndDateColumnName(null)
                .setSpannerFactory(spannerFactory)
                .setClockFactory(frozenClockFactory)
                .build());
    pipeline.run().waitUntilFinish();

    assertThat(TestMutationRegistry.getMutations())
        .containsExactly(
            Mutation.newInsertOrUpdateBuilder("tableName")
                .set("id")
                .to(1)
                .set("name")
                .to("Nito")
                .build(),
            Mutation.newInsertOrUpdateBuilder("tableName")
                .set("id")
                .to(2)
                .set("name")
                .to("Beam")
                .build());
  }

  @Test
  public void processElement_scdType2_withEndDate_withNoRowMatch_createsInserts() {
    List<Struct> input =
        ImmutableList.of(
            Struct.newBuilder().set("id").to(1).set("name").to("Nito").build(),
            Struct.newBuilder().set("id").to(2).set("name").to("Beam").build());
    TestSpannerFactory spannerFactory =
        new TestSpannerFactory(ImmutableList.of("id", "name", "end_date"), ImmutableList.of());

    pipeline
        .apply(Create.of(ImmutableList.of(input)))
        .apply(
            SpannerScdMutationTransform.builder()
                .setScdType(SpannerScdMutationTransform.ScdType.TYPE_2)
                .setSpannerConfig(spannerConfig)
                .setTableName("tableName")
                .setPrimaryKeyColumnNames(ImmutableList.of("id", "end_date"))
                .setStartDateColumnName(null)
                .setEndDateColumnName("end_date")
                .setSpannerFactory(spannerFactory)
                .setClockFactory(frozenClockFactory)
                .build());
    pipeline.run().waitUntilFinish();

    assertThat(TestMutationRegistry.getMutations())
        .containsExactly(
            Mutation.newInsertBuilder("tableName")
                .set("id")
                .to(1)
                .set("name")
                .to("Nito")
                .set("end_date")
                .to(NullValues.NULL_TIMESTAMP)
                .build(),
            Mutation.newInsertBuilder("tableName")
                .set("id")
                .to(2)
                .set("name")
                .to("Beam")
                .set("end_date")
                .to(NullValues.NULL_TIMESTAMP)
                .build());
  }

  @Test
  public void processElement_scdType2_withStartAndEndDate_withNoRowMatch_createsInserts() {
    List<Struct> input =
        ImmutableList.of(
            Struct.newBuilder().set("id").to(1).set("name").to("Nito").build(),
            Struct.newBuilder().set("id").to(2).set("name").to("Beam").build());
    TestSpannerFactory spannerFactory =
        new TestSpannerFactory(
            ImmutableList.of("id", "name", "start_date", "end_date"), ImmutableList.of());

    pipeline
        .apply(Create.of(ImmutableList.of(input)))
        .apply(
            SpannerScdMutationTransform.builder()
                .setScdType(SpannerScdMutationTransform.ScdType.TYPE_2)
                .setSpannerConfig(spannerConfig)
                .setTableName("tableName")
                .setPrimaryKeyColumnNames(ImmutableList.of("id", "end_date"))
                .setStartDateColumnName("start_date")
                .setEndDateColumnName("end_date")
                .setSpannerFactory(spannerFactory)
                .setClockFactory(frozenClockFactory)
                .build());
    pipeline.run().waitUntilFinish();

    assertThat(TestMutationRegistry.getMutations())
        .containsExactly(
            Mutation.newInsertBuilder("tableName")
                .set("id")
                .to(1)
                .set("name")
                .to("Nito")
                .set("start_date")
                .to(Timestamp.ofTimeMicroseconds(7000000))
                .set("end_date")
                .to(NullValues.NULL_TIMESTAMP)
                .build(),
            Mutation.newInsertBuilder("tableName")
                .set("id")
                .to(2)
                .set("name")
                .to("Beam")
                .set("start_date")
                .to(Timestamp.ofTimeMicroseconds(7001000))
                .set("end_date")
                .to(NullValues.NULL_TIMESTAMP)
                .build());
  }

  @Test
  public void processElement_scdType2_withEndDate_withRowMatch_createsUpdates() {
    List<Struct> input =
        ImmutableList.of(
            Struct.newBuilder().set("id").to(1).set("name").to("NewName").build(),
            Struct.newBuilder().set("id").to(2).set("name").to("Beam").build());
    ImmutableList<Struct> existingRows =
        ImmutableList.of(
            Struct.newBuilder()
                .set("id")
                .to(1)
                .set("name")
                .to("Nito")
                .set("end_date")
                .to(NullValues.NULL_TIMESTAMP)
                .build());
    TestSpannerFactory spannerFactory =
        new TestSpannerFactory(ImmutableList.of("id", "name", "end_date"), existingRows);

    pipeline
        .apply(Create.of(ImmutableList.of(input)))
        .apply(
            SpannerScdMutationTransform.builder()
                .setScdType(SpannerScdMutationTransform.ScdType.TYPE_2)
                .setSpannerConfig(spannerConfig)
                .setTableName("tableName")
                .setPrimaryKeyColumnNames(ImmutableList.of("id", "end_date"))
                .setStartDateColumnName(null)
                .setEndDateColumnName("end_date")
                .setSpannerFactory(spannerFactory)
                .setClockFactory(frozenClockFactory)
                .build());
    pipeline.run().waitUntilFinish();

    assertThat(TestMutationRegistry.getMutations())
        .containsExactly(
            // Updates via delete and 2x insert.
            Mutation.delete(
                "tableName", Key.newBuilder().append(1).append(NullValues.NULL_TIMESTAMP).build()),
            Mutation.newInsertBuilder("tableName")
                .set("id")
                .to(1)
                .set("name")
                .to("Nito")
                .set("end_date")
                .to(Timestamp.ofTimeMicroseconds(7000000))
                .build(),
            Mutation.newInsertBuilder("tableName")
                .set("id")
                .to(1)
                .set("name")
                .to("NewName")
                .set("end_date")
                .to(NullValues.NULL_TIMESTAMP)
                .build(),
            // Inserts non-existing row.
            Mutation.newInsertBuilder("tableName")
                .set("id")
                .to(2)
                .set("name")
                .to("Beam")
                .set("end_date")
                .to(NullValues.NULL_TIMESTAMP)
                .build());
  }

  @Test
  public void processElement_scdType2_withStartAndEndDate_withRowMatch_createsUpdates() {
    List<Struct> input =
        ImmutableList.of(
            Struct.newBuilder().set("id").to(1).set("name").to("NewName").build(),
            Struct.newBuilder().set("id").to(2).set("name").to("Beam").build());
    ImmutableList<Struct> existingRows =
        ImmutableList.of(
            Struct.newBuilder()
                .set("id")
                .to(1)
                .set("name")
                .to("Nito")
                .set("start_date")
                .to(Timestamp.ofTimeMicroseconds(123))
                .set("end_date")
                .to(NullValues.NULL_TIMESTAMP)
                .build());
    TestSpannerFactory spannerFactory =
        new TestSpannerFactory(
            ImmutableList.of("id", "name", "start_date", "end_date"), existingRows);

    pipeline
        .apply(Create.of(ImmutableList.of(input)))
        .apply(
            SpannerScdMutationTransform.builder()
                .setScdType(SpannerScdMutationTransform.ScdType.TYPE_2)
                .setSpannerConfig(spannerConfig)
                .setTableName("tableName")
                .setPrimaryKeyColumnNames(ImmutableList.of("id", "end_date"))
                .setStartDateColumnName("start_date")
                .setEndDateColumnName("end_date")
                .setSpannerFactory(spannerFactory)
                .setClockFactory(frozenClockFactory)
                .build());
    pipeline.run().waitUntilFinish();

    assertThat(TestMutationRegistry.getMutations())
        .containsExactly(
            // Updates via delete and 2x insert.
            Mutation.delete(
                "tableName", Key.newBuilder().append(1).append(NullValues.NULL_TIMESTAMP).build()),
            Mutation.newInsertBuilder("tableName")
                .set("id")
                .to(1)
                .set("name")
                .to("Nito")
                .set("start_date")
                .to(Timestamp.ofTimeMicroseconds(123))
                .set("end_date")
                .to(Timestamp.ofTimeMicroseconds(7000000))
                .build(),
            Mutation.newInsertBuilder("tableName")
                .set("id")
                .to(1)
                .set("name")
                .to("NewName")
                .set("start_date")
                .to(Timestamp.ofTimeMicroseconds(7000000))
                .set("end_date")
                .to(NullValues.NULL_TIMESTAMP)
                .build(),
            // Inserts non-existing row.
            Mutation.newInsertBuilder("tableName")
                .set("id")
                .to(2)
                .set("name")
                .to("Beam")
                .set("start_date")
                .to(Timestamp.ofTimeMicroseconds(7001000))
                .set("end_date")
                .to(NullValues.NULL_TIMESTAMP)
                .build());
  }

  @Test
  public void processElement_scdType2_withNoRowMatch_handlesSequentialUpdates() {
    List<Struct> input =
        ImmutableList.of(
            Struct.newBuilder().set("id").to(1).set("name").to("NewName").build(),
            Struct.newBuilder().set("id").to(1).set("name").to("OtherNewName").build());
    TestSpannerFactory spannerFactory =
        new TestSpannerFactory(
            ImmutableList.of("id", "name", "start_date", "end_date"), ImmutableList.of());

    pipeline
        .apply(Create.of(ImmutableList.of(input)))
        .apply(
            SpannerScdMutationTransform.builder()
                .setScdType(SpannerScdMutationTransform.ScdType.TYPE_2)
                .setSpannerConfig(spannerConfig)
                .setTableName("tableName")
                .setPrimaryKeyColumnNames(ImmutableList.of("id", "end_date"))
                .setStartDateColumnName("start_date")
                .setEndDateColumnName("end_date")
                .setSpannerFactory(spannerFactory)
                .setClockFactory(frozenClockFactory)
                .build());
    pipeline.run().waitUntilFinish();

    assertThat(TestMutationRegistry.getMutations())
        .containsExactly(
            // Insert row as there are no matches.
            Mutation.newInsertBuilder("tableName")
                .set("id")
                .to(1)
                .set("name")
                .to("NewName")
                .set("start_date")
                .to(Timestamp.ofTimeMicroseconds(7000000))
                .set("end_date")
                .to(NullValues.NULL_TIMESTAMP)
                .build(),
            // Updates row via delete and 2x inserts.
            Mutation.delete(
                "tableName", Key.newBuilder().append(1).append(NullValues.NULL_TIMESTAMP).build()),
            Mutation.newInsertBuilder("tableName")
                .set("id")
                .to(1)
                .set("name")
                .to("NewName")
                .set("start_date")
                .to(Timestamp.ofTimeMicroseconds(7000000))
                .set("end_date")
                .to(Timestamp.ofTimeMicroseconds(7001000))
                .build(),
            Mutation.newInsertBuilder("tableName")
                .set("id")
                .to(1)
                .set("name")
                .to("OtherNewName")
                .set("start_date")
                .to(Timestamp.ofTimeMicroseconds(7001000))
                .set("end_date")
                .to(NullValues.NULL_TIMESTAMP)
                .build());
  }

  @Test
  public void processElement_scdType2_withRowMatch_handlesSequentialUpdates() {
    ImmutableList<Struct> existingRows =
        ImmutableList.of(
            Struct.newBuilder()
                .set("id")
                .to(1)
                .set("name")
                .to("Nito")
                .set("start_date")
                .to(Timestamp.ofTimeMicroseconds(123))
                .set("end_date")
                .to(NullValues.NULL_TIMESTAMP)
                .build());
    List<Struct> input =
        ImmutableList.of(
            Struct.newBuilder().set("id").to(1).set("name").to("NewName").build(),
            Struct.newBuilder().set("id").to(1).set("name").to("OtherNewName").build());
    TestSpannerFactory spannerFactory =
        new TestSpannerFactory(
            ImmutableList.of("id", "name", "start_date", "end_date"), existingRows);

    pipeline
        .apply(Create.of(ImmutableList.of(input)))
        .apply(
            SpannerScdMutationTransform.builder()
                .setScdType(SpannerScdMutationTransform.ScdType.TYPE_2)
                .setSpannerConfig(spannerConfig)
                .setTableName("tableName")
                .setPrimaryKeyColumnNames(ImmutableList.of("id", "end_date"))
                .setStartDateColumnName("start_date")
                .setEndDateColumnName("end_date")
                .setSpannerFactory(spannerFactory)
                .setClockFactory(frozenClockFactory)
                .build());
    pipeline.run().waitUntilFinish();

    assertThat(TestMutationRegistry.getMutations())
        .containsExactly(
            // Updates via delete and 2x inserts.
            Mutation.delete(
                "tableName", Key.newBuilder().append(1).append(NullValues.NULL_TIMESTAMP).build()),
            Mutation.newInsertBuilder("tableName")
                .set("id")
                .to(1)
                .set("name")
                .to("Nito")
                .set("start_date")
                .to(Timestamp.ofTimeMicroseconds(123))
                .set("end_date")
                .to(Timestamp.ofTimeMicroseconds(7000000))
                .build(),
            Mutation.newInsertBuilder("tableName")
                .set("id")
                .to(1)
                .set("name")
                .to("NewName")
                .set("start_date")
                .to(Timestamp.ofTimeMicroseconds(7000000))
                .set("end_date")
                .to(NullValues.NULL_TIMESTAMP)
                .build(),
            // Updates again via delete and 2x inserts.
            Mutation.delete(
                "tableName", Key.newBuilder().append(1).append(NullValues.NULL_TIMESTAMP).build()),
            Mutation.newInsertBuilder("tableName")
                .set("id")
                .to(1)
                .set("name")
                .to("NewName")
                .set("start_date")
                .to(Timestamp.ofTimeMicroseconds(7000000))
                .set("end_date")
                .to(Timestamp.ofTimeMicroseconds(7001000))
                .build(),
            Mutation.newInsertBuilder("tableName")
                .set("id")
                .to(1)
                .set("name")
                .to("OtherNewName")
                .set("start_date")
                .to(Timestamp.ofTimeMicroseconds(7001000))
                .set("end_date")
                .to(NullValues.NULL_TIMESTAMP)
                .build());
  }

  static final class FrozenClockFactory implements ClockFactory {
    public Clock getClock() {
      return Clock.fixed(Instant.EPOCH.plusSeconds(7), ZoneId.of("UTC"));
    }
  }

  static final class TestMutationRegistry {
    static ArrayList<Mutation> mutations;

    static void init() {
      mutations = new ArrayList<Mutation>();
    }

    static void add(Mutation mutation) throws Exception {
      if (mutations == null) {
        throw new Exception("TestMutationRegistry was not initialized.");
      }
      mutations.add(mutation);
    }

    static ArrayList<Mutation> getMutations() {
      return mutations;
    }
  }

  static final class TestSpannerFactory implements SpannerFactory {

    private final ImmutableList<String> tableColumnNames;
    private final ImmutableList<Struct> existingRowResults;

    TestSpannerFactory(
        ImmutableList<String> tableColumnNames, ImmutableList<Struct> existingRowResults) {
      this.tableColumnNames = tableColumnNames;
      this.existingRowResults = existingRowResults;
    }

    public DatabaseClientManager newDatabaseClientManager() {
      return new TestDatabaseClientManager(this.tableColumnNames, this.existingRowResults);
    }

    public static final class TestDatabaseClientManager implements DatabaseClientManager {
      private boolean isClosed = false;
      private final ImmutableList<Struct> existingRowResults;
      private final ImmutableList<String> tableColumnNames;

      TestDatabaseClientManager(
          ImmutableList<String> tableColumnNames, ImmutableList<Struct> existingRowResults) {
        this.tableColumnNames = tableColumnNames;
        this.existingRowResults = existingRowResults;
      }

      public DatabaseClient newDatabaseClient() {
        return buildDatabaseClientMock();
      }

      private DatabaseClient buildDatabaseClientMock() {
        ReadOnlyTransaction readOnlyTransaction = buildReadOnlyTransactionMock();
        TransactionRunner transactionRunnerMock = buildTransactionRunnerMock();

        DatabaseClient databaseClientMock = mock(DatabaseClient.class);
        when(databaseClientMock.readWriteTransaction()).thenReturn(transactionRunnerMock);
        when(databaseClientMock.readWriteTransaction(any())).thenReturn(transactionRunnerMock);
        when(databaseClientMock.readOnlyTransaction()).thenReturn(readOnlyTransaction);
        return databaseClientMock;
      }

      private ReadOnlyTransaction buildReadOnlyTransactionMock() {
        ReadOnlyTransaction readOnlyTransaction = mock(ReadOnlyTransaction.class);
        ResultSet resultSet =
            buildResultSetMock(
                tableColumnNames.stream()
                    .map(
                        columnName -> Struct.newBuilder().set("COLUMN_NAME").to(columnName).build())
                    .collect(ImmutableList.toImmutableList()));
        when(readOnlyTransaction.executeQuery(any())).thenReturn(resultSet);
        return readOnlyTransaction;
      }

      private TransactionRunner buildTransactionRunnerMock() {
        ResultSet resultSetMock = buildResultSetMock(existingRowResults);
        TransactionContext transactionContextMock = buildTransactionContextMock(resultSetMock);
        TransactionRunner transactionRunnerMock = mock(TransactionRunner.class);
        when(transactionRunnerMock.allowNestedTransaction()).thenReturn(transactionRunnerMock);
        when(transactionRunnerMock.run(any()))
            .thenAnswer(
                invocation -> {
                  TransactionRunner.TransactionCallable<Void> callable = invocation.getArgument(0);
                  return callable.run(transactionContextMock);
                });
        return transactionRunnerMock;
      }

      private ResultSet buildResultSetMock(ImmutableList<Struct> results) {
        ResultSet resultSetMock = mock(ResultSet.class);
        Iterator<Struct> resultsIterator = results.stream().iterator();
        when(resultSetMock.next()).thenAnswer(input -> resultsIterator.hasNext());
        when(resultSetMock.getCurrentRowAsStruct()).thenAnswer(input -> resultsIterator.next());
        return resultSetMock;
      }

      private TransactionContext buildTransactionContextMock(ResultSet resultSet) {
        TransactionContext transactionContextMock = mock(TransactionContext.class);

        when(transactionContextMock.read(any(), any(), any())).thenReturn(resultSet);

        doAnswer(
                (invocation) -> {
                  Mutation mutation = invocation.getArgument(0);
                  TestMutationRegistry.add(mutation);
                  return null;
                })
            .when(transactionContextMock)
            .buffer(any(Mutation.class));

        doAnswer(
                (invocation) -> {
                  Iterable<Mutation> mutations = invocation.getArgument(0);
                  for (Mutation mutation : mutations) {
                    TestMutationRegistry.add(mutation);
                  }
                  return null;
                })
            .when(transactionContextMock)
            .buffer(any(Iterable.class));

        return transactionContextMock;
      }

      @Override
      public void close() {
        isClosed = true;
      }

      @Override
      public boolean isClosed() {
        return isClosed;
      }
    }
  }
}
