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
import com.google.cloud.solutions.dataflow.serde.ProtobufSerDe;
import com.google.common.annotations.VisibleForTesting;
import com.google.common.collect.ImmutableMap;
import com.google.common.flogger.GoogleLogger;
import com.google.protobuf.Message;
import java.util.Map;
import java.util.NoSuchElementException;
import java.util.function.Function;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.serialization.StringSerializer;

/** Thread runner to generate and send messages on Kafka. */
public final class KafkaProtoProducer<T extends Message> extends BaseKafkaClient<T>
    implements Runnable, AutoCloseable {

  private static final GoogleLogger logger = GoogleLogger.forEnclosingClass();

  public static final int DEFAULT_SEND_BATCH_SIZE = 20;

  private final int threadNumber;
  private final Function<Long, T> messageGenFn;
  private final String topic;
  private final int sendBatchSize;

  private long itemCount;
  private KafkaProducer<String, T> producer;

  @VisibleForTesting volatile boolean isClosed;

  /**
   * Creates a new Kafka producer client.
   *
   * <p>Publishes proto messages created by {@code messageGenFn} to the kafka topic.
   *
   * @param threadNumber the id of this worker.
   * @param kafkaArgs the details of Kafka configuration.
   * @param messageGenFn the Function that generates new Proto messages to send.
   * @param sendBatchSize the number of messages to send as single commit to Kafka.
   */
  public KafkaProtoProducer(
      int threadNumber, KafkaArgs kafkaArgs, Function<Long, T> messageGenFn, int sendBatchSize) {
    super(kafkaArgs);
    this.threadNumber = threadNumber;
    this.messageGenFn = messageGenFn;
    this.topic = kafkaArgs.topic();
    this.sendBatchSize = sendBatchSize;
    this.itemCount = 1L;
    this.isClosed = false;
  }

  @Override
  public void close() {
    isClosed = true;
    if (producer != null) {
      producer.flush();
      producer.close();
    }
  }

  protected Map<String, Object> createKafkaProperties() {
    var producerConfig = ImmutableMap.<String, Object>builder();
    if (kafkaArgs.kafkaBootStrapServer() != null) {
      producerConfig.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, kafkaArgs.kafkaBootStrapServer());
    }
    producerConfig.put(
        ProducerConfig.CLIENT_ID_CONFIG,
        threadNumber + "cloud-solutions/kafka-to-bigquery-producer-v1");
    producerConfig.put(
        ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
    producerConfig.put(
        ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG,
        ProtobufSerDe.ProtoSerializer.class.getName());

    return producerConfig.build();
  }

  public void init() {
    this.producer = createProducer();
  }

  private KafkaProducer<String, T> createProducer() {
    return new KafkaProducer<>(createClientProperties());
  }

  /** Sends a single message. */
  public void send(T message) {
    if (message == null) {
      logger.atInfo().log("Skip Sending message: null");
      return;
    }

    var key = threadNumber + "-" + itemCount++;
    producer.send(new ProducerRecord<>(topic, key, message));
    logger.atInfo().log("Key: %s", key);
  }

  @Override
  public void run() {
    try {
      do {
        send(messageGenFn.apply(itemCount));
        if (itemCount % sendBatchSize == 0) {
          producer.flush();
        }

        Thread.sleep(kafkaArgs.speed());
      } while (!isClosed);
      logger.atInfo().log("Thread %s already closed", threadNumber);
    } catch (InterruptedException e) {
      logger.atSevere().log("Worker %s Interrupted", threadNumber);
    } catch (NoSuchElementException e) {
      logger.atSevere().log("Worker %s: no more messages from Generator", threadNumber);
    }

    // Send unsent queued messages to Kafka broker.
    producer.flush();
  }
}
