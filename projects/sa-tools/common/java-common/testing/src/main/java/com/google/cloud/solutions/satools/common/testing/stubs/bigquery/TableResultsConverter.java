/*
 * Copyright 2023 Google LLC
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

package com.google.cloud.solutions.satools.common.testing.stubs.bigquery;

import static com.google.common.base.Preconditions.checkNotNull;

import com.google.api.gax.paging.Page;
import com.google.cloud.bigquery.FieldValueList;
import com.google.cloud.bigquery.TableResult;
import java.util.Collection;
import java.util.List;
import java.util.function.Function;

/** Helper function to convert a collection of objects to a TableResult. */
public class TableResultsConverter<T> implements Function<Collection<T>, TableResult> {

  private final Function<T, FieldValueList> valueConverterFn;

  public TableResultsConverter(Function<T, FieldValueList> valueConverterFn) {
    this.valueConverterFn = checkNotNull(valueConverterFn);
  }

  public static <T> TableResultsConverter<T> using(Function<T, FieldValueList> valueConverterFn) {
    return new TableResultsConverter<>(valueConverterFn);
  }

  @Override
  public TableResult apply(Collection<T> source) {

    if (source == null) {
      return new TableResult(null, 0, new FieldValueListPage(List.of()));
    }

    var valueList = source.stream().map(valueConverterFn).toList();

    return new TableResult(null, valueList.size(), new FieldValueListPage(valueList));
  }

  /**
   * A simple implementation of a Page that wraps a list of FieldValueList.
   *
   * <p>This is used to create a TableResult from a list of objects.
   */
  private record FieldValueListPage(List<FieldValueList> values) implements Page<FieldValueList> {

    @Override
    public Iterable<FieldValueList> iterateAll() {
      return values;
    }

    @Override
    public Iterable<FieldValueList> getValues() {
      return values;
    }

    @Override
    public boolean hasNextPage() {
      return false;
    }

    @Override
    public String getNextPageToken() {
      return null;
    }

    @Override
    public Page<FieldValueList> getNextPage() {
      return null;
    }
  }
}
