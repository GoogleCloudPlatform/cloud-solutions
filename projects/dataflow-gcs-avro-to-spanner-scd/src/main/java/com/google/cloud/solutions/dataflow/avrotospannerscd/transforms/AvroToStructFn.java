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

import static com.google.common.base.Preconditions.checkNotNull;

import com.google.cloud.ByteArray;
import com.google.cloud.Date;
import com.google.cloud.Timestamp;
import com.google.cloud.solutions.dataflow.avrotospannerscd.utils.StructHelper.NullValues;
import com.google.cloud.spanner.Struct;
import com.google.cloud.spanner.Value;
import java.nio.ByteBuffer;
import java.time.ZoneId;
import java.util.List;
import org.apache.avro.Conversions;
import org.apache.avro.LogicalTypes;
import org.apache.avro.Schema;
import org.apache.avro.Schema.Field;
import org.apache.avro.data.TimeConversions;
import org.apache.avro.generic.GenericRecord;
import org.apache.beam.sdk.transforms.SimpleFunction;

/** Transforms Avro GenericRecords into Spanner Structs. */
public final class AvroToStructFn extends SimpleFunction<GenericRecord, Struct> {

  public static AvroToStructFn create() {
    return new AvroToStructFn();
  }

  @Override
  public Struct apply(GenericRecord record) {
    return new GenericRecordConverter(record).toStruct();
  }

  /** A GenericRecord to a Struct converter. */
  private record GenericRecordConverter(GenericRecord record) {

    /**
     * Converts a GenericRecord to a Struct.
     *
     * <p>The GenericRecord is converted to a Struct by iterating over the fields and converting
     * each of the fields values and schemas from Avro GenericRecord to Spanner Struct.
     *
     * @return Struct for the GenericRecord with matching data and data types.
     */
    private Struct toStruct() {
      Struct.Builder structBuilder = Struct.newBuilder();
      Schema avroSchema = checkNotNull(record.getSchema(), "Input file Avro Schema is null.");
      avroSchema
          .getFields()
          .forEach(field -> structBuilder.set(field.name()).to(getFieldValue(field)));
      return structBuilder.build();
    }

    private Value getFieldValue(Field field) {
      if (field.schema().getLogicalType() != null) {
        return getLogicalFieldValue(field);
      }

      Schema.Type fieldType = field.schema().getType();
      Object fieldValue = record.get(field.name());

      return switch (fieldType) {
        case BOOLEAN ->
            Value.bool(fieldValue == null ? NullValues.NULL_BOOLEAN : (Boolean) fieldValue);
        case BYTES, FIXED ->
            Value.bytes(fieldValue == null ? NullValues.NULL_BYTES : (ByteArray) fieldValue);
        case DOUBLE ->
            Value.float64(fieldValue == null ? NullValues.NULL_FLOAT64 : (Double) fieldValue);
        case FLOAT ->
            Value.float32(fieldValue == null ? NullValues.NULL_FLOAT32 : (Float) fieldValue);
        case INT ->
            Value.int64(
                fieldValue == null ? NullValues.NULL_INT64 : Long.valueOf((Integer) fieldValue));
        case LONG -> Value.int64(fieldValue == null ? NullValues.NULL_INT64 : (Long) fieldValue);
        case STRING ->
            Value.string(fieldValue == null ? NullValues.NULL_STRING : fieldValue.toString());
        case UNION -> getUnionFieldValue(field);
        default ->
            throw new UnsupportedOperationException(
                String.format("Avro field type %s is not supported.", fieldType));
      };
    }

    private Value getLogicalFieldValue(Field field) {
      String logicalTypeName = field.schema().getLogicalType().getName();
      Object fieldValue = record.get(field.name());

      return switch (logicalTypeName) {
        case "date" ->
            Value.date(
                fieldValue == null
                    ? NullValues.NULL_DATE
                    : Date.fromJavaUtilDate(
                        java.util.Date.from(
                            new TimeConversions.DateConversion()
                                .fromInt(
                                    (Integer) fieldValue,
                                    field.schema(),
                                    LogicalTypes.fromSchema(field.schema()))
                                .atStartOfDay()
                                .atZone(ZoneId.systemDefault())
                                .toInstant())));
        case "decimal" ->
            Value.numeric(
                fieldValue == null
                    ? NullValues.NULL_NUMERIC
                    : new Conversions.DecimalConversion()
                        .fromBytes(
                            convertToByteBuffer(fieldValue),
                            field.schema(),
                            LogicalTypes.fromSchema(field.schema())));
        case "local-timestamp-millis", "timestamp-millis" ->
            Value.timestamp(
                fieldValue == null
                    ? NullValues.NULL_TIMESTAMP
                    : Timestamp.ofTimeMicroseconds(
                        new TimeConversions.TimestampMillisConversion()
                                .fromLong(
                                    (Long) fieldValue,
                                    field.schema(),
                                    LogicalTypes.fromSchema(field.schema()))
                                .toEpochMilli()
                            * 1000L));
        case "local-timestamp-micros", "timestamp-micros" ->
            Value.timestamp(
                fieldValue == null
                    ? NullValues.NULL_TIMESTAMP
                    : Timestamp.ofTimeMicroseconds(
                        new TimeConversions.TimestampMicrosConversion()
                                .fromLong(
                                    (Long) fieldValue,
                                    field.schema(),
                                    LogicalTypes.fromSchema(field.schema()))
                                .toEpochMilli()
                            * 1000L));
        // case "duration", "time-micros", "time-millis", "uuid"
        default ->
            throw new UnsupportedOperationException(
                String.format(
                    "Avro logical field type %s on column %s is not supported.",
                    logicalTypeName, field.name()));
      };
    }

    private static ByteBuffer convertToByteBuffer(Object fieldValue) {
      return switch (fieldValue) {
        case ByteBuffer byteBufferValue -> byteBufferValue;
        case ByteArray byteArrayValue -> ByteBuffer.wrap(byteArrayValue.toByteArray());
        case byte[] bytes -> ByteBuffer.wrap(bytes);
        default ->
            throw new UnsupportedOperationException("Unexpected value for decimal: " + fieldValue);
      };
    }

    private Value getUnionFieldValue(Field field) {
      List<Schema> unionTypes = field.schema().getTypes();
      if (unionTypes.size() != 2) {
        throw new UnsupportedOperationException(
            String.format("UNION is only supported for nullable fields. Got: %s.", unionTypes));
      }

      // It is not possible to have UNION of same type (e.g. NULL, NULL).
      if (unionTypes.get(0).getType() == Schema.Type.NULL) {
        return getFieldValue(new Field(field.name(), unionTypes.get(1), field.doc()));
      }
      if (unionTypes.get(1).getType() == Schema.Type.NULL) {
        return getFieldValue(new Field(field.name(), unionTypes.get(0), field.doc()));
      }

      throw new UnsupportedOperationException(
          String.format("UNION is only supported for nullable fields. Got: %s.", unionTypes));
    }
  }
}
