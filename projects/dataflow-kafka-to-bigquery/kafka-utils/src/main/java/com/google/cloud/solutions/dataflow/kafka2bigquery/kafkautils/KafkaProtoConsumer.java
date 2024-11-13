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

package com.google.cloud.solutions.dataflow.kafka2bigquery.kafkautils;

import static com.google.common.truth.Truth.assertThat;

import com.google.cloud.solutions.dataflow.kafka2bigquery.kafkautils.KafkaProtoProducerApp.KafkaArgs;
import com.google.cloud.solutions.dataflow.serde.ProtobufSerDe;
import com.google.cloud.solutions.dataflow.serde.ProtobufSerDe.ProtoDeserializer;
import com.google.common.annotations.VisibleForTesting;
import com.google.common.collect.ImmutableMap;
import com.google.common.flogger.GoogleLogger;
import com.google.protobuf.Message;
import java.time.Duration;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Map;
import java.util.stream.StreamSupport;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.common.serialization.StringDeserializer;

/** Thread runner to generate and send messages on Kafka. */
public final class KafkaProtoConsumer<T extends Message> extends BaseKafkaClient<T> {

  private static final GoogleLogger logger = GoogleLogger.forEnclosingClass();

  private KafkaConsumer<String, T> consumer;

  @VisibleForTesting boolean isClosed;

  private static final DateTimeFormatter TS_FORMATTER = DateTimeFormatter.ISO_INSTANT;

  /**
   * Creates new Kafka consumer client to consume proto messages and then assert against expected
   * messages.
   *
   * @param kafkaArgs the details of Kafka configuration.
   */
  public KafkaProtoConsumer(KafkaArgs kafkaArgs) {
    super(kafkaArgs);
    this.isClosed = false;
  }

  protected Map<String, Object> createKafkaProperties() {
    var consumerConfig = ImmutableMap.<String, Object>builder();
    if (kafkaArgs.kafkaBootStrapServer() != null) {
      consumerConfig.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, kafkaArgs.kafkaBootStrapServer());
    }
    consumerConfig.put(
        ConsumerConfig.CLIENT_ID_CONFIG,
        "consumer" + "cloud-solutions/kafka-to-bigquery-producer-v1");
    consumerConfig.put(ConsumerConfig.GROUP_ID_CONFIG, "1");
    consumerConfig.put(
        ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
    consumerConfig.put(
        ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG,
        ProtobufSerDe.ProtoDeserializer.class.getName());
    consumerConfig.put(
        ProtoDeserializer.DESERIALIZER_PROTO_CLASS_NAME_CONFIG, kafkaArgs.protoClassName());
    consumerConfig.put("auto.offset.reset", "earliest");

    return consumerConfig.build();
  }

  /** Asserts that Kafka received messages match the expected records. */
  public void validate(List<T> expectedRecords) {
    assertThat(receiveKafkaRecords()).containsExactlyElementsIn(expectedRecords);
  }

  /** Checks the actualRecords against records received from Kafka. */
  public void validateAgainstKafka(List<T> actualRecords) {
    assertThat(actualRecords).containsExactlyElementsIn(receiveKafkaRecords());
  }

  private List<T> receiveKafkaRecords() {
    try (var consumer = new KafkaConsumer<String, T>(createClientProperties())) {
      consumer.subscribe(List.of(kafkaArgs.topic()));
      var recordsIterator = consumer.poll(Duration.ofSeconds(1));

      return StreamSupport.stream(recordsIterator.records(kafkaArgs.topic()).spliterator(), true)
          .map(ConsumerRecord::value)
          .toList();
    }
  }
}
