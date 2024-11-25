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

import static java.util.stream.Collectors.toList;

import com.google.cloud.Timestamp;
import com.google.cloud.solutions.dataflow.avrotospannerscd.transforms.SpannerScdMutationTransform;
import com.google.cloud.solutions.dataflow.avrotospannerscd.transforms.SpannerScdMutationTransform.ScdType;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.ClockFactory;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.ClockFactory.SystemUtcClockFactory;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.SpannerFactory;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.SpannerFactory.DefaultSpannerFactory;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.SpannerOptionsFactory;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.StructHelper.NullValues;
import com.google.cloud.spanner.DatabaseAdminClient;
import com.google.cloud.spanner.DatabaseClient;
import com.google.cloud.spanner.DatabaseId;
import com.google.cloud.spanner.InstanceAdminClient;
import com.google.cloud.spanner.InstanceConfigId;
import com.google.cloud.spanner.InstanceId;
import com.google.cloud.spanner.InstanceInfo;
import com.google.cloud.spanner.KeySet;
import com.google.cloud.spanner.Mutation;
import com.google.cloud.spanner.ResultSet;
import com.google.cloud.spanner.Spanner;
import com.google.cloud.spanner.SpannerOptions;
import com.google.cloud.spanner.Struct;
import com.google.common.collect.ImmutableList;
import com.google.common.io.Resources;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.ExecutionException;
import org.apache.beam.it.gcp.spanner.matchers.SpannerAsserts;
import org.apache.beam.sdk.io.gcp.spanner.SpannerConfig;
import org.apache.beam.sdk.options.PipelineOptionsFactory;
import org.apache.beam.sdk.options.ValueProvider;
import org.apache.beam.sdk.testing.TestPipeline;
import org.junit.After;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.testcontainers.containers.SpannerEmulatorContainer;
import org.testcontainers.utility.DockerImageName;

@RunWith(JUnit4.class)
public final class AvroToSpannerScdPipelineIT {

  @Rule public final transient TestPipeline pipeline = TestPipeline.create();
  private static final String PROJECT_ID = "test-project";
  private static final String SPANNER_INSTANCE_ID = "test-instance";
  private static final String SPANNER_DATABASE_ID = "test-database";
  private static final String SPANNER_TABLE_NAME = "employees";

  private static final String RESOURCE_DIR = "AvroToSpannerScdPipelineITTest";

  @Rule public SpannerEmulatorContainer spannerEmulator;
  String spannerHost;

  Spanner spanner;

  @Before
  public void setUp() throws ExecutionException, InterruptedException {
    createSpannerEmulator();
    createSpannerInstance();
    // Database to be created on the test via createSpannerDDL.
  }

  @After
  public void tearDown() {
    if (spanner != null) {
      spanner.close();
    }

    if (spannerEmulator != null) {
      spannerEmulator.stop();
    }
  }

  @Test
  public void runScdType1Pipeline() throws IOException, ExecutionException, InterruptedException {
    createSpannerDDL(RESOURCE_DIR + "/spanner-schema-type-1.sql");
    List<Struct> initialRows = createSampleRows(SpannerScdMutationTransform.ScdType.TYPE_1);
    String dataFilePath = Resources.getResource(RESOURCE_DIR + "/data-write.avro").getPath();
    String[] pipelineArgs =
        new String[] {
          String.format("--inputFilePattern=%s", dataFilePath),
          String.format("--spannerProjectId=%s", PROJECT_ID),
          String.format("--instanceId=%s", SPANNER_INSTANCE_ID),
          String.format("--databaseId=%s", SPANNER_DATABASE_ID),
          String.format("--tableName=%s", SPANNER_TABLE_NAME),
          "--spannerBatchSize=2",
          "--scdType=TYPE_1",
          "--primaryKeyColumnNames=id"
        };
    AvroToSpannerScdOptions pipelineOptions =
        PipelineOptionsFactory.fromArgs(pipelineArgs).as(AvroToSpannerScdOptions.class);
    SpannerConfig spannerConfig = makeSpannerConfig();
    SpannerFactory spannerFactory = makeSpannerFactory(spannerConfig);
    ClockFactory clockFactory = new SystemUtcClockFactory();

    new AvroToSpannerScdPipeline(
            pipeline, pipelineOptions, spannerConfig, spannerFactory, clockFactory)
        .makePipeline();
    pipeline.run().waitUntilFinish();

    List<Struct> outputRecords = readTableRows(SpannerScdMutationTransform.ScdType.TYPE_1);
    SpannerAsserts.assertThatStructs(outputRecords)
        // Pipeline makes 7 changes: inserts 4 new rows and updates 1 existing row once and 1
        // existing row twice. All updates are done in place.
        .hasRows(initialRows.size() + 4);
  }

