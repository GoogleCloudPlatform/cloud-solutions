package com.google.cloud.solutions.dataflow.avrotospannerscd.testing;

import com.google.cloud.spanner.Struct;
import com.google.cloud.spanner.Value;
import com.google.common.collect.ImmutableList;
import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;
import java.util.stream.IntStream;
import org.apache.avro.Schema;
import org.apache.avro.Schema.Field;
import org.apache.avro.generic.GenericRecord;
import org.apache.avro.generic.GenericRecordBuilder;

/** Creates sample data for testing, including GenericRecords and Structs. */
public class TestSampleCreator {

  /** Creates a GenericRecord with one field with the provided field schema and value. */
  public static GenericRecord createGenericRecord(Schema fieldSchema, Object fieldValue) {
    return new GenericRecordBuilder(
            Schema.createRecord(
                /* name= */ "testRecord",
                /* doc= */ null,
                /* namespace= */ null,
                /* isError= */ false,
                ImmutableList.<Field>builder().add(new Field("testField", fieldSchema)).build()))
        .set("testField", fieldValue)
        .build();
  }

  /** Creates a list of Structs of given sample size. */
  public static List<Struct> createStructSamples(int sampleSize) {
    return IntStream.range(0, sampleSize)
        .boxed()
        .map(i -> TestSampleCreator.createSimpleStruct())
        .collect(Collectors.toList());
  }

  /** Creates a simple Struct with one field set to a given value. */
  private static Struct createStructWithField(String fieldName, Value fieldValue) {
    return Struct.newBuilder().set(fieldName).to(fieldValue).build();
  }

  /** Creates a simple Struct with one field (testField) set to a given value. */
  public static Struct createStructWithField(Value fieldValue) {
    return createStructWithField("testField", fieldValue);
  }

  /** Creates a simple Struct with one field (id) set to a unique value. */
  public static Struct createSimpleStruct() {
    return createStructWithField("id", Value.string(UUID.randomUUID().toString()));
  }
}
