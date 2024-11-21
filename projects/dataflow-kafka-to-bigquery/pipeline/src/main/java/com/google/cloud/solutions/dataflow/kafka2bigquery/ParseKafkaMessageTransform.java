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

package com.google.cloud.solutions.dataflow.kafka2bigquery;

import com.google.api.services.bigquery.model.TableRow;
import com.google.auto.value.AutoValue;
import com.google.cloud.solutions.dataflow.serde.ProtobufSerDe.ProtoDeserializer;
import com.google.common.flogger.GoogleLogger;
import com.google.common.flogger.StackSize;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.protobuf.Message;
import com.google.protobuf.util.JsonFormat;
import java.time.format.DateTimeFormatter;
import java.util.List;
import org.apache.beam.sdk.coders.SerializableCoder;
import org.apache.beam.sdk.io.gcp.bigquery.TableRowJsonCoder;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.PCollectionTuple;
import org.apache.beam.sdk.values.TupleTag;
import org.apache.beam.sdk.values.TupleTagList;
import org.checkerframework.checker.nullness.qual.NonNull;

/**
 * Parses the protobuf message from Kafka Record.
 *
 * <p>If the parsed message contains {@link Message#getUnknownFields()}, if then emits the cleaned
 * message with unknown fields, along with {@link KafkaSchemaError} message.
 */
@AutoValue
public abstract class ParseKafkaMessageTransform
    extends PTransform<@NonNull PCollection<KV<byte[], byte[]>>, @NonNull PCollectionTuple> {

  abstract String topic();

  abstract String protoClassName();

  abstract String protoJarPath();

  abstract ClockFactory clockFactory();

  public static ParseKafkaMessageTransform.Builder builder() {
    return new AutoValue_ParseKafkaMessageTransform.Builder();
  }

  @AutoValue.Builder
  public abstract static class Builder {

    public abstract Builder topic(String topic);

    public abstract Builder protoClassName(String protoClassName);

    public abstract Builder protoJarPath(String protoJarPath);

    public abstract Builder clockFactory(ClockFactory clockFactory);

    public abstract ParseKafkaMessageTransform build();
  }

  private final TupleTag<TableRow> outputTag = new TupleTag<>();
  private final TupleTag<KafkaSchemaError> schemaErrorTag = new TupleTag<>();

  public TupleTag<KafkaSchemaError> getSchemaErrorTag() {
    return schemaErrorTag;
  }

  public TupleTag<TableRow> getOutputTag() {
    return outputTag;
  }

  @Override
  @NonNull
  public PCollectionTuple expand(@NonNull PCollection<KV<byte[], byte[]>> input) {

    // Verify the class is valid during pipeline setup process.
    DynamicClassLoader.from(protoJarPath()).loadClass(protoClassName(), Message.class);

    var messageAndSchemaTuple =
        input.apply(
            "ReadKafkaRecord",
            ParDo.of(
                    new ParseKafkaProtoMessageFn(
                        topic(), protoClassName(), protoJarPath(), clockFactory(), schemaErrorTag))
                .withOutputTags(outputTag, TupleTagList.of(schemaErrorTag)));

    messageAndSchemaTuple.get(outputTag).setCoder(TableRowJsonCoder.of());
    messageAndSchemaTuple
        .get(schemaErrorTag)
        .setCoder(SerializableCoder.of(KafkaSchemaError.class));

    return messageAndSchemaTuple;
  }

  private static final class ParseKafkaProtoMessageFn extends DoFn<KV<byte[], byte[]>, TableRow> {

    private static final GoogleLogger logger = GoogleLogger.forEnclosingClass();

    private final String topic;

    private final String protoClassName;

    private final DynamicClassLoader dynamicClassLoader;

    private final ClockFactory clockFactory;

    private final TupleTag<KafkaSchemaError> schemaErrorTupleTag;

    private transient Class<Message> messageClass;
    private transient ProtoDeserializer protoDeserializer;
    private transient Gson gson;

    public ParseKafkaProtoMessageFn(
        String topic,
        String protoClassName,
        String protoJarPath,
        ClockFactory clockFactory,
        TupleTag<KafkaSchemaError> schemaErrorTupleTag) {
      this.topic = topic;
      this.protoClassName = protoClassName;
      this.dynamicClassLoader = DynamicClassLoader.from(protoJarPath);
      this.clockFactory = clockFactory;
      this.schemaErrorTupleTag = schemaErrorTupleTag;
    }

    @Setup
    public void createDeserializers() {
      var messageClass = dynamicClassLoader.loadClass(protoClassName, Message.class);
      protoDeserializer = new ProtoDeserializer(messageClass);
      gson = new GsonBuilder().setLenient().create();
    }

    @Teardown
    public void stopStringDeserializer() {
      if (protoDeserializer != null) {
        protoDeserializer.close();
      }
    }

    @ProcessElement
    public void convertMessage(
        @Element KV<byte[], byte[]> kafkaRecord, ProcessContext processContext) {
      new ProcessKafkaElement(kafkaRecord, processContext).processElement();
    }

    /** Process given proto bytes, inner class to improve structure. */
    private final class ProcessKafkaElement {

      private final KV<byte[], byte[]> kafkaRecord;
      private final ProcessContext processContext;

      public ProcessKafkaElement(KV<byte[], byte[]> kafkaRecord, ProcessContext processContext) {
        this.kafkaRecord = kafkaRecord;
        this.processContext = processContext;
      }

      private void sendSchemaError() {
        sendSchemaError(/* unknownFields= */ null);
      }

      private void sendSchemaError(List<Integer> unknownFields) {
        var schemaErrorBuilder =
            KafkaSchemaError.builder()
                .topic(topic)
                .timestamp(DateTimeFormatter.ISO_INSTANT.format(clockFactory.getClock().instant()))
                .rawKey(kafkaRecord.getKey())
                .rawMessage(kafkaRecord.getValue());

        if (unknownFields != null && !unknownFields.isEmpty()) {
          schemaErrorBuilder.unknownFieldIds(unknownFields);
        }

        processContext.output(schemaErrorTupleTag, schemaErrorBuilder.build());
      }

      private void processElement() {
        try {
          var rawMessage = kafkaRecord.getValue();
          var parsedMessage = protoDeserializer.deserialize(topic, rawMessage);

          var messageJson =
              JsonFormat.printer()
                  .includingDefaultValueFields()
                  .preservingProtoFieldNames()
                  .print(parsedMessage);

          var tableRow = gson.fromJson(messageJson, TableRow.class);

          processContext.output(tableRow);

          var unknownFields = parsedMessage.getUnknownFields().asMap().keySet().stream().toList();
          if (!unknownFields.isEmpty()) {
            sendSchemaError(unknownFields);
          }
        } catch (Exception exp) {
          logger.atSevere().withStackTrace(StackSize.NONE).withCause(exp).log(
              "Error processing proto message");
          sendSchemaError();
        }
      }
    }
  }
}
