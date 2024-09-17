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

import com.google.api.gax.paging.Page;
import com.google.cloud.Policy;
import com.google.cloud.bigquery.BigQuery;
import com.google.cloud.bigquery.BigQueryOptions;
import com.google.cloud.bigquery.Connection;
import com.google.cloud.bigquery.ConnectionSettings;
import com.google.cloud.bigquery.Dataset;
import com.google.cloud.bigquery.DatasetId;
import com.google.cloud.bigquery.DatasetInfo;
import com.google.cloud.bigquery.InsertAllRequest;
import com.google.cloud.bigquery.InsertAllResponse;
import com.google.cloud.bigquery.Job;
import com.google.cloud.bigquery.JobException;
import com.google.cloud.bigquery.JobId;
import com.google.cloud.bigquery.JobInfo;
import com.google.cloud.bigquery.Model;
import com.google.cloud.bigquery.ModelId;
import com.google.cloud.bigquery.ModelInfo;
import com.google.cloud.bigquery.QueryJobConfiguration;
import com.google.cloud.bigquery.QueryResponse;
import com.google.cloud.bigquery.Routine;
import com.google.cloud.bigquery.RoutineId;
import com.google.cloud.bigquery.RoutineInfo;
import com.google.cloud.bigquery.Schema;
import com.google.cloud.bigquery.Table;
import com.google.cloud.bigquery.TableDataWriteChannel;
import com.google.cloud.bigquery.TableId;
import com.google.cloud.bigquery.TableInfo;
import com.google.cloud.bigquery.TableResult;
import com.google.cloud.bigquery.WriteChannelConfiguration;
import com.google.cloud.solutions.satools.common.testing.stubs.PatchyStub;
import java.util.List;
import org.checkerframework.checker.nullness.qual.NonNull;

/** Fake BigQuery Client. */
public class PatchyBigQueryStub implements BigQuery {

  private final PatchyStub patchyStub;

  public PatchyBigQueryStub(PatchyStub patchyStub) {
    this.patchyStub = patchyStub;
  }

  @Override
  public TableResult query(QueryJobConfiguration configuration, JobOption... options) {
    return patchyStub
        .findCallable(
            QueryJobConfiguration.class,
            TableResult.class,
            () -> {
              throw new UnsupportedOperationException("bigquery query callable not found");
            })
        .call(configuration);
  }

  @Override
  public TableResult query(QueryJobConfiguration configuration, JobId jobId, JobOption... options)
      throws InterruptedException, JobException {
    throw new UnsupportedOperationException();
  }

  @Override
  public Dataset create(DatasetInfo datasetInfo, DatasetOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Table create(TableInfo tableInfo, TableOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Routine create(RoutineInfo routineInfo, RoutineOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Job create(JobInfo jobInfo, JobOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Connection createConnection(@NonNull ConnectionSettings connectionSettings) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Connection createConnection() {
    throw new UnsupportedOperationException();
  }

  @Override
  public Dataset getDataset(String datasetId, DatasetOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Dataset getDataset(DatasetId datasetId, DatasetOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Page<Dataset> listDatasets(DatasetListOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Page<Dataset> listDatasets(String projectId, DatasetListOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public boolean delete(String datasetId, DatasetDeleteOption... options) {
    return false;
  }

  @Override
  public boolean delete(DatasetId datasetId, DatasetDeleteOption... options) {
    return false;
  }

  @Override
  public boolean delete(String datasetId, String tableId) {
    return false;
  }

  @Override
  public boolean delete(TableId tableId) {
    return false;
  }

  @Override
  public boolean delete(ModelId modelId) {
    return false;
  }

  @Override
  public boolean delete(RoutineId routineId) {
    return false;
  }

  @Override
  public boolean delete(JobId jobId) {
    return false;
  }

  @Override
  public Dataset update(DatasetInfo datasetInfo, DatasetOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Table update(TableInfo tableInfo, TableOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Model update(ModelInfo modelInfo, ModelOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Routine update(RoutineInfo routineInfo, RoutineOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Table getTable(String datasetId, String tableId, TableOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Table getTable(TableId tableId, TableOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Model getModel(String datasetId, String modelId, ModelOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Model getModel(ModelId tableId, ModelOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Routine getRoutine(String datasetId, String routineId, RoutineOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Routine getRoutine(RoutineId routineId, RoutineOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Page<Routine> listRoutines(String datasetId, RoutineListOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Page<Routine> listRoutines(DatasetId datasetId, RoutineListOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Page<Table> listTables(String datasetId, TableListOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Page<Table> listTables(DatasetId datasetId, TableListOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Page<Model> listModels(String datasetId, ModelListOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Page<Model> listModels(DatasetId datasetId, ModelListOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public List<String> listPartitions(TableId tableId) {
    throw new UnsupportedOperationException();
  }

  @Override
  public InsertAllResponse insertAll(InsertAllRequest request) {
    throw new UnsupportedOperationException();
  }

  @Override
  public TableResult listTableData(
      String datasetId, String tableId, TableDataListOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public TableResult listTableData(TableId tableId, TableDataListOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public TableResult listTableData(
      String datasetId, String tableId, Schema schema, TableDataListOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public TableResult listTableData(TableId tableId, Schema schema, TableDataListOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Job getJob(String jobId, JobOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Job getJob(JobId jobId, JobOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Page<Job> listJobs(JobListOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public boolean cancel(String jobId) {
    return false;
  }

  @Override
  public boolean cancel(JobId jobId) {
    return false;
  }

  @Override
  public QueryResponse getQueryResults(JobId jobId, QueryResultsOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public TableDataWriteChannel writer(WriteChannelConfiguration writeChannelConfiguration) {
    throw new UnsupportedOperationException();
  }

  @Override
  public TableDataWriteChannel writer(
      JobId jobId, WriteChannelConfiguration writeChannelConfiguration) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Policy getIamPolicy(TableId tableId, IAMOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public Policy setIamPolicy(TableId tableId, Policy policy, IAMOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public List<String> testIamPermissions(
      TableId table, List<String> permissions, IAMOption... options) {
    throw new UnsupportedOperationException();
  }

  @Override
  public BigQueryOptions getOptions() {
    throw new UnsupportedOperationException();
  }
}