  @Test
  public void runScdType2Pipeline() throws IOException, ExecutionException, InterruptedException {
    createSpannerDDL(RESOURCE_DIR + "/spanner-schema-type-2.sql");
    List<Struct> initialRows = createSampleRows(SpannerScdMutationTransform.ScdType.TYPE_2);
    String dataFilePath = Resources.getResource(RESOURCE_DIR + "/data-write.avro").getPath();
    String[] pipelineArgs =
        new String[] {
          String.format("--inputFilePattern=%s", dataFilePath),
          String.format("--spannerProjectId=%s", PROJECT_ID),
          String.format("--instanceId=%s", SPANNER_INSTANCE_ID),
          String.format("--databaseId=%s", SPANNER_DATABASE_ID),
          String.format("--tableName=%s", SPANNER_TABLE_NAME),
          "--spannerBatchSize=2",
          "--scdType=TYPE_2",
          "--primaryKeyColumnNames=id,end_date",
          "--startDateColumnName=start_date",
          "--endDateColumnName=end_date"
        };
    AvroToSpannerScdOptions pipelineOptions =
        PipelineOptionsFactory.fromArgs(pipelineArgs).as(AvroToSpannerScdOptions.class);
    SpannerConfig spannerConfig = makeSpannerConfig();
    SpannerFactory spannerFactory = makeSpannerFactory(spannerConfig);
    ClockFactory clockFactory = new SystemUtcClockFactory();

    new AvroToSpannerScdPipeline(
            pipeline, pipelineOptions, spannerConfig, spannerFactory, clockFactory)
        .makePipeline();
    pipeline.run().waitUntilFinish();

    List<Struct> outputRecords = readTableRows(SpannerScdMutationTransform.ScdType.TYPE_2);
    SpannerAsserts.assertThatStructs(outputRecords)
        // Pipeline makes 7 changes: inserts 4 new rows and updates 1 existing row once and 1
        // existing row twice.
        // However, since it is SCD Type 2, both are handled by adding a new row.
        .hasRows(initialRows.size() + 7);
  }

  private void createSpannerEmulator() {
    spannerEmulator =
        new SpannerEmulatorContainer(
            DockerImageName.parse(
                "gcr.io/cloud-spanner-emulator/emulator@sha256:636fdfc528824bae5f0ea2eca6ae307fe81092f05ec21038008bc0d6100e52fc"));
    spannerEmulator.start();

    spannerHost = spannerEmulator.getEmulatorGrpcEndpoint();
    SpannerOptions options =
        SpannerOptions.newBuilder().setEmulatorHost(spannerHost).setProjectId(PROJECT_ID).build();
    spanner = options.getService();
  }

  private void createSpannerInstance() throws ExecutionException, InterruptedException {
    InstanceAdminClient instanceAdminClient = spanner.getInstanceAdminClient();
    instanceAdminClient
        .createInstance(
            InstanceInfo.newBuilder(InstanceId.of(PROJECT_ID, SPANNER_INSTANCE_ID))
                .setNodeCount(1)
                .setDisplayName(SPANNER_INSTANCE_ID)
                .setInstanceConfigId(InstanceConfigId.of(PROJECT_ID, SPANNER_INSTANCE_ID))
                .build())
        .get();
  }

  /**
   * Creates DDL mutation on Spanner.
   *
   * <p>Reads the sql file from resources directory and applies the DDL to Spanner instance.
   *
   * @param resourceName SQL file name with path relative to resources directory
   */
  private void createSpannerDDL(String resourceName)
      throws IOException, ExecutionException, InterruptedException {
    String ddl =
        String.join(
            " ",
            Resources.readLines(Resources.getResource(resourceName), StandardCharsets.UTF_8)
                .stream()
                // Comments break DDL statements, especially when joined in one
                // line like the above.
                .filter(line -> line.length() < 2 || !line.strip().substring(0, 2).equals("--"))
                .toList());
    ddl = ddl.trim();
    List<String> ddls = Arrays.stream(ddl.split(";")).filter(d -> !d.isBlank()).collect(toList());

    DatabaseAdminClient dbAdminClient = spanner.getDatabaseAdminClient();
    dbAdminClient.createDatabase(SPANNER_INSTANCE_ID, SPANNER_DATABASE_ID, ddls).get();
  }

