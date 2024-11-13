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

import static com.google.cloud.solutions.dataflow.kafka2bigquery.testing.GenericJsonStringifier.convertAndAddToCollection;
import static com.google.cloud.solutions.dataflow.kafka2bigquery.testing.GenericJsonStringifier.convertJsonToObject;
import static com.google.cloud.solutions.dataflow.kafka2bigquery.testing.GenericJsonStringifier.convertMapEntriesToString;
import static com.google.cloud.solutions.dataflow.kafka2bigquery.testing.GenericJsonStringifier.convertObjectToString;
import static com.google.cloud.solutions.dataflow.kafka2bigquery.testing.GenericJsonStringifier.convertSetToString;
import static java.util.Collections.synchronizedList;
import static java.util.Collections.synchronizedMap;
import static java.util.Collections.synchronizedSet;

import com.google.api.services.bigquery.model.Dataset;
import com.google.api.services.bigquery.model.DatasetReference;
import com.google.api.services.bigquery.model.Table;
import com.google.api.services.bigquery.model.TableReference;
import com.google.api.services.bigquery.model.TableRow;
import com.google.common.flogger.GoogleLogger;
import java.io.Serializable;
import java.util.LinkedHashMap;
import java.util.LinkedList;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import org.apache.beam.sdk.io.gcp.bigquery.BigQueryServices.DatasetService;
import org.apache.beam.sdk.io.gcp.bigquery.ErrorContainer;
import org.apache.beam.sdk.io.gcp.bigquery.InsertRetryPolicy;
import org.apache.beam.sdk.values.FailsafeValueInSingleWindow;
import org.apache.beam.sdk.values.ValueInSingleWindow;

/** Records all the calls made against the DatasetService for inspection. */
public class FakeDatasetService implements DatasetService, Serializable {

  private static final GoogleLogger logger = GoogleLogger.forEnclosingClass();

  // All measurable fields are static as DoFn will create different instances per call.

  public static Map<String, String> existingTables;
  public static Set<String> emptyTables;
  public static Map<String, String> existingDatasets;
  public static List<String> getTableCalls;
  public static List<String> createTableCalls;
  public static List<String> deleteTableCalls;
  public static List<String> createDatasetCalls;
  public static List<String> deleteDatasetCalls;
  public static Map<String, List<String>> insertedRows;

  public static void init(
      Map<TableReference, Table> existingTables,
      Set<TableReference> emptyTables,
      Map<DatasetReference, Dataset> existingDatasets) {

    // LinkedList structures allow fast addition at end of the list
    // in O(1) time, required for fast insertion performance in test-stub.
    FakeDatasetService.existingTables = synchronizedMap(convertMapEntriesToString(existingTables));
    FakeDatasetService.emptyTables = synchronizedSet(convertSetToString(emptyTables));
    FakeDatasetService.existingDatasets =
        synchronizedMap(convertMapEntriesToString(existingDatasets));
    getTableCalls = synchronizedList(new LinkedList<>());
    createTableCalls = synchronizedList(new LinkedList<>());
    deleteTableCalls = synchronizedList(new LinkedList<>());
    createDatasetCalls = synchronizedList(new LinkedList<>());
    deleteDatasetCalls = synchronizedList(new LinkedList<>());
    insertedRows = synchronizedMap(new LinkedHashMap<>());
  }

  @Override
  public Table getTable(TableReference tableRef) {
    var strTableRef = convertAndAddToCollection(tableRef, getTableCalls);
    return (existingTables != null)
        ? convertJsonToObject(existingTables.get(strTableRef), Table.class)
        : null;
  }

  @Override
  public Table getTable(TableReference tableRef, List<String> selectedFields) {
    return getTable(tableRef);
  }

  @Override
  public Table getTable(
      TableReference tableRef, List<String> selectedFields, TableMetadataView view) {
    return getTable(tableRef);
  }

  @Override
  public void createTable(Table table) {
    convertAndAddToCollection(table, createTableCalls);
  }

  @Override
  public void deleteTable(TableReference tableRef) {
    convertAndAddToCollection(tableRef, deleteTableCalls);
  }

  @Override
  public boolean isTableEmpty(TableReference tableRef) {
    var strTableRef = convertObjectToString(tableRef);
    return (emptyTables != null && emptyTables.contains(strTableRef));
  }

  @Override
  public Dataset getDataset(String projectId, String datasetId) {
    var datasetRef = new DatasetReference().setProjectId(projectId).setDatasetId(datasetId);
    var strDatasetRef = convertObjectToString(datasetRef);
    return (existingDatasets != null)
        ? convertJsonToObject(existingDatasets.get(strDatasetRef), Dataset.class)
        : null;
  }

  @Override
  public void createDataset(
      String projectId,
      String datasetId,
      String location,
      String description,
      Long defaultTableExpirationMs) {
    var dataset =
        new Dataset()
            .setLocation(location)
            .setDatasetReference(
                new DatasetReference().setProjectId(projectId).setDatasetId(datasetId))
            .setDescription(description)
            .setDefaultTableExpirationMs(defaultTableExpirationMs);
    convertAndAddToCollection(dataset, createDatasetCalls);
  }

  @Override
  public void deleteDataset(String projectId, String datasetId) {
    convertAndAddToCollection(
        new DatasetReference().setProjectId(projectId).setDatasetId(datasetId), deleteDatasetCalls);
  }

  @Override
  public <T> long insertAll(
      TableReference ref,
      List<FailsafeValueInSingleWindow<TableRow, TableRow>> rowList,
      List<String> insertIdList,
      InsertRetryPolicy retryPolicy,
      List<ValueInSingleWindow<T>> failedInserts,
      ErrorContainer<T> errorContainer,
      boolean skipInvalidRows,
      boolean ignoreUnknownValues,
      boolean ignoreInsertIds,
      List<ValueInSingleWindow<TableRow>> successfulRows) {

    logger.atInfo().log(
        "table [%s:%s.%s] rowCount = %s",
        ref.getProjectId(), ref.getDatasetId(), ref.getTableId(), rowList.size());

    var strTableRef = convertObjectToString(ref);

    var newRows =
        rowList.stream()
            .map(FailsafeValueInSingleWindow::getValue)
            .map(GenericJsonStringifier::convertObjectToString)
            .filter(Objects::nonNull)
            .toList();

    //noinspection SynchronizeOnNonFinalField
    synchronized (insertedRows) {
      List<String> rows = insertedRows.get(strTableRef);

      if (rows == null) {
        rows = synchronizedList(new LinkedList<>());
      }
      rows.addAll(newRows);
      insertedRows.put(strTableRef, rows);
    }
    return 1;
  }

  @Override
  public Table patchTableDescription(TableReference tableReference, String tableDescription) {
    return null;
  }

  @Override
  public void close() {}
}
