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

import com.google.cloud.ByteArray;
import com.google.cloud.Date;
import com.google.cloud.Timestamp;
import com.google.cloud.spanner.Key;
import com.google.cloud.spanner.Mutation;
import com.google.cloud.spanner.Struct;
import com.google.cloud.spanner.Type;
import com.google.cloud.spanner.Type.StructField;
import com.google.cloud.spanner.Value;
import java.io.Serializable;
import java.math.BigDecimal;
import java.util.Comparator;
import java.util.HashMap;
import java.util.concurrent.atomic.AtomicBoolean;
import javax.annotation.Nullable;

/** Provides functionality to interact with Struct values. */
public record StructHelper(Struct struct) {

  public static StructHelper of(Struct struct) {
    return new StructHelper(struct);
  }

  /**
   * Removes a field from the Struct.
   *
   * <p>If the field does not exist, ignores it.
   *
   * @param fieldName Field that should be removed.
   * @return StructHelper with the updated Struct.
   */
  public StructHelper withoutField(String fieldName) {
    Struct.Builder recordBuilder = makeStructBuilderWithoutField(fieldName);
    return StructHelper.of(recordBuilder.build());
  }

  /**
   * Adds or updates a field in the Struct.
   *
   * <p>If the field exist, updates it. Otherwise, it adds it.
   *
   * @param fieldName Field that should be added or updated.
   * @return StructHelper with the updated Struct.
   */
  public StructHelper withUpdatedFieldValue(String fieldName, Value value) {
    Struct.Builder recordBuilder = Struct.newBuilder();
    AtomicBoolean updatedField = new AtomicBoolean(false);
    struct.getType().getStructFields().stream()
        .forEach(
            field -> {
              recordBuilder
                  .set(field.getName())
                  .to(field.getName().equals(fieldName) ? value : struct.getValue(field.getName()));
              if (field.getName().equals(fieldName)) {
                updatedField.set(true);
              }
            });
    // The field may not already exist in the Struct. If that's the case, we add it as a new field.
    if (!updatedField.get()) {
      recordBuilder.set(fieldName).to(value);
    }
    return StructHelper.of(recordBuilder.build());
  }

  private Struct.Builder makeStructBuilderWithoutField(String fieldName) {
    Struct.Builder recordBuilder = Struct.newBuilder();
    struct.getType().getStructFields().stream()
        .filter(field -> !field.getName().equals(fieldName))
        .forEach(field -> recordBuilder.set(field.getName()).to(struct.getValue(field.getName())));
    return recordBuilder;
  }

  public KeyMaker keyMaker(Iterable<String> primaryKeyColumnNames) {
    return new KeyMaker(primaryKeyColumnNames);
  }

  public MutationCreator mutationCreator(String tableName, Iterable<String> primaryKeyColumnNames) {
    return new MutationCreator(tableName, primaryKeyColumnNames);
  }

  /** Creates Keys for Structs. */
  public final class KeyMaker {

    private final Iterable<String> primaryKeyColumnNames;

    /**
     * Initializes KeyMaker with primary key column names, which will be added to the key.
     *
     * @param primaryKeyColumnNames List of primary key column names.
     */
    private KeyMaker(Iterable<String> primaryKeyColumnNames) {
      this.primaryKeyColumnNames = primaryKeyColumnNames;
    }

    /**
     * Generates the Key for a given record using the primary key column names.
     *
     * @return Primary Key for the record.
     */
    public Key createKey() {
      Key.Builder keyBuilder = Key.newBuilder();
      addRecordFieldsToKeyBuilder(primaryKeyColumnNames, keyBuilder);
      return keyBuilder.build();
    }

    /**
     * Creates the Key and casts to string format.
     *
     * <p>Useful in cases where there is need for a deterministic coder. Key does not provide this
     * guarantee.
     *
     * @return Record Key in string format.
     */
    public String createKeyString() {
      return createKey().toString();
    }

    /**
     * Adds struct values to the Key builder for the requested column names.
     *
     * <p>Used to generate Keys for records.
     *
     * @param columnNames to add to the Key.
     * @param keyBuilder Key Builder where key will be created.
     */
    private void addRecordFieldsToKeyBuilder(Iterable<String> columnNames, Key.Builder keyBuilder) {
      HashMap<String, StructField> structFieldMap = new HashMap<>();
      struct()
          .getType()
          .getStructFields()
          .forEach(field -> structFieldMap.put(field.getName(), field));

      columnNames.forEach(
          columnName -> {
            StructField field = structFieldMap.get(columnName);
            if (field == null) {
              throw new RuntimeException(
                  String.format(
                      "Primary key name %s not found in record. Unable to create Key.",
                      columnName));
            }

            Value fieldValue = struct().getValue(field.getName());
            addValueToKeyBuilder(keyBuilder, fieldValue);
          });
    }

