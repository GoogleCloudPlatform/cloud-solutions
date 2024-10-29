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

package com.google.cloud.solutions.dataflow.avrotospannerscd.utils;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;

import com.google.cloud.ByteArray;
import com.google.cloud.Date;
import com.google.cloud.Timestamp;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.StructHelper.NullValues;
import com.google.cloud.spanner.Key;
import com.google.cloud.spanner.Mutation;
import com.google.cloud.spanner.Struct;
import com.google.cloud.spanner.Value;
import com.google.common.collect.ImmutableList;
import com.google.common.flogger.GoogleLogger;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.junit.runners.Parameterized;
import org.junit.runners.Parameterized.Parameters;

public final class StructHelperTest {

  @RunWith(JUnit4.class)
  public static final class StructHelperMethodsTest {
    @Test
    public void withoutField_removesFieldFromStruct() {
      Struct output = StructHelper.of(TEST_RECORD).withoutField("booleanField").struct();

      // Since the field is removed, accessing the field will throw an error.
      RuntimeException thrown =
          assertThrows(IllegalArgumentException.class, () -> output.getStruct("booleanField"));

      assertThat(thrown).hasMessageThat().contains("Field not found: booleanField");
    }

    @Test
    public void withoutField_keepsAllOtherFields() {
      StructHelper structHelper =
          StructHelper.of(TEST_RECORD).withUpdatedFieldValue("newField", Value.string("value"));

      Struct output = structHelper.withoutField("newField").struct();

      assertThat(output).isEqualTo(TEST_RECORD);
    }

    @Test
    public void withUpdatedFieldValue_addsNewFieldIfNotExisting() {
      Struct output =
          StructHelper.of(TEST_RECORD)
              .withUpdatedFieldValue("newField", Value.string("Nito"))
              .struct();

      assertThat(output.getString("newField")).isEqualTo("Nito");
    }

    @Test
    public void withUpdatedFieldValue_updatesExistingField() {
      Struct output =
          StructHelper.of(TEST_RECORD)
              .withUpdatedFieldValue("stringField", Value.string("newValue"))
              .struct();

      assertThat(output.getString("stringField")).isEqualTo("newValue");
    }

    @Test
    public void withUpdatedFieldValue_keepsAllOtherFields() {
      Struct output =
          StructHelper.of(TEST_RECORD)
              // Updating field to the same value as it's currently set, so output should match
              // input.
              .withUpdatedFieldValue("booleanField", Value.bool(Boolean.TRUE))
              .struct();

      assertThat(output).isEqualTo(TEST_RECORD);
    }
  }

  @RunWith(Parameterized.class)
  public static final class KeyMakerTest {

    private final List<String> primaryKeys;
    private final Key expectedKey;

    public KeyMakerTest(String testCaseName, List<String> primaryKeys, Key expectedKey) {
      this.primaryKeys = primaryKeys;
      this.expectedKey = expectedKey;

      GoogleLogger.forEnclosingClass().atInfo().log("testCase: %s", testCaseName);
    }

    @Test
    public void createKey_createsExpectedKey() {
      Key returnKey = StructHelper.of(TEST_RECORD).keyMaker(primaryKeys).createKey();

      assertThat(returnKey).isEqualTo(expectedKey);
    }

