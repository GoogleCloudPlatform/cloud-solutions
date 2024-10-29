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

import static com.google.cloud.solutions.dataflow.avrotospannerscd.testing.TestSampleCreator.createGenericRecord;
import static com.google.cloud.solutions.dataflow.avrotospannerscd.testing.TestSampleCreator.createStructWithField;
import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;

import com.google.cloud.ByteArray;
import com.google.cloud.Date;
import com.google.cloud.Timestamp;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.StructHelper.NullValues;
import com.google.cloud.spanner.Struct;
import com.google.cloud.spanner.Value;
import com.google.common.collect.ImmutableList;
import com.google.common.flogger.GoogleLogger;
import com.google.common.io.Resources;
import java.math.BigDecimal;
import java.nio.ByteBuffer;
import org.apache.avro.Conversions;
import org.apache.avro.LogicalTypes;
import org.apache.avro.Schema;
import org.apache.avro.generic.GenericRecord;
import org.apache.beam.sdk.extensions.avro.io.AvroIO;
import org.apache.beam.sdk.testing.PAssert;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.values.PCollection;
import org.junit.Rule;
import org.junit.Test;
import org.junit.experimental.runners.Enclosed;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.junit.runners.Parameterized;
import org.junit.runners.Parameterized.Parameters;

/** Tests AvroToStructFn functionality. */
@RunWith(Enclosed.class)
final class AvroToStructFnTest {

  /** Tests that AvroToStructFn casts GenericRecords to Struct. */
  @RunWith(Parameterized.class)
  public static final class AvroToStructFnParameterizedTest {

    private final GenericRecord inputRecord;
    private final Struct expectedStruct;

    /** Records must be in expected output order. */
    public AvroToStructFnParameterizedTest(
        String testCaseName, GenericRecord inputRecord, Struct expectedStruct) {
      this.inputRecord = inputRecord;
      this.expectedStruct = expectedStruct;

      GoogleLogger.forEnclosingClass().atInfo().log("testCase: %s", testCaseName);
    }

    @Test
    public void apply_castsDataToStruct() {
      assertThat(AvroToStructFn.create().apply(inputRecord)).isEqualTo(expectedStruct);
    }