    private void addValueToKeyBuilder(Key.Builder keyBuilder, Value fieldValue) {
      Type fieldType = fieldValue.getType();

      switch (fieldType.getCode()) {
        case BOOL:
          keyBuilder.append(ValueHelper.of(fieldValue).getBoolOrNull());
          break;
        case BYTES:
          keyBuilder.append(ValueHelper.of(fieldValue).getBytesOrNull());
          break;
        case DATE:
          keyBuilder.append(ValueHelper.of(fieldValue).getDateOrNull());
          break;
        case FLOAT32:
          keyBuilder.append(ValueHelper.of(fieldValue).getFloat32OrNull());
          break;
        case FLOAT64:
          keyBuilder.append(ValueHelper.of(fieldValue).getFloat64OrNull());
          break;
        case INT64:
          keyBuilder.append(ValueHelper.of(fieldValue).getInt64OrNull());
          break;
        case JSON:
          keyBuilder.append(ValueHelper.of(fieldValue).getJsonOrNull());
          break;
        case NUMERIC:
        case PG_NUMERIC:
          keyBuilder.append(ValueHelper.of(fieldValue).getNumericOrNull());
          break;
        case PG_JSONB:
          keyBuilder.append(ValueHelper.of(fieldValue).getPgJsonbOrNull());
          break;
        case STRING:
          keyBuilder.append(ValueHelper.of(fieldValue).getStringOrNull());
          break;
        case TIMESTAMP:
          keyBuilder.append(ValueHelper.of(fieldValue).getTimestampOrNull());
          break;
        default:
          throw new UnsupportedOperationException(
              String.format("Unsupported Spanner field type %s.", fieldType.getCode()));
      }
    }
  }

  /** Value types with null values. */
  public static class NullValues {
    public static final Boolean NULL_BOOLEAN = null;
    public static final ByteArray NULL_BYTES = null;
    public static final Date NULL_DATE = null;
    public static final Float NULL_FLOAT32 = null;
    public static final Double NULL_FLOAT64 = null;
    public static final Integer NULL_INT32 = null;
    public static final Long NULL_INT64 = null;
    public static final String NULL_JSON = null;
    public static final BigDecimal NULL_NUMERIC = null;
    public static final String NULL_STRING = null;
    public static final Timestamp NULL_TIMESTAMP = null;
  }

  /** Provides functionality to get and work with Values for Structs. */
  private record ValueHelper(Value value) {

    /**
     * Initializes ValueHelper with a Value.
     *
     * @param value Value for which to create ValueHelper.
     */
    static ValueHelper of(Value value) {
      return new ValueHelper(value);
    }

    Boolean getBoolOrNull() {
      return value.isNull()
          ? StructHelper.NullValues.NULL_BOOLEAN
          : Boolean.valueOf(value.getBool());
    }

    ByteArray getBytesOrNull() {
      return value.isNull() ? StructHelper.NullValues.NULL_BYTES : value.getBytes();
    }

    Date getDateOrNull() {
      return value.isNull() ? StructHelper.NullValues.NULL_DATE : value.getDate();
    }

    Float getFloat32OrNull() {
      return value.isNull()
          ? StructHelper.NullValues.NULL_FLOAT32
          : Float.valueOf(value.getFloat32());
    }

    Double getFloat64OrNull() {
      return value.isNull()
          ? StructHelper.NullValues.NULL_FLOAT64
          : Double.valueOf(value.getFloat64());
    }

    Long getInt64OrNull() {
      return value.isNull() ? StructHelper.NullValues.NULL_INT64 : Long.valueOf(value.getInt64());
    }

    String getJsonOrNull() {
      return value.isNull() ? StructHelper.NullValues.NULL_JSON : value.getJson();
    }

    BigDecimal getNumericOrNull() {
      return value.isNull() ? StructHelper.NullValues.NULL_NUMERIC : value.getNumeric();
    }

    String getPgJsonbOrNull() {
      return value.isNull() ? StructHelper.NullValues.NULL_JSON : value.getPgJsonb();
    }

    String getStringOrNull() {
      return value.isNull() ? StructHelper.NullValues.NULL_STRING : value.getString();
    }

    Timestamp getTimestampOrNull() {
      return value.isNull() ? StructHelper.NullValues.NULL_TIMESTAMP : value.getTimestamp();
    }
  }

  /**
   * Compares two Spanner Structs based on the data type of the selected column.
   *
   * <p>In the context of this Comparator, a Struct is a Spanner record - i.e. a collection of
   * columns and their values. One of those columns will be used to compare the records.
   */
  public static final class StructComparator implements Comparator<Struct>, Serializable {

    private final String orderByColumnName;
    private final SortOrder sortOrder;

    public enum SortOrder {
      ASC,
      DESC;
    }

    private StructComparator(String orderByColumnName, SortOrder sortOrder) {
      this.orderByColumnName = orderByColumnName;
      this.sortOrder = sortOrder;
    }

    /** Returns a new StructComparator that compares orderByColumnName in ASC order. */
    public static StructComparator create(String orderByColumnName) {
      return create(orderByColumnName, SortOrder.ASC);
    }