    @Parameters(name = "{0}")
    public static ImmutableList<Object[]> testingParameters() {
      return ImmutableList.<Object[]>builder()
          .add(
              new Object[] {
                /* testCaseName= */ "For one key",
                /* primaryKeys= */ List.of("pk1"),
                /* expectedKey= */ Key.newBuilder().append("value1").build()
              })
          .add(
              new Object[] {
                /* testCaseName= */ "For multiple keys, in order",
                /* primaryKeys= */ List.of("pk1", "pk2", "pk3"),
                /* expectedKey= */ Key.newBuilder().append("value1").append(true).append(3).build()
              })
          .add(
              new Object[] {
                /* testCaseName= */ "For multiple keys, out of order",
                /* primaryKeys= */ List.of("pk2", "pk3", "pk1"),
                /* expectedKey= */ Key.newBuilder().append(true).append(3).append("value1").build()
              })
          .add(
              new Object[] {
                /* testCaseName= */ "For multiple keys, with null types",
                /* primaryKeys= */ List.of("pk1", "nullBooleanField", "nullTimestampField"),
                /* expectedKey= */ Key.newBuilder()
                    .append("value1")
                    .append(NullValues.NULL_TIMESTAMP)
                    .append(NullValues.NULL_BOOLEAN)
                    .build()
              })
          .add(
              new Object[] {
                /* testCaseName= */ "For booleanField",
                /* primaryKeys= */ List.of("booleanField"),
                /* expectedKey= */ Key.newBuilder().append(Boolean.TRUE).build()
              })
          .add(
              new Object[] {
                /* testCaseName= */ "For bytesField",
                /* primaryKeys= */ List.of("bytesField"),
                /* expectedKey= */ Key.newBuilder().append(ByteArray.fromBase64("Tml0bw==")).build()
              })
          .add(
              new Object[] {
                /* testCaseName= */ "For dateField",
                /* primaryKeys= */ List.of("dateField"),
                /* expectedKey= */ Key.newBuilder()
                    .append(Date.fromYearMonthDay(1990, 7, 14))
                    .build()
              })
          .add(
              new Object[] {
                /* testCaseName= */ "For float32Field",
                /* primaryKeys= */ List.of("float32Field"),
                /* expectedKey= */ Key.newBuilder().append(3.14F).build()
              })
          .add(
              new Object[] {
                /* testCaseName= */ "For float64Field",
                /* primaryKeys= */ List.of("float64Field"),
                /* expectedKey= */ Key.newBuilder().append(3.14).build()
              })
          .add(
              new Object[] {
                /* testCaseName= */ "For int64Field",
                /* primaryKeys= */ List.of("int64Field"),
                /* expectedKey= */ Key.newBuilder().append(777L).build()
              })
          .add(
              new Object[] {
                /* testCaseName= */ "For jsonField",
                /* primaryKeys= */ List.of("jsonField"),
                /* expectedKey= */ Key.newBuilder().append("{\"name\": \"Nito\"}").build()
              })
          .add(
              new Object[] {
                /* testCaseName= */ "For numericField",
                /* primaryKeys= */ List.of("numericField"),
                /* expectedKey= */ Key.newBuilder().append(BigDecimal.valueOf(3.14)).build()
              })
          .add(
              new Object[] {
                /* testCaseName= */ "For pgNumericField",
                /* primaryKeys= */ List.of("pgNumericField"),
                /* expectedKey= */ Key.newBuilder().append(BigDecimal.valueOf(3.14)).build()
              })
          .add(
              new Object[] {
                /* testCaseName= */ "For jsonbField",
                /* primaryKeys= */ List.of("jsonbField"),
                /* expectedKey= */ Key.newBuilder().append("{\"name\": \"Nito\"}").build()
              })
          .add(
              new Object[] {
                /* testCaseName= */ "For stringField",
                /* primaryKeys= */ List.of("stringField"),
                /* expectedKey= */ Key.newBuilder().append("string").build()
              })
          .add(
              new Object[] {
                /* testCaseName= */ "For timestampField",
                /* primaryKeys= */ List.of("timestampField"),
                /* expectedKey= */ Key.newBuilder()
                    .append(Timestamp.ofTimeMicroseconds(1000))
                    .build()
              })
          .build();
    }
  }

  @RunWith(JUnit4.class)
  public static final class KeyMakerExceptionsTest {
    @Test
    public void createKey_throwsForNonExistingPrimaryKey() {
      List<String> primaryKeys = List.of("nonExistingPk");

      RuntimeException thrown =
          assertThrows(
              RuntimeException.class,
              () -> StructHelper.of(TEST_RECORD).keyMaker(primaryKeys).createKey());

      assertThat(thrown)
          .hasMessageThat()
          .contains("Primary key name nonExistingPk not found in record. Unable to create Key.");
    }

    @Test
    public void createKey_throwsForNonSupportedType() {
      List<String> primaryKeys = List.of("structField");

      UnsupportedOperationException thrown =
          assertThrows(
              UnsupportedOperationException.class,
              () -> StructHelper.of(TEST_RECORD).keyMaker(primaryKeys).createKey());

      assertThat(thrown).hasMessageThat().contains("Unsupported Spanner field type STRUCT.");
    }
  }

