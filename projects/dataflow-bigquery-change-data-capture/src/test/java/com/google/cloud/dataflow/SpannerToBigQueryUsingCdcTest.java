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

import static org.junit.Assert.assertEquals;

import com.google.api.services.bigquery.model.TableReference;
import com.google.cloud.Timestamp;
import com.google.cloud.bigquery.BigQuery;
import com.google.cloud.bigquery.BigQueryOptions;
import com.google.cloud.bigquery.QueryJobConfiguration;
import com.google.cloud.bigquery.TableResult;
import com.google.cloud.dataflow.SpannerToBigQueryUsingCdc.Options;
import com.google.cloud.dataflow.model.Order;
import com.google.cloud.dataflow.model.Order.Status;
import com.google.cloud.dataflow.model.OrderMutation;
import com.google.cloud.dataflow.model.OrderMutation.OrderMutationCoder;
import com.google.cloud.spanner.DatabaseClient;
import com.google.cloud.spanner.DatabaseId;
import com.google.cloud.spanner.Key;
import com.google.cloud.spanner.Mutation;
import com.google.cloud.spanner.Options.RpcPriority;
import com.google.cloud.spanner.ResultSet;
import com.google.cloud.spanner.Spanner;
import com.google.cloud.spanner.SpannerOptions;
import com.google.cloud.spanner.Statement;
import com.google.cloud.spanner.TransactionRunner;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;
import java.util.stream.Collectors;
import org.apache.beam.sdk.Pipeline;
import org.apache.beam.sdk.io.gcp.bigquery.BigQueryIO;
import org.apache.beam.sdk.io.gcp.bigquery.BigQueryIO.Write;
import org.apache.beam.sdk.io.gcp.bigquery.BigQueryIO.Write.CreateDisposition;
import org.apache.beam.sdk.io.gcp.bigquery.BigQueryIO.Write.WriteDisposition;
import org.apache.beam.sdk.io.gcp.bigquery.WriteResult;
import org.apache.beam.sdk.io.gcp.spanner.SpannerConfig;
import org.apache.beam.sdk.io.gcp.spanner.SpannerIO;
import org.apache.beam.sdk.io.gcp.spanner.changestreams.model.DataChangeRecord;
import org.apache.beam.sdk.options.PipelineOptionsFactory;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.values.PCollection;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;

/** Integration test for the pipeline. */
public class SpannerToBigQueryUsingCdcTest {

  private Options options;
  private Spanner spanner;
  private DatabaseClient dbClient;

  /** Setup method to initialize the Spanner client. */
  @Before
  public void setUp() {
    options = PipelineOptionsFactory.as(Options.class);

    options.setSpannerProjectId(envValue("SPANNER_PROJECT_ID"));
    options.setSpannerInstanceId(envValue("SPANNER_INSTANCE"));
    options.setSpannerDatabaseId(envValue("SPANNER_DATABASE"));
    options.setSpannerOrdersStreamId(envValue("ORDERS_CHANGE_STREAM"));

    options.setBigQueryProjectId(envValue("BQ_PROJECT_ID"));
    options.setBigQueryDataset(envValue("BQ_DATASET"));

    // Workaround for JDK 17+. To be fixed in later Beam releases.
    options.setJdkAddOpenModules(Collections.singletonList("java.base/java.lang=ALL-UNNAMED"));

    spanner = SpannerOptions.newBuilder().build().getService();
    DatabaseId spannerDb =
        DatabaseId.of(
            options.getSpannerProjectId(),
            options.getSpannerInstanceId(),
            options.getSpannerDatabaseId());
    dbClient = spanner.getDatabaseClient(spannerDb);
  }

  private static String envValue(String envVariable) {
    String result = System.getenv(envVariable);
    if (result == null) {
      throw new IllegalStateException("Environment variable '" + envVariable + "' is not set.");
    }
    return result;
  }

  /** Clean up method to gracefully close the Spanner client. */
  @After
  public void tearDown() {
    if (spanner != null) {
      spanner.close();
    }
  }