    /** Creates test parameters. */
    @Parameters(name = "{0}")
    public static ImmutableList<Object[]> testingParameters() {
      return ImmutableList.<Object[]>builder()
          // Primitive types.
          .add(
              new Object[] {
                /* testCaseName= */ "BooleanTrue",
                /* inputRecord= */ createGenericRecord(
                    Schema.create(Schema.Type.BOOLEAN), Boolean.TRUE),
                /* expectedStruct= */ createStructWithField(Value.bool(Boolean.TRUE)),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "BooleanFalse",
                /* inputRecord= */ createGenericRecord(
                    Schema.create(Schema.Type.BOOLEAN), Boolean.FALSE),
                /* expectedStruct= */ createStructWithField(Value.bool(Boolean.FALSE)),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "Bytes",
                /* inputRecord= */ createGenericRecord(
                    Schema.create(Schema.Type.BYTES), ByteArray.fromBase64("Tml0bw==")),
                /* expectedStruct= */ createStructWithField(
                    Value.bytes(ByteArray.fromBase64("Tml0bw=="))),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "Double",
                /* inputRecord= */ createGenericRecord(Schema.create(Schema.Type.DOUBLE), 7.0),
                /* expectedStruct= */ createStructWithField(Value.float64(7.0)),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "Fixed",
                /* inputRecord= */ createGenericRecord(
                    Schema.createFixed("fixed", "doc", "namespace", 4),
                    ByteArray.fromBase64("Tml0bw==")),
                /* expectedStruct= */ createStructWithField(
                    Value.bytes(ByteArray.fromBase64("Tml0bw=="))),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "Float",
                /* inputRecord= */ createGenericRecord(Schema.create(Schema.Type.FLOAT), 7.0F),
                /* expectedStruct= */ createStructWithField(Value.float32(7.0F)),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "Int",
                /* inputRecord= */ createGenericRecord(Schema.create(Schema.Type.INT), 7),
                /* expectedStruct= */ createStructWithField(Value.int64(7)),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "Long",
                /* inputRecord= */ createGenericRecord(Schema.create(Schema.Type.LONG), 7L),
                /* expectedStruct= */ createStructWithField(Value.int64(7)),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "String",
                /* inputRecord= */ createGenericRecord(
                    Schema.create(Schema.Type.STRING), "stringValue"),
                /* expectedStruct= */ createStructWithField(Value.string("stringValue")),
              })
          // Logical types.
          .add(
              new Object[] {
                /* testCaseName= */ "Date",
                /* inputRecord= */ createGenericRecord(
                    new Schema.Parser()
                        .parse(
                            """
                            {"type": "int", "logicalType": "date"}"""),
                    7499),
                /* expectedStruct= */ createStructWithField(
                    Value.date(Date.fromYearMonthDay(1990, 7, 14))),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "Decimal",
                /* inputRecord= */ createGenericRecord(
                    new Schema.Parser()
                        .parse(
                            """
                            {
                                "type": "bytes",
                                "logicalType": "decimal",
                                "precision": 7,
                                "scale": 6
                            }"""),
                    ByteArray.copyFrom(
                        new Conversions.DecimalConversion()
                            .toBytes(
                                BigDecimal.valueOf(3141592L, 6),
                                new Schema.Parser()
                                    .parse(
                                        """
                                        {
                                            "type": "bytes",
                                            "logicalType": "decimal",
                                            "precision": 7,
                                            "scale": 6
                                        }"""),
                                LogicalTypes.fromSchema(
                                    new Schema.Parser()
                                        .parse(
                                            """
                                            {
                                                "type": "bytes",
                                                "logicalType": "decimal",
                                                "precision": 7,
                                                "scale": 6
                                            }"""))))),
                /* expectedStruct= */ createStructWithField(
                    Value.numeric(BigDecimal.valueOf(3141592, 6))),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "DecimalBytes",
                /* inputRecord= */ createGenericRecord(
                    new Schema.Parser()
                        .parse(
                            """
                            {
                                "type": "bytes",
                                "logicalType": "decimal",
                                "precision": 7,
                                "scale": 6
                            }"""),
                    ByteArray.copyFrom(
                            new Conversions.DecimalConversion()
                                .toBytes(
                                    BigDecimal.valueOf(3141592L, 6),
                                    new Schema.Parser()
                                        .parse(
                                            """
                                            {
                                                "type": "bytes",
                                                "logicalType": "decimal",
                                                "precision": 7,
                                                "scale": 6
                                            }"""),
                                    LogicalTypes.fromSchema(
                                        new Schema.Parser()
                                            .parse(
                                                """
                                                {
                                                    "type": "bytes",
                                                    "logicalType": "decimal",
                                                    "precision": 7,
                                                    "scale": 6
                                                }"""))))
                        .toByteArray()),
                /* expectedStruct= */ createStructWithField(
                    Value.numeric(BigDecimal.valueOf(3141592, 6))),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "Decimal",
                /* inputRecord= */ createGenericRecord(
                    new Schema.Parser()
                        .parse(
                            """
                            {
                                "type": "bytes",
                                "logicalType": "decimal",
                                "precision": 7,
                                "scale": 6
                            }"""),
                    ByteBuffer.wrap(
                        ByteArray.copyFrom(
                                new Conversions.DecimalConversion()
                                    .toBytes(
                                        BigDecimal.valueOf(3141592L, 6),
                                        new Schema.Parser()
                                            .parse(
                                                """
                                                {
                                                    "type": "bytes",
                                                    "logicalType": "decimal",
                                                    "precision": 7,
                                                    "scale": 6
                                                }"""),
                                        LogicalTypes.fromSchema(
                                            new Schema.Parser()
                                                .parse(
                                                    """
                                                    {
                                                        "type": "bytes",
                                                        "logicalType": "decimal",
                                                        "precision": 7,
                                                        "scale": 6
                                                    }"""))))
                            .toByteArray())),
                /* expectedStruct= */ createStructWithField(
                    Value.numeric(BigDecimal.valueOf(3141592, 6))),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "LocalTimestampMillis",
                /* inputRecord= */ createGenericRecord(
                    new Schema.Parser()
                        .parse(
                            """
                            {"type": "long", "logicalType": "local-timestamp-millis"}"""),
                    647917261000L),
                /* expectedStruct= */ createStructWithField(
                    Value.timestamp(Timestamp.ofTimeMicroseconds(647917261000000L))),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "TimestampMillis",
                /* inputRecord= */ createGenericRecord(
                    new Schema.Parser()
                        .parse(
                            """
                            {"type": "long", "logicalType": "local-timestamp-millis"}"""),
                    647917261000L),
                /* expectedStruct= */ createStructWithField(
                    Value.timestamp(Timestamp.ofTimeMicroseconds(647917261000000L))),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "LocalTimestampMicros",
                /* inputRecord= */ createGenericRecord(
                    new Schema.Parser()
                        .parse(
                            """
                            {"type": "long", "logicalType": "local-timestamp-micros"}"""),
                    647917261000000L),
                /* expectedStruct= */ createStructWithField(
                    Value.timestamp(Timestamp.ofTimeMicroseconds(647917261000000L))),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "TimestampMicros",
                /* inputRecord= */ createGenericRecord(
                    new Schema.Parser()
                        .parse(
                            """
                            {"type": "long", "logicalType": "timestamp-micros"}"""),
                    647917261000000L),
                /* expectedStruct= */ createStructWithField(
                    Value.timestamp(Timestamp.ofTimeMicroseconds(647917261000000L))),
              })
          // Nullable Types (Union): Primitive Types.
          .add(
              new Object[] {
                /* testCaseName= */ "NullableBoolean",
                /* inputRecord= */ createGenericRecord(
                    Schema.createUnion(
                        Schema.create(Schema.Type.BOOLEAN), Schema.create(Schema.Type.NULL)),
                    NullValues.NULL_BOOLEAN),
                /* expectedStruct= */ createStructWithField(Value.bool(NullValues.NULL_BOOLEAN)),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "NullableBooleanWithValue",
                /* inputRecord= */ createGenericRecord(
                    Schema.createUnion(
                        Schema.create(Schema.Type.BOOLEAN), Schema.create(Schema.Type.NULL)),
                    Boolean.TRUE),
                /* expectedStruct= */ createStructWithField(Value.bool(Boolean.TRUE)),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "NullableDouble",
                /* inputRecord= */ createGenericRecord(
                    Schema.createUnion(
                        Schema.create(Schema.Type.NULL), Schema.create(Schema.Type.DOUBLE)),
                    NullValues.NULL_FLOAT64),
                /* expectedStruct= */ createStructWithField(Value.float64(NullValues.NULL_FLOAT64)),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "NullableDoubleWithValue",
                /* inputRecord= */ createGenericRecord(
                    Schema.createUnion(
                        Schema.create(Schema.Type.NULL), Schema.create(Schema.Type.DOUBLE)),
                    7.0),
                /* expectedStruct= */ createStructWithField(Value.float64(7.0)),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "NullableFloat",
                /* inputRecord= */ createGenericRecord(
                    Schema.createUnion(
                        Schema.create(Schema.Type.FLOAT), Schema.create(Schema.Type.NULL)),
                    NullValues.NULL_FLOAT32),
                /* expectedStruct= */ createStructWithField(Value.float32(NullValues.NULL_FLOAT32)),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "NullableFloatWithValue",
                /* inputRecord= */ createGenericRecord(
                    Schema.createUnion(
                        Schema.create(Schema.Type.FLOAT), Schema.create(Schema.Type.NULL)),
                    7.0F),
                /* expectedStruct= */ createStructWithField(Value.float32(7.0F)),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "NullableInt",
                /* inputRecord= */ createGenericRecord(
                    Schema.createUnion(
                        Schema.create(Schema.Type.NULL), Schema.create(Schema.Type.INT)),
                    NullValues.NULL_INT64),
                /* expectedStruct= */ createStructWithField(Value.int64(NullValues.NULL_INT64)),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "NullableIntWithValue",
                /* inputRecord= */ createGenericRecord(
                    Schema.createUnion(
                        Schema.create(Schema.Type.NULL), Schema.create(Schema.Type.INT)),
                    7),
                /* expectedStruct= */ createStructWithField(Value.int64(7)),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "NullableLong",
                /* inputRecord= */ createGenericRecord(
                    Schema.createUnion(
                        Schema.create(Schema.Type.LONG), Schema.create(Schema.Type.NULL)),
                    NullValues.NULL_INT64),
                /* expectedStruct= */ createStructWithField(Value.int64(NullValues.NULL_INT64)),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "NullableLongWithValue",
                /* inputRecord= */ createGenericRecord(
                    Schema.createUnion(
                        Schema.create(Schema.Type.LONG), Schema.create(Schema.Type.NULL)),
                    7L),
                /* expectedStruct= */ createStructWithField(Value.int64(7)),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "NullableString",
                /* inputRecord= */ createGenericRecord(
                    Schema.createUnion(
                        Schema.create(Schema.Type.NULL), Schema.create(Schema.Type.STRING)),
                    NullValues.NULL_STRING),
                /* expectedStruct= */ createStructWithField(Value.string(NullValues.NULL_STRING)),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "NullableStringWithValue",
                /* inputRecord= */ createGenericRecord(
                    Schema.createUnion(
                        Schema.create(Schema.Type.NULL), Schema.create(Schema.Type.STRING)),
                    "stringValue"),
                /* expectedStruct= */ createStructWithField(Value.string("stringValue")),
              })
          // Nullable Types (Union): Logical Types.
          .add(
              new Object[] {
                /* testCaseName= */ "NullableDate",
                /* inputRecord= */ createGenericRecord(
                    Schema.createUnion(
                        Schema.create(Schema.Type.NULL),
                        new Schema.Parser()
                            .parse(
                                """
                                {"type": "int", "logicalType": "date"}""")),
                    NullValues.NULL_INT32),
                /* expectedStruct= */ createStructWithField(Value.date(NullValues.NULL_DATE)),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "NullableDateWithValue",
                /* inputRecord= */ createGenericRecord(
                    Schema.createUnion(
                        Schema.create(Schema.Type.NULL),
                        new Schema.Parser()
                            .parse(
                                """
                                {"type": "int", "logicalType": "date"}""")),
                    7499),
                /* expectedStruct= */ createStructWithField(
                    Value.date(Date.fromYearMonthDay(1990, 7, 14))),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "NullableDecimal",
                /* inputRecord= */ createGenericRecord(
                    Schema.createUnion(
                        Schema.create(Schema.Type.NULL),
                        new Schema.Parser()
                            .parse(
                                """
                                {
                                    "type": "bytes",
                                    "logicalType": "decimal",
                                    "precision": 7,
                                    "scale": 6
                                }""")),
                    NullValues.NULL_BYTES),
                /* expectedStruct= */ createStructWithField(Value.numeric(NullValues.NULL_NUMERIC)),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "NullableDecimalWithValue",
                /* inputRecord= */ createGenericRecord(
                    Schema.createUnion(
                        Schema.create(Schema.Type.NULL),
                        new Schema.Parser()
                            .parse(
                                """
                                {
                                    "type": "bytes",
                                    "logicalType": "decimal",
                                    "precision": 7,
                                    "scale": 6
                                }""")),
                    ByteArray.copyFrom(
                        new Conversions.DecimalConversion()
                            .toBytes(
                                BigDecimal.valueOf(3141592L, 6),
                                new Schema.Parser()
                                    .parse(
                                        """
                                        {
                                            "type": "bytes",
                                            "logicalType": "decimal",
                                            "precision": 7,
                                            "scale": 6
                                        }"""),
                                LogicalTypes.fromSchema(
                                    new Schema.Parser()
                                        .parse(
                                            """
                                            {
                                                "type": "bytes",
                                                "logicalType": "decimal",
                                                "precision": 7,
                                                "scale": 6
                                            }"""))))),
                /* expectedStruct= */ createStructWithField(
                    Value.numeric(BigDecimal.valueOf(3141592, 6))),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "NullableLocalTimestampMillis",
                /* inputRecord= */ createGenericRecord(
                    Schema.createUnion(
                        Schema.create(Schema.Type.NULL),
                        new Schema.Parser()
                            .parse(
                                """
                                {
                                    "type": "long",
                                    "logicalType": "local-timestamp-millis"
                                }""")),
                    NullValues.NULL_INT64),
                /* expectedStruct= */ createStructWithField(
                    Value.timestamp(NullValues.NULL_TIMESTAMP)),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "NullableLocalTimestampMillisWithValue",
                /* inputRecord= */ createGenericRecord(
                    Schema.createUnion(
                        Schema.create(Schema.Type.NULL),
                        new Schema.Parser()
                            .parse(
                                """
                                {
                                    "type": "long",
                                    "logicalType": "local-timestamp-millis"
                                }""")),
                    647917261000L),
                /* expectedStruct= */ createStructWithField(
                    Value.timestamp(Timestamp.ofTimeMicroseconds(647917261000000L))),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "NullableTimestampMillis",
                /* inputRecord= */ createGenericRecord(
                    Schema.createUnion(
                        Schema.create(Schema.Type.NULL),
                        new Schema.Parser()
                            .parse(
                                """
                                {
                                    "type": "long",
                                    "logicalType": "timestamp-millis"
                                }""")),
                    NullValues.NULL_INT64),
                /* expectedStruct= */ createStructWithField(
                    Value.timestamp(NullValues.NULL_TIMESTAMP)),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "NullableTimestampMillisWithValue",
                /* inputRecord= */ createGenericRecord(
                    Schema.createUnion(
                        Schema.create(Schema.Type.NULL),
                        new Schema.Parser()
                            .parse(
                                """
                                {
                                    "type": "long",
                                    "logicalType": "timestamp-millis"
                                }""")),
                    647917261000L),
                /* expectedStruct= */ createStructWithField(
                    Value.timestamp(Timestamp.ofTimeMicroseconds(647917261000000L))),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "NullableLocalTimestampMicros",
                /* inputRecord= */ createGenericRecord(
                    Schema.createUnion(
                        Schema.create(Schema.Type.NULL),
                        new Schema.Parser()
                            .parse(
                                """
                                {
                                    "type": "long",
                                    "logicalType": "local-timestamp-micros"
                                }""")),
                    NullValues.NULL_INT64),
                /* expectedStruct= */ createStructWithField(
                    Value.timestamp(NullValues.NULL_TIMESTAMP)),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "NullableLocalTimestampMicrosWithValue",
                /* inputRecord= */ createGenericRecord(
                    Schema.createUnion(
                        Schema.create(Schema.Type.NULL),
                        new Schema.Parser()
                            .parse(
                                """
                                {
                                    "type": "long",
                                    "logicalType": "local-timestamp-micros"
                                }""")),
                    647917261000000L),
                /* expectedStruct= */ createStructWithField(
                    Value.timestamp(Timestamp.ofTimeMicroseconds(647917261000000L))),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "NullableTimestampMicros",
                /* inputRecord= */ createGenericRecord(
                    Schema.createUnion(
                        Schema.create(Schema.Type.NULL),
                        new Schema.Parser()
                            .parse(
                                """
                                {
                                    "type": "long",
                                    "logicalType": "timestamp-micros"
                                }""")),
                    NullValues.NULL_INT64),
                /* expectedStruct= */ createStructWithField(
                    Value.timestamp(NullValues.NULL_TIMESTAMP)),
              })
          .add(
              new Object[] {
                /* testCaseName= */ "NullableTimestampMicrosWithValue",
                /* inputRecord= */ createGenericRecord(
                    Schema.createUnion(
                        Schema.create(Schema.Type.NULL),
                        new Schema.Parser()
                            .parse(
                                """
                                {
                                    "type": "long",
                                    "logicalType": "timestamp-micros"
                                }""")),
                    647917261000000L),
                /* expectedStruct= */ createStructWithField(
                    Value.timestamp(Timestamp.ofTimeMicroseconds(647917261000000L))),
              })
          .build();
    }
  }