  @RunWith(Parameterized.class)
  public static final class StructComparatorTestParameterized {

    private final Struct firstRecord;
    private final Struct secondRecord;
    private final Struct thirdRecord;

    /** Records must be in expected output order. */
    public StructComparatorTestParameterized(
        String testCaseName, Struct firstRecord, Struct secondRecord, Struct thirdRecord) {
      this.firstRecord = firstRecord;
      this.secondRecord = secondRecord;
      this.thirdRecord = thirdRecord;

      GoogleLogger.forEnclosingClass().atInfo().log("testCase: %s", testCaseName);
    }

    @Test
    public void compare_comparesToProduceNaturalOrder() {
      // Input records in out of order.
      ArrayList<Struct> inputRecords =
          new ArrayList<>(List.of(thirdRecord, firstRecord, secondRecord));
      ArrayList<Struct> expectedOutput =
          new ArrayList<>(List.of(firstRecord, secondRecord, thirdRecord));

      inputRecords.sort(StructHelper.StructComparator.create("orderColumn"));

      assertThat(inputRecords).containsExactlyElementsIn(expectedOutput).inOrder();
    }

    @Test
    public void compare_comparesToProduceReverseOrder() {
      // Input records in out of order.
      ArrayList<Struct> inputRecords =
          new ArrayList<>(List.of(thirdRecord, firstRecord, secondRecord));
      ArrayList<Struct> expectedOutput =
          new ArrayList<>(List.of(thirdRecord, secondRecord, firstRecord));

      inputRecords.sort(StructHelper.StructComparator.create("orderColumn").reversed());

      assertThat(inputRecords).containsExactlyElementsIn(expectedOutput).inOrder();
    }

    @Parameters(name = "{0}")
    public static ImmutableList<Object[]> testingParameters() {
      return ImmutableList.<Object[]>builder()
          .add(
              new Object[] {
                /* testCaseName= */ "Boolean",
                /* firstRecord= */ Struct.newBuilder()
                    .set("orderColumn")
                    .to(NullValues.NULL_BOOLEAN)
                    .build(),
                /* secondRecord= */ Struct.newBuilder()
                    .set("orderColumn")
                    .to(Boolean.FALSE)
                    .build(),
                /* thirdRecord= */ Struct.newBuilder().set("orderColumn").to(Boolean.TRUE).build(),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "Date",
                /* firstRecord= */ Struct.newBuilder()
                    .set("orderColumn")
                    .to(NullValues.NULL_DATE)
                    .build(),
                /* secondRecord= */ Struct.newBuilder()
                    .set("orderColumn")
                    .to(Date.fromYearMonthDay(1990, 7, 14))
                    .build(),
                /* thirdRecord= */ Struct.newBuilder()
                    .set("orderColumn")
                    .to(Date.fromYearMonthDay(2024, 1, 1))
                    .build(),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "Float32",
                /* firstRecord= */ Struct.newBuilder()
                    .set("orderColumn")
                    .to(NullValues.NULL_FLOAT32)
                    .build(),
                /* secondRecord= */ Struct.newBuilder().set("orderColumn").to(2.72F).build(),
                /* thirdRecord= */ Struct.newBuilder().set("orderColumn").to(3.14F).build(),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "Float64",
                /* firstRecord= */ Struct.newBuilder()
                    .set("orderColumn")
                    .to(NullValues.NULL_FLOAT64)
                    .build(),
                /* secondRecord= */ Struct.newBuilder().set("orderColumn").to(2.72).build(),
                /* thirdRecord= */ Struct.newBuilder().set("orderColumn").to(3.14).build(),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "Int64",
                /* firstRecord= */ Struct.newBuilder()
                    .set("orderColumn")
                    .to(NullValues.NULL_INT64)
                    .build(),
                /* secondRecord= */ Struct.newBuilder().set("orderColumn").to(-2).build(),
                /* thirdRecord= */ Struct.newBuilder().set("orderColumn").to(0).build(),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "Json",
                /* firstRecord= */ Struct.newBuilder()
                    .set("orderColumn")
                    .to(NullValues.NULL_JSON)
                    .build(),
                /* secondRecord= */ Struct.newBuilder().set("orderColumn").to("{\"a\": 1}").build(),
                /* thirdRecord= */ Struct.newBuilder().set("orderColumn").to("{\"a\": 2}").build(),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "Numeric",
                /* firstRecord= */ Struct.newBuilder()
                    .set("orderColumn")
                    .to(NullValues.NULL_JSON)
                    .build(),
                /* secondRecord= */ Struct.newBuilder()
                    .set("orderColumn")
                    .to(BigDecimal.valueOf(2.72))
                    .build(),
                /* thirdRecord= */ Struct.newBuilder()
                    .set("orderColumn")
                    .to(BigDecimal.valueOf(3.14))
                    .build(),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "PgNumeric",
                /* firstRecord= */ Struct.newBuilder()
                    .set("orderColumn")
                    .to(NullValues.NULL_NUMERIC)
                    .build(),
                /* secondRecord= */ Struct.newBuilder()
                    .set("orderColumn")
                    .to(Value.pgNumeric("2.72"))
                    .build(),
                /* thirdRecord= */ Struct.newBuilder()
                    .set("orderColumn")
                    .to(Value.pgNumeric("3.14"))
                    .build(),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "PgJsonb",
                /* firstRecord= */ Struct.newBuilder()
                    .set("orderColumn")
                    .to(NullValues.NULL_JSON)
                    .build(),
                /* secondRecord= */ Struct.newBuilder()
                    .set("orderColumn")
                    .to(Value.pgJsonb("{\"a\": 1}"))
                    .build(),
                /* thirdRecord= */ Struct.newBuilder()
                    .set("orderColumn")
                    .to(Value.pgJsonb("{\"a\": 2}"))
                    .build(),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "String",
                /* firstRecord= */ Struct.newBuilder()
                    .set("orderColumn")
                    .to(NullValues.NULL_STRING)
                    .build(),
                /* secondRecord= */ Struct.newBuilder().set("orderColumn").to("abc").build(),
                /* thirdRecord= */ Struct.newBuilder().set("orderColumn").to("xyz").build(),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "Timestamp",
                /* firstRecord= */ Struct.newBuilder()
                    .set("orderColumn")
                    .to(NullValues.NULL_TIMESTAMP)
                    .build(),
                /* secondRecord= */ Struct.newBuilder()
                    .set("orderColumn")
                    .to(Timestamp.ofTimeMicroseconds(10))
                    .build(),
                /* thirdRecord= */ Struct.newBuilder()
                    .set("orderColumn")
                    .to(Timestamp.ofTimeMicroseconds(1000))
                    .build(),
              })
          .build();
    }
  }

