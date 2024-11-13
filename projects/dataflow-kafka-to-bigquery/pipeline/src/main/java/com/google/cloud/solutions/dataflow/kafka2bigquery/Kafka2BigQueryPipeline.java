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

import static com.google.common.base.Strings.isNullOrEmpty;

import com.google.api.services.bigquery.model.TableRow;
import com.google.common.collect.ImmutableMap;
import com.google.common.io.Resources;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import org.apache.arrow.util.VisibleForTesting;
import org.apache.beam.sdk.Pipeline;
import org.apache.beam.sdk.io.gcp.bigquery.BigQueryIO.Write.CreateDisposition;
import org.apache.beam.sdk.io.gcp.bigquery.BigQueryIO.Write.WriteDisposition;
import org.apache.beam.sdk.io.kafka.KafkaIO;
import org.apache.beam.sdk.options.PipelineOptionsFactory;

/** Dataflow pipeline that writes proto messages from Kafka topic to BigQuery table. */
public final class Kafka2BigQueryPipeline {

  private final Pipeline pipeline;
  private final Kafka2BigQueryOptions options;
  private final BigQueryWriterFactory bigqueryWriterFactory;
  private final ClockFactory clockFactory;

  @VisibleForTesting
  Kafka2BigQueryPipeline(
      Pipeline pipeline,
      Kafka2BigQueryOptions options,
      BigQueryWriterFactory bigqueryWriterFactory,
      ClockFactory clockFactory) {
    this.pipeline = pipeline;
    this.options = options;
    this.bigqueryWriterFactory = bigqueryWriterFactory;
    this.clockFactory = clockFactory;
  }

  public static void main(String[] args) throws Exception {
    var options =
        PipelineOptionsFactory.fromArgs(args).withValidation().as(Kafka2BigQueryOptions.class);
    new Kafka2BigQueryPipeline(
            Pipeline.create(options),
            options,
            new DefaultBigQueryWriterFactory(),
            ClockFactory.systemClockFactory())
        .setup()
        .run();
  }

  @VisibleForTesting
  Pipeline setup() throws IOException {
    options.setAppName("cloud-solutions/dataflow-kafka-to-bigquery-v1");
    options.setUserAgent("cloud-solutions/dataflow-kafka-to-bigquery-v1");

    var parseKafkaXform =
        ParseKafkaMessageTransform.builder()
            .clockFactory(clockFactory)
            .protoClassName(options.getProtoClassName())
            .protoJarPath(options.getProtoJarFile())
            .topic(options.getKafkaTopic())
            .build();

    var messagesTuple =
        pipeline
            .apply(
                "ReadFromKafka",
                KafkaIO.readBytes()
                    .withBootstrapServers(options.getKafkaBootstrapServers())
                    .withTopic(options.getKafkaTopic())
                    .withReadCommitted()
                    .withConsumerConfigUpdates(createKafkaConsumerConfig())
                    .withoutMetadata())
            .apply("ParseMessages", parseKafkaXform);

    // Write messages to main BQ Table
    messagesTuple
        .get(parseKafkaXform.getOutputTag())
        .apply(
            "WriteToBQ",
            bigqueryWriterFactory
                .get(TableRow.class)
                .to(options.getBigQueryTableSpec())
                .withCreateDisposition(CreateDisposition.CREATE_NEVER)
                .withWriteDisposition(WriteDisposition.WRITE_APPEND));

    // Check and write unProcessedBytes messages deadletter BQ Table
    if (!isNullOrEmpty(options.getMismatchedMessageBigQueryTableSpec())) {
      var errorTableSchema =
          Resources.toString(
              Resources.getResource("bigquery_kafkaschemaerror_table_schema.json"),
              StandardCharsets.UTF_8);

      messagesTuple
          .get(parseKafkaXform.getSchemaErrorTag())
          .apply(
              "WriteErrorMessages",
              bigqueryWriterFactory
                  .get(KafkaSchemaError.class)
                  .to(options.getMismatchedMessageBigQueryTableSpec())
                  .withFormatFunction(KafkaSchemaError.bigqueryFormatFunction())
                  .withJsonSchema(errorTableSchema)
                  .withWriteDisposition(WriteDisposition.WRITE_APPEND)
                  .withCreateDisposition(CreateDisposition.CREATE_IF_NEEDED));
    }

    return pipeline;
  }

  private Map<String, Object> createKafkaConsumerConfig() {

    var configBuilder = ImmutableMap.<String, Object>builder();

    if (options.getKafkaConsumerConfigProperties() != null
        && !options.getKafkaConsumerConfigProperties().isEmpty()) {
      configBuilder.putAll(
          StringPropertiesHelper.create(options.getKafkaConsumerConfigProperties()).readAsMap());
    }

    return configBuilder.build();
  }
}
