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

import static org.junit.Assert.assertThrows;

import com.google.cloud.solutions.dataflow.kafka2bigquery.kafkautils.KafkaProtoProducerApp.KafkaArgs;
import com.google.cloud.solutions.dataflow.serde.ProtobufSerDe;
import com.google.cloud.solutions.satools.common.testing.TestResourceLoader;
import demo.fraud.FraudEventOuterClass.FraudEvent;
import java.util.List;
import java.util.Properties;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.serialization.StringSerializer;
import org.junit.After;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.testcontainers.kafka.KafkaContainer;

@RunWith(JUnit4.class)
public final class KafkaProtoConsumerTest {

  private static final String KAFKA_TEST_TOPIC = "test-topic";

  @Rule public KafkaContainer kafkaContainer = new KafkaContainer("apache/kafka-native:3.8.1");

  private KafkaArgs kafkaArgs;

  private KafkaProducer<String, FraudEvent> producer;

  @Before
  public void setUp() {
    kafkaContainer.start();

    kafkaArgs =
        new KafkaArgs(
            /* threads= */ 1,
            /* speed= */ 1000,
            /* runDurationMinutes= */ 0,
            kafkaContainer.getBootstrapServers(),
            KAFKA_TEST_TOPIC,
            FraudEvent.class.getName(),
            /* properties= */ null);
    producer = new KafkaProducer<>(getProducerProps());
  }

  @After
  public void tearDown() {
    producer.close();
  }

  @Test
  public void validate_listMatches_noAssertion() {
    // Arrange
    var message =
        TestResourceLoader.classPath()
            .forProto(FraudEvent.class)
            .loadText("fraud_event_random_seed_1_clock_1730472569L.txtpb");
    // send 2 messages
    producer.send(new ProducerRecord<>(KAFKA_TEST_TOPIC, "someThing", message));
    producer.send(new ProducerRecord<>(KAFKA_TEST_TOPIC, "someThing2", message));
    producer.flush();
    // Setup Consumer
    var consumer = new KafkaProtoConsumer<>(kafkaArgs);

    // Act + No Assertion thrown
    consumer.validate(List.of(message, message));
  }

  @Test
  public void validate_listDoesntMatch_assertion() {
    // Arrange
    var message =
        TestResourceLoader.classPath()
            .forProto(FraudEvent.class)
            .loadText("fraud_event_random_seed_1_clock_1730472569L.txtpb");
    // send 2 messages
    producer.send(new ProducerRecord<>(KAFKA_TEST_TOPIC, "someThing", message));
    producer.flush();
    // Setup Consumer
    var consumer = new KafkaProtoConsumer<>(kafkaArgs);

    // Act + Assertion
    assertThrows(AssertionError.class, () -> consumer.validate(List.of(message, message)));
  }

  private Properties getProducerProps() {
    var producerConfig = new Properties();
    producerConfig.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, kafkaArgs.kafkaBootStrapServer());
    producerConfig.put(
        ProducerConfig.CLIENT_ID_CONFIG, "cloud-solutions/kafka-to-bigquery-producer-v1");
    producerConfig.put(
        ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
    producerConfig.put(
        ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG,
        ProtobufSerDe.ProtoSerializer.class.getName());

    return producerConfig;
  }
}