  @RunWith(JUnit4.class)
  public static final class MutationCreatorTest {

    @Test
    public void createInsertMutation_createsExpectedMutation() {
      var output =
          StructHelper.of(TEST_RECORD)
              .mutationCreator("tableName", ImmutableList.of("pk1", "pk2", "pk3"))
              .createInsertMutation();

      assertThat(output)
          .isEqualTo(
              Mutation.newInsertBuilder("tableName")
                  .set("pk1")
                  .to(Value.string("value1"))
                  .set("pk2")
                  .to(Value.bool(Boolean.TRUE))
                  .set("pk3")
                  .to(Value.int64(3))
                  .set("booleanField")
                  .to(Value.bool(Boolean.TRUE))
                  .set("nullBooleanField")
                  .to(Value.bool(NullValues.NULL_BOOLEAN))
                  .set("bytesField")
                  .to(Value.bytes(ByteArray.fromBase64("Tml0bw==")))
                  .set("dateField")
                  .to(Value.date(Date.fromYearMonthDay(1990, 7, 14)))
                  .set("float32Field")
                  .to(Value.float32(3.14F))
                  .set("float64Field")
                  .to(Value.float64(3.14))
                  .set("int64Field")
                  .to(Value.int64(777L))
                  .set("jsonField")
                  .to(Value.json("{\"name\": \"Nito\"}"))
                  .set("numericField")
                  .to(Value.numeric(BigDecimal.valueOf(3.14)))
                  .set("pgNumericField")
                  .to(Value.pgNumeric("3.14"))
                  .set("jsonbField")
                  .to(Value.pgJsonb("{\"name\": \"Nito\"}"))
                  .set("stringField")
                  .to(Value.string("string"))
                  .set("timestampField")
                  .to(Value.timestamp(Timestamp.ofTimeMicroseconds(1000)))
                  .set("nullTimestampField")
                  .to(Value.timestamp(NullValues.NULL_TIMESTAMP))
                  .set("structField")
                  .to(Struct.newBuilder().set("subField").to(123).build())
                  .build());
    }