    /** Returns a new StructComparator that compares orderByColumnName in given sort order. */
    public static StructComparator create(String orderByColumnName, @Nullable SortOrder sortOrder) {
      if (sortOrder == null) {
        return StructComparator.create(orderByColumnName);
      }

      return new StructComparator(orderByColumnName, sortOrder);
    }

    /** Creates the StructComparator, which will return the reverse of the natural ordering. */
    @Override
    public Comparator<Struct> reversed() {
      return new StructComparator(this.orderByColumnName, SortOrder.DESC);
    }

    /**
     * {@inheritDoc}
     *
     * <p>Nulls are sorted first, following SQL behaviour.
     *
     * <p>Order is reversed when called with reversed().
     */
    @Override
    public int compare(Struct leftStruct, Struct rightStruct) {
      return naturalCompare(leftStruct, rightStruct) * (sortOrder.equals(SortOrder.DESC) ? -1 : 1);
    }

    private int naturalCompare(Struct leftStruct, Struct rightStruct) {
      Value leftValue = leftStruct.getValue(orderByColumnName);
      Value rightValue = rightStruct.getValue(orderByColumnName);

      // Sort NULL first (ASC), following SQL behaviour.
      if (leftValue.isNull() && rightValue.isNull()) {
        return 0;
      } else if (leftValue.isNull()) {
        return -1;
      } else if (rightValue.isNull()) {
        return 1;
      }

      return switch (leftValue.getType().getCode()) {
        case BOOL ->
            ValueHelper.of(leftValue)
                .getBoolOrNull()
                .compareTo(ValueHelper.of(rightValue).getBoolOrNull());
        case BYTES ->
            throw new RuntimeException(
                String.format("Unable to sort by ByteArray field %s.", orderByColumnName));
        case DATE ->
            ValueHelper.of(leftValue)
                .getDateOrNull()
                .compareTo(ValueHelper.of(rightValue).getDateOrNull());
        case FLOAT32 ->
            ValueHelper.of(leftValue)
                .getFloat32OrNull()
                .compareTo(ValueHelper.of(rightValue).getFloat32OrNull());
        case FLOAT64 ->
            ValueHelper.of(leftValue)
                .getFloat64OrNull()
                .compareTo(ValueHelper.of(rightValue).getFloat64OrNull());
        case INT64 ->
            ValueHelper.of(leftValue)
                .getInt64OrNull()
                .compareTo(ValueHelper.of(rightValue).getInt64OrNull());
        case JSON ->
            ValueHelper.of(leftValue)
                .getJsonOrNull()
                .compareTo(ValueHelper.of(rightValue).getJsonOrNull());
        case NUMERIC, PG_NUMERIC ->
            ValueHelper.of(leftValue)
                .getNumericOrNull()
                .compareTo(ValueHelper.of(rightValue).getNumericOrNull());
        case PG_JSONB ->
            ValueHelper.of(leftValue)
                .getPgJsonbOrNull()
                .compareTo(ValueHelper.of(rightValue).getPgJsonbOrNull());
        case STRING ->
            ValueHelper.of(leftValue)
                .getStringOrNull()
                .compareTo(ValueHelper.of(rightValue).getStringOrNull());
        case TIMESTAMP ->
            ValueHelper.of(leftValue)
                .getTimestampOrNull()
                .compareTo(ValueHelper.of(rightValue).getTimestampOrNull());
        default ->
            throw new UnsupportedOperationException(
                String.format("Unsupported Spanner field type %s.", leftValue.getType().getCode()));
      };
    }
  }

  /** Creates Spanner mutations for the Struct and given tables. */
  public final class MutationCreator {

    private String tableName;
    private Iterable<String> primaryKeyColumnNames;

    private MutationCreator(String tableName, Iterable<String> primaryKeyColumnNames) {
      this.tableName = tableName;
      this.primaryKeyColumnNames = primaryKeyColumnNames;
    }

    /** Creates an insert mutation for the given Struct and table name. */
    public Mutation createInsertMutation() {
      Mutation.WriteBuilder insertMutationBuilder = Mutation.newInsertBuilder(tableName);
      struct
          .getType()
          .getStructFields()
          .forEach(
              field ->
                  insertMutationBuilder.set(field.getName()).to(struct.getValue(field.getName())));
      return insertMutationBuilder.build();
    }

    /** Creates an upsert (insertOrUpdate) mutation for the given Struct and table name. */
    public Mutation createUpsertMutation() {
      Mutation.WriteBuilder upsertMutationBuilder = Mutation.newInsertOrUpdateBuilder(tableName);
      struct
          .getType()
          .getStructFields()
          .forEach(
              field ->
                  upsertMutationBuilder.set(field.getName()).to(struct.getValue(field.getName())));
      return upsertMutationBuilder.build();
    }

    /** Creates a deletion mutation for the existing given Struct and table name. */
    public Mutation createDeleteMutation() {
      Key recordKey = StructHelper.of(struct).keyMaker(primaryKeyColumnNames).createKey();
      return Mutation.delete(tableName, recordKey);
    }
  }
}
