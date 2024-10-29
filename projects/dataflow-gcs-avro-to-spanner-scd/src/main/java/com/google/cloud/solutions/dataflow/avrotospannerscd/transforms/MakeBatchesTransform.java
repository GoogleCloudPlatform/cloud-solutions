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

import com.google.auto.value.AutoValue;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.StructHelper;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.StructHelper.StructComparator;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.StructHelper.StructComparator.SortOrder;
import com.google.cloud.spanner.Struct;
import com.google.common.collect.ImmutableList;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.stream.StreamSupport;
import org.apache.beam.sdk.transforms.GroupByKey;
import org.apache.beam.sdk.transforms.GroupIntoBatches;
import org.apache.beam.sdk.transforms.MapElements;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.transforms.SimpleFunction;
import org.apache.beam.sdk.transforms.WithKeys;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.checkerframework.checker.nullness.qual.Nullable;

/** Batches individual rows (Structs) into groups of the given size. */
@AutoValue
public abstract class MakeBatchesTransform
    extends PTransform<PCollection<Struct>, PCollection<List<Struct>>> {

  abstract Integer batchSize();

  abstract ImmutableList<String> primaryKeyColumns();

  @Nullable
  abstract String orderByColumnName();

  @Nullable
  abstract SortOrder sortOrder();

  @Nullable
  abstract String endDateColumnName();

  @AutoValue.Builder
  public abstract static class Builder {

    public abstract Builder setBatchSize(Integer value);

    public abstract Builder setPrimaryKeyColumns(ImmutableList<String> value);

    public abstract Builder setOrderByColumnName(String value);

    public abstract Builder setSortOrder(SortOrder value);

    public abstract Builder setEndDateColumnName(String value);

    public abstract MakeBatchesTransform build();
  }

  public static MakeBatchesTransform.Builder builder() {
    return new AutoValue_MakeBatchesTransform.Builder();
  }

  @Override
  public PCollection<List<Struct>> expand(PCollection<Struct> input) {
    PCollection<List<Struct>> batchedRows =
        input
            .apply("AddPrimaryKey", WithKeys.of(new ExtractPrimaryKeyFn()))
            .apply("GroupByPrimaryKey", GroupByKey.create())
            .apply("GroupArbitrarilyForBatchSize", WithKeys.of(1))
            .apply("GroupIntoBatchesOfPrimaryKey", GroupIntoBatches.ofSize(batchSize()))
            .apply("RemoveArbitraryBatchKeyAndUngroup", MapElements.via(new UngroupPrimaryKeyFn()));

    return (orderByColumnName() == null)
        ? batchedRows
        : batchedRows.apply(
            "OrderByColumnName",
            MapElements.via(
                new OrderByColumnNameFn(
                    StructComparator.create(orderByColumnName(), sortOrder()))));
  }

  private final class ExtractPrimaryKeyFn extends SimpleFunction<Struct, String> {

    private final ImmutableList<String> extractPrimaryKeyColumns;

    private ExtractPrimaryKeyFn() {
      if (endDateColumnName() == null) {
        this.extractPrimaryKeyColumns = primaryKeyColumns();
        return;
      }

      ArrayList<String> primaryKeysWithoutEndDate = new ArrayList<>(primaryKeyColumns());
      primaryKeysWithoutEndDate.remove(endDateColumnName());
      this.extractPrimaryKeyColumns = ImmutableList.copyOf(primaryKeysWithoutEndDate);
    }

    @Override
    public String apply(Struct record) {
      // Use Key string because Key has a non-deterministic order.
      return StructHelper.of(record).keyMaker(extractPrimaryKeyColumns).createKeyString();
    }
  }

  private static class UngroupPrimaryKeyFn
      extends SimpleFunction<KV<Integer, Iterable<KV<String, Iterable<Struct>>>>, List<Struct>> {

    /** Ungroups data which was keyed randomly and by primary key into a single iterable. */
    public List<Struct> apply(KV<Integer, Iterable<KV<String, Iterable<Struct>>>> groupedBatch) {
      if (groupedBatch == null || groupedBatch.getValue() == null) {
        return ImmutableList.of();
      }

      return StreamSupport.stream(groupedBatch.getValue().spliterator(), true)
          .map(KV::getValue)
          .filter(Objects::nonNull)
          .map(ImmutableList::copyOf)
          .flatMap(List::stream)
          .toList();
    }
  }

  private static final class OrderByColumnNameFn
      extends SimpleFunction<List<Struct>, List<Struct>> {

    private final StructComparator comparator;

    public OrderByColumnNameFn(StructComparator comparator) {
      this.comparator = comparator;
    }

    /**
     * Orders iterable of structs by the requested orderByColumnName.
     *
     * @param inputBatch Batch to sort.
     */
    @Override
    public List<Struct> apply(List<Struct> inputBatch) {
      return inputBatch.stream().sorted(comparator).toList();
    }
  }
}