    @Test
    public void createUpsertMutation_createsExpectedMutation() {
      var output =
          StructHelper.of(TEST_RECORD)
              .mutationCreator("tableName", ImmutableList.of("pk1", "pk2", "pk3"))
              .createUpsertMutation();

      assertThat(output)
          .isEqualTo(
              Mutation.newInsertOrUpdateBuilder("tableName")
                  .set("pk1")
                  .to(Value.string("value1"))
                  .set("pk2")
                  .to(Value.bool(Boolean.TRUE))
                  .set("pk3")
                  .to(Value.int64(3))
                  .set("booleanField")
                  .to(Value.bool(Boolean.TRUE))
                  .set("nullBooleanField")
                  .to(Value.bool(NullValues.NULL_BOOLEAN))
                  .set("bytesField")
                  .to(Value.bytes(ByteArray.fromBase64("Tml0bw==")))
                  .set("dateField")
                  .to(Value.date(Date.fromYearMonthDay(1990, 7, 14)))
                  .set("float32Field")
                  .to(Value.float32(3.14F))
                  .set("float64Field")
                  .to(Value.float64(3.14))
                  .set("int64Field")
                  .to(Value.int64(777L))
                  .set("jsonField")
                  .to(Value.json("{\"name\": \"Nito\"}"))
                  .set("numericField")
                  .to(Value.numeric(BigDecimal.valueOf(3.14)))
                  .set("pgNumericField")
                  .to(Value.pgNumeric("3.14"))
                  .set("jsonbField")
                  .to(Value.pgJsonb("{\"name\": \"Nito\"}"))
                  .set("stringField")
                  .to(Value.string("string"))
                  .set("timestampField")
                  .to(Value.timestamp(Timestamp.ofTimeMicroseconds(1000)))
                  .set("nullTimestampField")
                  .to(Value.timestamp(NullValues.NULL_TIMESTAMP))
                  .set("structField")
                  .to(Struct.newBuilder().set("subField").to(123).build())
                  .build());
    }

    @Test
    public void createDeleteMutation_createsExpectedMutation() {
      var output =
          StructHelper.of(TEST_RECORD)
              .mutationCreator("tableName", ImmutableList.of("pk1", "pk2", "pk3"))
              .createDeleteMutation();

      assertThat(output)
          .isEqualTo(
              Mutation.delete(
                  "tableName",
                  Key.newBuilder().append("value1").append(Boolean.TRUE).append(3).build()));
    }
  }

  private static final Struct TEST_RECORD =
      Struct.newBuilder()
          .set("pk1")
          .to("value1")
          .set("pk2")
          .to(true)
          .set("pk3")
          .to(3)
          .set("booleanField")
          .to(Value.bool(Boolean.TRUE))
          .set("nullBooleanField")
          .to(NullValues.NULL_BOOLEAN)
          .set("bytesField")
          .to(Value.bytes(ByteArray.fromBase64("Tml0bw==")))
          .set("dateField")
          .to(Value.date(Date.fromYearMonthDay(1990, 7, 14)))
          .set("float32Field")
          .to(Value.float32(3.14F))
          .set("float64Field")
          .to(Value.float64(3.14))
          .set("int64Field")
          .to(Value.int64(777L))
          .set("jsonField")
          .to(Value.json("{\"name\": \"Nito\"}"))
          .set("numericField")
          .to(Value.numeric(BigDecimal.valueOf(3.14)))
          .set("pgNumericField")
          .to(Value.pgNumeric("3.14"))
          .set("jsonbField")
          .to(Value.pgJsonb("{\"name\": \"Nito\"}"))
          .set("stringField")
          .to(Value.string("string"))
          .set("timestampField")
          .to(Value.timestamp(Timestamp.ofTimeMicroseconds(1000)))
          .set("nullTimestampField")
          .to(NullValues.NULL_TIMESTAMP)
          .set("structField")
          .to(Struct.newBuilder().set("subField").to(123).build())
          .build();
}
