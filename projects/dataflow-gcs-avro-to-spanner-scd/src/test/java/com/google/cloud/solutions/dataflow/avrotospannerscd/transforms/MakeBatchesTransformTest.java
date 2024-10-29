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

import static com.google.cloud.solutions.dataflow.avrotospannerscd.testing.TestSampleCreator.createSimpleStruct;
import static com.google.cloud.solutions.dataflow.avrotospannerscd.testing.TestSampleCreator.createStructSamples;
import static com.google.cloud.solutions.dataflow.avrotospannerscd.testing.TestSampleCreator.createStructWithField;
import static com.google.common.truth.Truth.assertThat;

import com.google.cloud.Timestamp;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.StructHelper;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.StructHelper.NullValues;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.StructHelper.StructComparator.SortOrder;
import com.google.cloud.spanner.Struct;
import com.google.cloud.spanner.Value;
import com.google.common.collect.ImmutableList;
import java.util.Collections;
import java.util.List;
import java.util.stream.StreamSupport;
import org.apache.beam.sdk.testing.PAssert;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.transforms.MapElements;
import org.apache.beam.sdk.transforms.SimpleFunction;
import org.apache.beam.sdk.values.PCollection;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.junit.runners.Parameterized;
import org.junit.runners.Parameterized.Parameters;

public final class MakeBatchesTransformTest {

  @RunWith(Parameterized.class)
  public static final class BatchCreationParameterizedTests {

    @Rule public final transient TestPipeline pipeline = TestPipeline.create();

    private final int batchSize;
    private final Iterable<Struct> inputRecords;
    private final Iterable<Integer> expectedBatchSizes;

    public BatchCreationParameterizedTests(
        // Suppressing not used: testCaseName is used by Parameterized, even when not used here.
        @SuppressWarnings("unused") String testCaseName,
        int batchSize,
        Iterable<Struct> inputRecords,
        Iterable<Integer> expectedBatchSizes) {
      this.batchSize = batchSize;
      this.inputRecords = inputRecords;
      this.expectedBatchSizes = expectedBatchSizes;
    }

    @Test
    public void expand_createsBatches() {
      // Arrange.
      var outputBatchSize =
          pipeline
              .apply(Create.of(inputRecords))

              // Act.
              .apply(
                  MakeBatchesTransform.builder()
                      .setBatchSize(batchSize)
                      .setPrimaryKeyColumns(ImmutableList.of("id"))
                      .build())
              // Assert.
              .apply(MapElements.via(new MapToListSizeFn()));

      PAssert.that(outputBatchSize).containsInAnyOrder(expectedBatchSizes);
      pipeline.run().waitUntilFinish();
    }

    // @Test
    public void expand_createsBatchesAndIgnoresEndDate() {
      // Arrange.
      PCollection<Integer> outputBatchSize =
          pipeline
              .apply(Create.of(inputRecords))

              // Act.
              .apply(
                  MakeBatchesTransform.builder()
                      .setBatchSize(batchSize)
                      .setPrimaryKeyColumns(ImmutableList.of("id", "end_date"))
                      .setEndDateColumnName("end_date")
                      .build())

              // Assert.
              .apply(MapElements.via(new MapToListSizeFn()));

      PAssert.that(outputBatchSize).containsInAnyOrder(expectedBatchSizes);
      pipeline.run().waitUntilFinish();
    }

    /** Maps a PCollection of Iterables to a PCollection of its size. */
    private static class MapToListSizeFn extends SimpleFunction<Iterable<Struct>, Integer> {
      @Override
      public Integer apply(Iterable<Struct> inputBatch) {
        return ImmutableList.copyOf(inputBatch).size();
      }
    }

    /** Creates test parameters. */
    @Parameters(name = "{0}")
    public static ImmutableList<Object[]> testingParameters() {
      return ImmutableList.<Object[]>builder()
          .add(
              new Object[] {
                /* testCaseName= */ "One Batch (bathSize > inputRecords.size)",
                /* batchSize= */ 10,
                /* inputRecords= */ createStructSamples(5),
                /* expectedBatchSizes= */ ImmutableList.of(5)
              })
          .add(
              new Object[] {
                /* testCaseName= */ "Multiple Batches (inputRecords.size > batchSize)",
                /* batchSize= */ 10,
                /* inputRecords= */ createStructSamples(25),
                /* expectedBatchSizes= */ ImmutableList.of(10, 10, 5)
              })
          .add(
              new Object[] {
                /* testCaseName= */ "Batches primary keys together even if batch >= than batchSize",
                /* batchSize= */ 5,
                /* inputRecords= */ ImmutableList.builder()
                    .addAll(Collections.nCopies(7, createSimpleStruct()))
                    // Must be a multiple of 5 minus 1 or the results may be flaky.
                    // The reason for this is that there is no sorting before the group by happens.
                    // As such, the group with 7 keys may fall in any group. If the groups are not
                    // perfect multiple of 5, the group may be 7+4 or 7 + whatever extra (modulo) is
                    // on the last group when this gets grouped with the last one. By making it a
                    // multiple of 5 (minus one to account for the repeated row), there will always
                    // be
                    // X groups of 5, and one group of 4+7 for the repeated key.
                    .addAll(createStructSamples(14))
                    .build(),
                /* expectedBatchSizes= */ ImmutableList.of(11, 5, 5)
              })
          .build();
    }
  }

