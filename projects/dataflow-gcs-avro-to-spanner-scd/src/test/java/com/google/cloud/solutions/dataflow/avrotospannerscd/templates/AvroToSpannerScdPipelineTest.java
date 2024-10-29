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

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public final class AvroToSpannerScdPipelineTest {

  AvroToSpannerScdOptions pipelineOptions;

  // Exact values are not relevant for these test, defining some valid values here for easy use.
  private static final String INPUT_FILE_PATTERN = "gs://bucket/file-path/*";
  private static final String SPANNER_INSTANCE_ID = "spanner-instance-id";
  private static final String SPANNER_DATABASE_ID = "spanner-database-id";
  private static final String SPANNER_TABLE_NAME = "spanner-table";
  private static final String PRIMARY_KEY_COLUMN_NAMES_STR = "id,key";
  private static final String FIELD_NAME = "column";

  @Test
  public void testValidateOptions_throwsEmptySpannerProjectId() {
    String[] pipelineArgs =
        new String[] {
          String.format("--spannerProjectId=%s", ""),
          // Other required fields.
          String.format("--inputFilePattern=%s", INPUT_FILE_PATTERN),
          String.format("--instanceId=%s", SPANNER_INSTANCE_ID),
          String.format("--databaseId=%s", SPANNER_DATABASE_ID),
          String.format("--tableName=%s", SPANNER_TABLE_NAME),
          String.format("--primaryKeyColumnNames=%s", PRIMARY_KEY_COLUMN_NAMES_STR),
        };

    IllegalArgumentException thrown =
        assertThrows(
            IllegalArgumentException.class, () -> AvroToSpannerScdPipeline.main(pipelineArgs));

    assertThat(thrown).hasMessageThat().contains("Spanner project id must not be empty.");
  }

  @Test
  public void testValidateOptions_throwsEmptyInstanceId() {
    String[] pipelineArgs =
        new String[] {
          String.format("--instanceId=%s", ""),
          // Other required fields.
          String.format("--inputFilePattern=%s", INPUT_FILE_PATTERN),
          String.format("--databaseId=%s", SPANNER_DATABASE_ID),
          String.format("--tableName=%s", SPANNER_TABLE_NAME),
          String.format("--primaryKeyColumnNames=%s", PRIMARY_KEY_COLUMN_NAMES_STR),
        };

    IllegalArgumentException thrown =
        assertThrows(
            IllegalArgumentException.class, () -> AvroToSpannerScdPipeline.main(pipelineArgs));

    assertThat(thrown).hasMessageThat().contains("Spanner instance id must not be empty.");
  }

  @Test
  public void testValidateOptions_throwsEmptySpannerDatabaseId() {
    String[] pipelineArgs =
        new String[] {
          String.format("--databaseId=%s", ""),
          // Other required fields.
          String.format("--inputFilePattern=%s", INPUT_FILE_PATTERN),
          String.format("--instanceId=%s", SPANNER_INSTANCE_ID),
          String.format("--tableName=%s", SPANNER_TABLE_NAME),
          String.format("--primaryKeyColumnNames=%s", PRIMARY_KEY_COLUMN_NAMES_STR),
        };

    IllegalArgumentException thrown =
        assertThrows(
            IllegalArgumentException.class, () -> AvroToSpannerScdPipeline.main(pipelineArgs));

    assertThat(thrown).hasMessageThat().contains("Spanner database id must not be empty.");
  }

  @Test
  public void testValidateOptions_throwsNegativeBatchSize() {
    String[] pipelineArgs =
        new String[] {
          String.format("--spannerBatchSize=%s", "-5"),
          // Other required fields.
          String.format("--inputFilePattern=%s", INPUT_FILE_PATTERN),
          String.format("--instanceId=%s", SPANNER_INSTANCE_ID),
          String.format("--databaseId=%s", SPANNER_DATABASE_ID),
          String.format("--tableName=%s", SPANNER_TABLE_NAME),
          String.format("--primaryKeyColumnNames=%s", PRIMARY_KEY_COLUMN_NAMES_STR),
        };

    IllegalArgumentException thrown =
        assertThrows(
            IllegalArgumentException.class, () -> AvroToSpannerScdPipeline.main(pipelineArgs));

    assertThat(thrown)
        .hasMessageThat()
        .contains("Batch size must be greater than 0. Provided: -5.");
  }

  @Test
  public void testValidateOptions_throwsEmptyTableName() {
    String[] pipelineArgs =
        new String[] {
          String.format("--tableName=%s", ""),
          // Other required fields.
          String.format("--inputFilePattern=%s", INPUT_FILE_PATTERN),
          String.format("--instanceId=%s", SPANNER_INSTANCE_ID),
          String.format("--databaseId=%s", SPANNER_DATABASE_ID),
          String.format("--primaryKeyColumnNames=%s", PRIMARY_KEY_COLUMN_NAMES_STR),
        };

    IllegalArgumentException thrown =
        assertThrows(
            IllegalArgumentException.class, () -> AvroToSpannerScdPipeline.main(pipelineArgs));

    assertThat(thrown).hasMessageThat().contains("Spanner table name must not be empty.");
  }

  @Test
  public void testValidateOptions_throwsEmptyPrimaryKeyColumnNames() {
    String[] pipelineArgs =
        new String[] {
          String.format("--primaryKeyColumnNames=%s", ""),
          // Other required fields.
          String.format("--inputFilePattern=%s", INPUT_FILE_PATTERN),
          String.format("--instanceId=%s", SPANNER_INSTANCE_ID),
          String.format("--databaseId=%s", SPANNER_DATABASE_ID),
          String.format("--tableName=%s", SPANNER_TABLE_NAME),
        };

    IllegalArgumentException thrown =
        assertThrows(
            IllegalArgumentException.class, () -> AvroToSpannerScdPipeline.main(pipelineArgs));

    assertThat(thrown)
        .hasMessageThat()
        .contains("Spanner primary key column names must not be empty.");
  }

  @Test
  public void testValidateOptions_throwsEmptyOrderByColumnName() {
    String[] pipelineArgs =
        new String[] {
          String.format("--orderByColumnName=%s", ""),
          // Other required fields.
          String.format("--inputFilePattern=%s", INPUT_FILE_PATTERN),
          String.format("--instanceId=%s", SPANNER_INSTANCE_ID),
          String.format("--databaseId=%s", SPANNER_DATABASE_ID),
          String.format("--tableName=%s", SPANNER_TABLE_NAME),
          String.format("--primaryKeyColumnNames=%s", PRIMARY_KEY_COLUMN_NAMES_STR),
        };

    IllegalArgumentException thrown =
        assertThrows(
            IllegalArgumentException.class, () -> AvroToSpannerScdPipeline.main(pipelineArgs));

    assertThat(thrown)
        .hasMessageThat()
        .contains("When provided, order by column name must not be empty.");
  }

  @Test
  public void testValidateOptions_scdType1_throwsIfUsingStartDate() {
    String[] pipelineArgs =
        new String[] {
          "--scdType=TYPE_1",
          String.format("--startDateColumnName=%s", FIELD_NAME),
          // Other required fields.
          String.format("--inputFilePattern=%s", INPUT_FILE_PATTERN),
          String.format("--instanceId=%s", SPANNER_INSTANCE_ID),
          String.format("--databaseId=%s", SPANNER_DATABASE_ID),
          String.format("--tableName=%s", SPANNER_TABLE_NAME),
          String.format("--primaryKeyColumnNames=%s", PRIMARY_KEY_COLUMN_NAMES_STR),
        };

    IllegalArgumentException thrown =
        assertThrows(
            IllegalArgumentException.class, () -> AvroToSpannerScdPipeline.main(pipelineArgs));

    assertThat(thrown)
        .hasMessageThat()
        .contains("When using SCD Type 1, start date column name is not used.");
  }

  @Test
  public void testValidateOptions_scdType1_throwsIfUsingEndDate() {
    String[] pipelineArgs =
        new String[] {
          "--scdType=TYPE_1",
          String.format("--endDateColumnName=%s", FIELD_NAME),
          // Other required fields.
          String.format("--inputFilePattern=%s", INPUT_FILE_PATTERN),
          String.format("--instanceId=%s", SPANNER_INSTANCE_ID),
          String.format("--databaseId=%s", SPANNER_DATABASE_ID),
          String.format("--tableName=%s", SPANNER_TABLE_NAME),
          String.format("--primaryKeyColumnNames=%s", PRIMARY_KEY_COLUMN_NAMES_STR),
        };

    IllegalArgumentException thrown =
        assertThrows(
            IllegalArgumentException.class, () -> AvroToSpannerScdPipeline.main(pipelineArgs));

    assertThat(thrown)
        .hasMessageThat()
        .contains("When using SCD Type 1, end date column name is not used.");
  }

  @Test
  public void testValidateOptions_scdType2_throwsEmptyStartDate() {
    String[] pipelineArgs =
        new String[] {
          "--scdType=TYPE_2",
          String.format("--startDateColumnName=%s", ""),
          // Other required fields.
          String.format("--endDateColumnName=%s", FIELD_NAME),
          String.format("--inputFilePattern=%s", INPUT_FILE_PATTERN),
          String.format("--instanceId=%s", SPANNER_INSTANCE_ID),
          String.format("--databaseId=%s", SPANNER_DATABASE_ID),
          String.format("--tableName=%s", SPANNER_TABLE_NAME),
          String.format("--primaryKeyColumnNames=%s", PRIMARY_KEY_COLUMN_NAMES_STR),
        };

    IllegalArgumentException thrown =
        assertThrows(
            IllegalArgumentException.class, () -> AvroToSpannerScdPipeline.main(pipelineArgs));

    assertThat(thrown)
        .hasMessageThat()
        .contains("When provided, start date column name must not be empty.");
  }

  @Test
  public void testValidateOptions_scdType2_throwsNoEndDate() {
    String[] pipelineArgs =
        new String[] {
          "--scdType=TYPE_2",
          // Other required fields.
          String.format("--inputFilePattern=%s", INPUT_FILE_PATTERN),
          String.format("--instanceId=%s", SPANNER_INSTANCE_ID),
          String.format("--databaseId=%s", SPANNER_DATABASE_ID),
          String.format("--tableName=%s", SPANNER_TABLE_NAME),
          String.format("--primaryKeyColumnNames=%s", PRIMARY_KEY_COLUMN_NAMES_STR),
        };

    NullPointerException thrown =
        assertThrows(NullPointerException.class, () -> AvroToSpannerScdPipeline.main(pipelineArgs));

    assertThat(thrown)
        .hasMessageThat()
        .contains("When using SCD Type 2, end date column name must be provided.");
  }

  @Test
  public void testValidateOptions_scdType2_throwsEmptyEndDate() {
    String[] pipelineArgs =
        new String[] {
          "--scdType=TYPE_2",
          String.format("--endDateColumnName=%s", ""),
          // Other required fields.
          String.format("--inputFilePattern=%s", INPUT_FILE_PATTERN),
          String.format("--instanceId=%s", SPANNER_INSTANCE_ID),
          String.format("--databaseId=%s", SPANNER_DATABASE_ID),
          String.format("--tableName=%s", SPANNER_TABLE_NAME),
          String.format("--primaryKeyColumnNames=%s", PRIMARY_KEY_COLUMN_NAMES_STR),
        };

    IllegalArgumentException thrown =
        assertThrows(
            IllegalArgumentException.class, () -> AvroToSpannerScdPipeline.main(pipelineArgs));

    assertThat(thrown)
        .hasMessageThat()
        .contains("When using SCD Type 2, end date column name must not be empty.");
  }
}
