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

import com.google.cloud.solutions.dataflow.kafka2bigquery.kafkautils.KafkaProtoProducerApp.KafkaArgs;
import com.google.cloud.solutions.dataflow.protofn.FraudEventCreatorFnFactory;
import com.google.cloud.solutions.satools.common.testing.TestResourceLoader;
import demo.fraud.FraudEventOuterClass.FraudEvent;
import java.util.List;
import java.util.Properties;
import java.util.function.Function;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.Parameterized;
import org.junit.runners.Parameterized.Parameters;
import org.testcontainers.kafka.KafkaContainer;
import org.testcontainers.shaded.com.google.common.collect.ImmutableList;

/** Unit test class for KafkaProducer. */
@RunWith(Parameterized.class)
public final class KafkaProtoProducerTest {
  private static final String KAFKA_TEST_TOPIC = "test-topic";

  @Rule public KafkaContainer kafka = new KafkaContainer("apache/kafka-native:3.8.1");

  private final Function<String, KafkaArgs> producerArgsFn;

  private KafkaProtoConsumer<FraudEvent> consumer;

  public KafkaProtoProducerTest(String testName, Function<String, KafkaArgs> producerArgsFn) {
    this.producerArgsFn = producerArgsFn;
  }

  @Before
  public void setUpKafka() {
    kafka.start();
  }

  @Test
  public void run_preClosed_submitsOneMessage() {
    // Arrange
    var producerArgs = producerArgsFn.apply(kafka.getBootstrapServers());

    var fnFactory = new FraudEventCreatorFnFactory.TestFraudEventCreatorFnFactory();

    consumer = new KafkaProtoConsumer<>(producerArgs);
    try (var producer =
        new KafkaProtoProducer<>(
            /* int= */ 1,
            /* kafkaArgs= */ producerArgs,
            /* messageGenFn= */ fnFactory.fixedListEventsFn(
                List.of(
                    TestResourceLoader.classPath()
                        .forProto(FraudEvent.class)
                        .loadText("fraud_event_random_seed_1_clock_1730472569L.txtpb"))),
            producerArgs.sendBatchSize())) {
      producer.init();

      // Act
      producer.run();

      // Assert
      consumer.validate(
          List.of(
              TestResourceLoader.classPath()
                  .forProto(FraudEvent.class)
                  .loadText("fraud_event_random_seed_1_clock_1730472569L.txtpb")));
    }
  }

  @Parameters(name = "{0}")
  public static ImmutableList<Object[]> testParameters() {
    return ImmutableList.<Object[]>builder()
        .add(
            new Object[] {
              "BootStrapServer in main args",
              (Function<String, KafkaArgs>)
                  bootStrapSevers ->
                      new KafkaArgs(
                          /* threads= */ 1,
                          /* speed= */ 1000,
                          /* runDurationMinutes= */ 0,
                          bootStrapSevers,
                          KAFKA_TEST_TOPIC,
                          FraudEvent.class.getName(),
                          null)
            })
        .add(
            new Object[] {
              "BootStrap Server in properties",
              (Function<String, KafkaArgs>)
                  bootStrapSevers -> {
                    var properties = new Properties();
                    properties.put("bootstrap.servers", bootStrapSevers);

                    return new KafkaArgs(
                        /* threads= */ 1,
                        /* speed= */ 1000,
                        /* runDurationMinutes= */ 0,
                        null,
                        KAFKA_TEST_TOPIC,
                        FraudEvent.class.getName(),
                        properties);
                  }
            })
        .build();
  }
}