  /** Tests that UnsupportedOperationException is thrown on unsupported field types. */
  @RunWith(Parameterized.class)
  public static final class AvroToStructFnUnsupportedOperationExceptionParameterizedTest {

    private final GenericRecord inputRecord;
    private final String expectedErrorMessage;

    /** Records must be in expected output order. */
    public AvroToStructFnUnsupportedOperationExceptionParameterizedTest(
        String testCaseName, GenericRecord inputRecord, String expectedErrorMessage) {
      this.inputRecord = inputRecord;
      this.expectedErrorMessage = expectedErrorMessage;

      GoogleLogger.forEnclosingClass().atInfo().log("testCase: %s", testCaseName);
    }

    @Test
    public void apply_throwsForUnsupportedOperationException() {
      UnsupportedOperationException thrown =
          assertThrows(
              UnsupportedOperationException.class,
              () -> AvroToStructFn.create().apply(inputRecord));

      assertThat(thrown).hasMessageThat().contains(expectedErrorMessage);
    }

    /** Creates test parameters. */
    @Parameters(name = "{0}")
    public static ImmutableList<Object[]> testingParameters() {
      return ImmutableList.<Object[]>builder()
          .add(
              new Object[] {
                /* testCaseName= */ "Array",
                /* inputRecord= */ createGenericRecord(
                    Schema.createArray(Schema.create(Schema.Type.STRING)),
                    ImmutableList.of("arrayValue")),
                /* expectedErrorMessage= */ "Avro field type ARRAY is not supported.",
              })
          .add(
              new Object[] {
                /* testCaseName= */ "LogicalType_TimeMicros",
                /* inputRecord= */ createGenericRecord(
                    new Schema.Parser()
                        .parse(
                            """
                            {
                                "type": "long",
                                "logicalType": "time-micros"
                            }"""),
                    647917261000000L),
                /* expectedErrorMessage= */ ""
                    + "Avro logical field type time-micros on column testField is not supported.",
              })
          .add(
              new Object[] {
                /* testCaseName= */ "TripleUnion",
                /* inputRecord= */ createGenericRecord(
                    Schema.createUnion(
                        Schema.create(Schema.Type.BOOLEAN),
                        Schema.create(Schema.Type.NULL),
                        Schema.create(Schema.Type.LONG)),
                    Boolean.TRUE),
                /* expectedErrorMessage= */ "UNION is only supported for nullable fields. "
                    + "Got: [\"boolean\", \"null\", \"long\"]",
              })
          .add(
              new Object[] {
                /* testCaseName= */ "NonNullableUnion",
                /* inputRecord= */ createGenericRecord(
                    Schema.createUnion(
                        Schema.create(Schema.Type.BOOLEAN), Schema.create(Schema.Type.DOUBLE)),
                    Boolean.TRUE),
                /* expectedErrorMessage= */ "UNION is only supported for nullable fields. "
                    + "Got: [\"boolean\", \"double\"].",
              })
          .add(
              new Object[] {
                /* testCaseName= */ "DecimalNotByteArray",
                /* inputRecord= */ createGenericRecord(
                    new Schema.Parser()
                        .parse(
                            """
                            {
                                "type": "bytes",
                                "logicalType": "decimal",
                                "precision": 7,
                                "scale": 6
                            }"""),
                    // Using BigDecimal, but any non bytes-like type should throw this exception.
                    BigDecimal.valueOf(3141592L, 6)),
                /* expectedErrorMessage= */ "Unexpected value for decimal: ",
              })
          .build();
    }
  }