  @Test
  public void testCdcIngestion() throws InterruptedException {

    long startOrderNumber = getNextOrderNumber();
    AtomicLong nextOrderNumber = new AtomicLong(startOrderNumber);

    String[] descriptions = new String[] {"Phone", "Tablet", "Desktop", "Monitor"};
    Map<Long, Order> newOrders =
        Arrays.stream(descriptions)
            .collect(
                Collectors.toMap(
                    description -> nextOrderNumber.get(),
                    description -> {
                      Order order =
                          new Order(nextOrderNumber.getAndIncrement(), Status.NEW, description);
                      return order;
                    }));

    Timestamp startTime;
    startTime = Timestamp.now();

    createNewOrders(newOrders);

    Thread.sleep(3000);
    Long orderIdToDelete = newOrders.keySet().iterator().next();
    Order toDelete = newOrders.remove(orderIdToDelete);
    deleteOrder(toDelete);

    Thread.sleep(2000);

    Order orderToUpdate = newOrders.values().iterator().next();
    orderToUpdate.setStatus(Status.PROCESSED);
    orderToUpdate.setDescription(orderToUpdate.getDescription() + " - processed");

    Timestamp endTime = updateOrder(orderToUpdate);
    endTime = Timestamp.ofTimeSecondsAndNanos(endTime.getSeconds() + 60, 0);

    Pipeline p = Pipeline.create(options);

    SpannerConfig spannerConfig =
        SpannerConfig.create()
            .withProjectId(options.getSpannerProjectId())
            .withInstanceId(options.getSpannerInstanceId())
            .withDatabaseId(options.getSpannerDatabaseId());

    PCollection<DataChangeRecord> dataChangeRecords =
        p.apply(
            "Read Change Stream",
            SpannerIO.readChangeStream()
                .withSpannerConfig(spannerConfig)
                .withChangeStreamName(options.getSpannerOrdersStreamId())
                .withRpcPriority(RpcPriority.MEDIUM)
                .withInclusiveStartAt(startTime)
                .withInclusiveEndAt(endTime));

    TableReference ordersTableReference = new TableReference();
    ordersTableReference.setProjectId(options.getBigQueryProjectId());
    ordersTableReference.setTableId(options.getBigQueryOrdersTableName());
    ordersTableReference.setDatasetId(options.getBigQueryDataset());

    WriteResult writeResult =
        dataChangeRecords
            .apply("To OrderMutations", ParDo.of(new DataChangeRecordToOrderMutation()))
            .setCoder(new OrderMutationCoder())
            .apply(
                "Save To BigQuery",
                BigQueryIO.<OrderMutation>write()
                    .to(ordersTableReference)
                    .withCreateDisposition(CreateDisposition.CREATE_NEVER)
                    .withWriteDisposition(WriteDisposition.WRITE_APPEND)
                    .withMethod(Write.Method.STORAGE_API_AT_LEAST_ONCE)
                    .withFormatFunction(new OrderMutationToTableRow())
                    .withRowMutationInformationFn(
                        orderMutation -> orderMutation.getMutationInformation()));

    writeResult
        .getFailedStorageApiInserts()
        .apply("Validate no records failed", new BigQueryFailedInsertProcessor());

    p.run();

    Map<Long, Order> ordersInBigQuery =
        readOrdersFromBigQuery(options, startOrderNumber, nextOrderNumber.get());

    assertEquals("Orders", newOrders, ordersInBigQuery);
  }

  private Map<Long, Order> readOrdersFromBigQuery(
      Options options, long startOrderId, long endOrderId) throws InterruptedException {
    BigQuery bigquery = BigQueryOptions.getDefaultInstance().getService();

    String query =
        String.format(
            "SELECT * FROM %s.%s.%s WHERE order_id BETWEEN %d and %d",
            options.getBigQueryProjectId(),
            options.getBigQueryDataset(),
            options.getBigQueryOrdersTableName(),
            startOrderId,
            endOrderId);
    QueryJobConfiguration queryConfig = QueryJobConfiguration.newBuilder(query).build();

    // Execute the query.
    TableResult queryResult = bigquery.query(queryConfig);

    Map<Long, Order> result = new HashMap<>();
    // Print the results.
    queryResult
        .iterateAll()
        .forEach(
            row -> {
              long orderId = row.get("order_id").getLongValue();
              String status = row.get("status").getStringValue();
              String description = row.get("description").getStringValue();

              result.put(orderId, new Order(orderId, Status.valueOf(status), description));
            });

    return result;
  }

  private long getNextOrderNumber() {
    try (ResultSet resultSet =
        dbClient
            .singleUse() // Execute a single read or query against Cloud Spanner.
            .executeQuery(Statement.of("SELECT MAX(order_id) max_order_id FROM orders"))) {
      resultSet.next();
      if (resultSet.isNull("max_order_id")) {
        return 1;
      } else {
        return resultSet.getLong("max_order_id") + 1;
      }
    }
  }

  private Timestamp createNewOrders(Map<Long, Order> orders) {
    List<Mutation> mutations = new ArrayList<>();
    for (Order order : orders.values()) {
      mutations.add(
          Mutation.newInsertBuilder(options.getSpannerTableName())
              .set("order_id")
              .to(order.getId())
              .set("status")
              .to(order.getStatus().name())
              .set("description")
              .to(order.getDescription())
              .build());
    }

    return dbClient.write(mutations);
  }

  private Timestamp deleteOrder(Order order) {
    List<Mutation> mutations = new ArrayList<>();
    mutations.add(Mutation.delete(options.getSpannerTableName(), Key.of(order.getId())));

    return dbClient.write(mutations);
  }

  private Timestamp updateOrder(Order order) {
    TransactionRunner transactionRunner = dbClient.readWriteTransaction();
    transactionRunner.run(
        transaction -> {
          String sql =
              "UPDATE "
                  + options.getSpannerTableName()
                  + " SET status = '"
                  + order.getStatus().name()
                  + "',"
                  // We are not concerned about SQL injection in this demo code.
                  + " description = '"
                  + order.getDescription()
                  + "'"
                  + " WHERE order_id = "
                  + order.getId();
          transaction.executeUpdate(Statement.of(sql));
          return null;
        });
    return transactionRunner.getCommitTimestamp();
  }
}