  private List<Struct> readTableRows(ScdType scdType) {
    ImmutableList<String> columns;
    switch (scdType) {
      case TYPE_1:
        columns =
            ImmutableList.of("id", "first_name", "last_name", "department", "salary", "hire_date");
        break;
      case TYPE_2:
        columns =
            ImmutableList.of(
                "id",
                "first_name",
                "last_name",
                "department",
                "salary",
                "hire_date",
                "start_date",
                "end_date");
        break;
      default:
        columns = ImmutableList.of();
        break;
    }

    DatabaseClient dbClient =
        spanner.getDatabaseClient(
            DatabaseId.of(PROJECT_ID, SPANNER_INSTANCE_ID, SPANNER_DATABASE_ID));
    ResultSet resultSet = dbClient.singleUse().read(SPANNER_TABLE_NAME, KeySet.all(), columns);

    List<Struct> results = new ArrayList<>();
    while (resultSet.next()) {
      results.add(resultSet.getCurrentRowAsStruct());
    }
    return results;
  }

  private List<Struct> createSampleRows(ScdType scdType) {
    List<Mutation> mutations =
        switch (scdType) {
          case TYPE_1 ->
              List.of(
                  Mutation.newInsertBuilder(SPANNER_TABLE_NAME)
                      .set("id")
                      .to(9968777427L)
                      .set("first_name")
                      .to("Nadean")
                      .set("last_name")
                      .to("Macie")
                      .set("department")
                      .to("Engineering")
                      .set("salary")
                      .to(63500000.0)
                      .set("hire_date")
                      .to("1937-10-08")
                      .build(),
                  Mutation.newInsertBuilder(SPANNER_TABLE_NAME)
                      .set("id")
                      .to(9970229008L)
                      .set("first_name")
                      .to("Dilan")
                      .set("last_name")
                      .to("Duayne")
                      .set("department")
                      .to("Research and Development")
                      .set("salary")
                      .to(84900000.0)
                      .set("hire_date")
                      .to("1992-02-25")
                      .build(),
                  Mutation.newInsertBuilder(SPANNER_TABLE_NAME)
                      .set("id")
                      .to(9972236478L)
                      .set("first_name")
                      .to("Perry")
                      .set("last_name")
                      .to("Hollyn")
                      .set("department")
                      .to("Accounting")
                      .set("salary")
                      .to(61600000.0)
                      .set("hire_date")
                      .to("1971-09-02")
                      .build(),
                  Mutation.newInsertBuilder(SPANNER_TABLE_NAME)
                      .set("id")
                      .to(9975339673L)
                      .set("first_name")
                      .to("Sophie")
                      .set("last_name")
                      .to("Danah")
                      .set("department")
                      .to("Internal Audit")
                      .set("salary")
                      .to(66300000.0)
                      .set("hire_date")
                      .to("1999-05-14")
                      .build(),
                  Mutation.newInsertBuilder(SPANNER_TABLE_NAME)
                      .set("id")
                      .to(9976152507L)
                      .set("first_name")
                      .to("Hillari")
                      .set("last_name")
                      .to("Sally")
                      .set("department")
                      .to("Production")
                      .set("salary")
                      .to(31900000.0)
                      .set("hire_date")
                      .to("1973-06-03")
                      .build());
          case TYPE_2 ->
              List.of(
                  Mutation.newInsertBuilder(SPANNER_TABLE_NAME)
                      .set("id")
                      .to(9968777427L)
                      .set("first_name")
                      .to("Nadean")
                      .set("last_name")
                      .to("Macie")
                      .set("department")
                      .to("Engineering")
                      .set("salary")
                      .to(63500000.0)
                      .set("hire_date")
                      .to("1937-10-08")
                      .set("start_date")
                      .to(Timestamp.parseTimestamp("2024-01-01T00:00:01.000Z"))
                      .set("end_date")
                      .to(NullValues.NULL_TIMESTAMP)
                      .build(),
                  Mutation.newInsertBuilder(SPANNER_TABLE_NAME)
                      .set("id")
                      .to(9970229008L)
                      .set("first_name")
                      .to("Dilan")
                      .set("last_name")
                      .to("Duayne")
                      .set("department")
                      .to("Research and Development")
                      .set("salary")
                      .to(84900000.0)
                      .set("hire_date")
                      .to("1992-02-25")
                      .set("start_date")
                      .to(Timestamp.parseTimestamp("2024-02-01T00:00:01.000Z"))
                      .set("end_date")
                      .to(Timestamp.parseTimestamp("2024-02-15T00:00:01.000Z"))
                      .build(),
                  Mutation.newInsertBuilder(SPANNER_TABLE_NAME)
                      .set("id")
                      .to(9970229008L)
                      .set("first_name")
                      .to("Dilan")
                      .set("last_name")
                      .to("Duayne")
                      .set("department")
                      .to("Management")
                      .set("salary")
                      .to(84900000.0)
                      .set("hire_date")
                      .to("1992-02-25")
                      .set("start_date")
                      .to(Timestamp.parseTimestamp("2024-02-15T00:00:01.000Z"))
                      .set("end_date")
                      .to(NullValues.NULL_TIMESTAMP)
                      .build(),
                  Mutation.newInsertBuilder(SPANNER_TABLE_NAME)
                      .set("id")
                      .to(9972236478L)
                      .set("first_name")
                      .to("Perry")
                      .set("last_name")
                      .to("Hollyn")
                      .set("department")
                      .to("Accounting")
                      .set("salary")
                      .to(61600000.0)
                      .set("hire_date")
                      .to("1971-09-02")
                      .set("start_date")
                      .to(Timestamp.parseTimestamp("2024-03-01T00:00:01.000Z"))
                      .set("end_date")
                      .to(NullValues.NULL_TIMESTAMP)
                      .build(),
                  Mutation.newInsertBuilder(SPANNER_TABLE_NAME)
                      .set("id")
                      .to(9975339673L)
                      .set("first_name")
                      .to("Sophie")
                      .set("last_name")
                      .to("Danah")
                      .set("department")
                      .to("Internal Audit")
                      .set("salary")
                      .to(66300000.0)
                      .set("hire_date")
                      .to("1999-05-14")
                      .set("start_date")
                      .to(Timestamp.parseTimestamp("2024-04-01T00:00:01.000Z"))
                      .set("end_date")
                      .to(NullValues.NULL_TIMESTAMP)
                      .build(),
                  Mutation.newInsertBuilder(SPANNER_TABLE_NAME)
                      .set("id")
                      .to(9976152507L)
                      .set("first_name")
                      .to("Hillari")
                      .set("last_name")
                      .to("Sally")
                      .set("department")
                      .to("Production")
                      .set("salary")
                      .to(31900000.0)
                      .set("hire_date")
                      .to("1973-06-03")
                      .set("start_date")
                      .to(Timestamp.parseTimestamp("2024-05-01T00:00:01.000Z"))
                      .set("end_date")
                      .to(NullValues.NULL_TIMESTAMP)
                      .build());
        };

    DatabaseClient dbClient =
        spanner.getDatabaseClient(
            DatabaseId.of(PROJECT_ID, SPANNER_INSTANCE_ID, SPANNER_DATABASE_ID));
    dbClient.write(mutations);
    return readTableRows(scdType);
  }

  private SpannerConfig makeSpannerConfig() {
    return SpannerConfig.create()
        .withProjectId(PROJECT_ID)
        .withInstanceId(SPANNER_INSTANCE_ID)
        .withDatabaseId(SPANNER_DATABASE_ID)
        .withEmulatorHost(ValueProvider.StaticValueProvider.of(spannerHost));
  }

  private SpannerFactory makeSpannerFactory(SpannerConfig spannerConfig) {
    return new DefaultSpannerFactory(spannerConfig, new TestSpannerOptionsFactory(spannerConfig));
  }

  static final class TestSpannerOptionsFactory implements SpannerOptionsFactory {

    private final SpannerConfig spannerConfig;

    TestSpannerOptionsFactory(SpannerConfig spannerConfig) {
      this.spannerConfig = spannerConfig;
    }

    @Override
    public SpannerOptions getSpannerOptions() {
      return SpannerOptions.newBuilder()
          .setProjectId(spannerConfig.getProjectId().get())
          .setEmulatorHost(spannerConfig.getEmulatorHost().get())
          .build();
    }
  }
}