  /** Tests the integration of AvroToStructFnTest and AvroIO in a pipeline. * */
  @RunWith(JUnit4.class)
  public static final class IntegrationTests {
    @Rule public final transient TestPipeline pipeline = TestPipeline.create();

    private static final String RESOURCES_DIR = "AvroToStructFnTest/";

    @Test
    public void integrates_withAvroIo() {
      String testFile = Resources.getResource(RESOURCES_DIR + "test_avro_file.avro").getPath();

      PCollection<Struct> output =
          pipeline.apply(AvroIO.parseGenericRecords(AvroToStructFn.create()).from(testFile));

      PAssert.that(output)
          .containsInAnyOrder(
              Struct.newBuilder()
                  .set("boolean_nullable")
                  .to(Boolean.TRUE)
                  .set("boolean_required")
                  .to(Boolean.FALSE)
                  .set("decimal_nullable")
                  .to(BigDecimal.valueOf(14150000000L, 9))
                  .set("decimal_required")
                  .to(BigDecimal.valueOf(16170000000L, 9))
                  .set("float_nullable")
                  .to(1.23)
                  .set("float_required")
                  .to(4.56)
                  .set("integer_nullable")
                  .to(12)
                  .set("integer_required")
                  .to(13)
                  .set("string_nullable")
                  .to("nullable string")
                  .set("string_required")
                  .to("required string")
                  .set("timestamp_nullable")
                  .to(Timestamp.parseTimestamp("2024-01-01T00:00:00Z"))
                  .set("timestamp_required")
                  .to(Timestamp.parseTimestamp("2024-01-01T00:00:00Z"))
                  .build(),
              Struct.newBuilder()
                  .set("boolean_nullable")
                  .to(NullValues.NULL_BOOLEAN)
                  .set("boolean_required")
                  .to(Boolean.TRUE)
                  .set("decimal_nullable")
                  .to(NullValues.NULL_NUMERIC)
                  .set("decimal_required")
                  .to(BigDecimal.valueOf(24250000000L, 9))
                  .set("float_nullable")
                  .to(NullValues.NULL_FLOAT64)
                  .set("float_required")
                  .to(20.21)
                  .set("integer_nullable")
                  .to(NullValues.NULL_INT64)
                  .set("integer_required")
                  .to(22)
                  .set("string_nullable")
                  .to(NullValues.NULL_STRING)
                  .set("string_required")
                  .to("another required string")
                  .set("timestamp_nullable")
                  .to(NullValues.NULL_TIMESTAMP)
                  .set("timestamp_required")
                  .to(Timestamp.parseTimestamp("2024-12-31T23:59:59Z"))
                  .build());

      pipeline.run().waitUntilFinish();
    }
  }
}