  @RunWith(JUnit4.class)
  public static final class BatchCreationTests {

    @Rule public final transient TestPipeline pipeline = TestPipeline.create();

    @Test
    public void expand_batchesPrimaryKeysTogether() {
      var batchSize = 2;
      var primaryKeys = ImmutableList.of("id");
      var repeatedRow = createSimpleStruct();
      var repeatedKey = StructHelper.of(repeatedRow).keyMaker(primaryKeys).createKeyString();
      PCollection<Struct> input =
          pipeline.apply(
              Create.of(
                  new ImmutableList.Builder<Struct>()
                      .addAll(Collections.nCopies(4, repeatedRow))
                      .addAll(createStructSamples(15))
                      .build()));

      PCollection<List<Struct>> output =
          input.apply(
              MakeBatchesTransform.builder()
                  .setBatchSize(batchSize)
                  .setPrimaryKeyColumns(primaryKeys)
                  .build());

      PAssert.that(output)
          .satisfies(
              collection -> {
                assertThat(
                        StreamSupport.stream(collection.spliterator(), false)
                            .map(ImmutableList::copyOf)
                            .filter(batch -> batch.size() == 5)
                            .flatMap(List::stream)
                            .filter(
                                record ->
                                    StructHelper.of(record)
                                        .keyMaker(primaryKeys)
                                        .createKeyString()
                                        .equals(repeatedKey))
                            .count())
                    .isEqualTo(4);
                return null;
              });
      pipeline.run().waitUntilFinish();
    }
  }

  @RunWith(Parameterized.class)
  public static final class BatchSortingTests {

    @Rule public final transient TestPipeline pipeline = TestPipeline.create();

    private final SortOrder sortOrder;

    private final List<Struct> inputRecords;
    private final List<Struct> expectedRecordsInOrder;

    public BatchSortingTests(
        // Suppressing not used: testCaseName is used by Parameterized, even when not used here.
        @SuppressWarnings("unused") String testCaseName,
        SortOrder sortOrder,
        List<Struct> inputRecords,
        List<Struct> expectedRecordsInOrder) {
      this.sortOrder = sortOrder;
      this.inputRecords = inputRecords;
      this.expectedRecordsInOrder = expectedRecordsInOrder;
    }

    /** Records must be in expected output order. */
    @Test
    public void expand_sortsBatches() {
      var output =
          pipeline
              .apply(Create.of(inputRecords))
              .apply(
                  MakeBatchesTransform.builder()
                      .setBatchSize(3)
                      .setPrimaryKeyColumns(ImmutableList.of("testField"))
                      .setOrderByColumnName("testField")
                      .setSortOrder(sortOrder)
                      .build());

      PAssert.thatSingleton(output).isEqualTo(expectedRecordsInOrder);
      pipeline.run().waitUntilFinish();
    }

    /** Creates test parameters. */
    @Parameters(name = "{0}")
    public static ImmutableList<Object[]> testingParameters() {
      var outOfOrderRecords =
          List.of( // Records are out of order (2, 1, 3) using ASC order.
              createStructWithField(Value.timestamp(Timestamp.ofTimeMicroseconds(10))),
              createStructWithField(Value.timestamp(NullValues.NULL_TIMESTAMP)),
              createStructWithField(Value.timestamp(Timestamp.ofTimeMicroseconds(1000))));

      return ImmutableList.<Object[]>builder()
          .add(
              new Object[] {
                /* testCaseName= */ "Default",
                /* sortOrder= */ null,
                /* inputRecords */ outOfOrderRecords,
                /* expectedOutput= */ List.of(
                    createStructWithField(Value.timestamp(NullValues.NULL_TIMESTAMP)),
                    createStructWithField(Value.timestamp(Timestamp.ofTimeMicroseconds(10))),
                    createStructWithField(Value.timestamp(Timestamp.ofTimeMicroseconds(1000)))),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "ASC",
                /* sortOrder= */ SortOrder.ASC,
                /* inputRecords */ outOfOrderRecords,
                /* indexOrder= */ List.of(
                    createStructWithField(Value.timestamp(NullValues.NULL_TIMESTAMP)),
                    createStructWithField(Value.timestamp(Timestamp.ofTimeMicroseconds(10))),
                    createStructWithField(Value.timestamp(Timestamp.ofTimeMicroseconds(1000)))),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "DESC",
                /* sortOrder= */ SortOrder.DESC,
                /* inputRecords */ outOfOrderRecords,
                /* indexOrder= */ List.of(
                    createStructWithField(Value.timestamp(Timestamp.ofTimeMicroseconds(1000))),
                    createStructWithField(Value.timestamp(Timestamp.ofTimeMicroseconds(10))),
                    createStructWithField(Value.timestamp(NullValues.NULL_TIMESTAMP))),
              })
          .build();
    }
  }
}
