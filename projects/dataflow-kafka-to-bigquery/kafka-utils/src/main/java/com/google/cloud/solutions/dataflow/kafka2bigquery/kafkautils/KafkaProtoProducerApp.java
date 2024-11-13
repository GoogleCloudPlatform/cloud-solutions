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

import static com.google.cloud.solutions.dataflow.kafka2bigquery.kafkautils.KafkaProtoProducer.DEFAULT_SEND_BATCH_SIZE;
import static com.google.common.base.Preconditions.checkArgument;
import static com.google.common.base.Preconditions.checkNotNull;
import static com.google.common.base.Strings.isNullOrEmpty;

import com.google.cloud.solutions.dataflow.protofn.FraudEventCreatorFn;
import com.google.common.annotations.VisibleForTesting;
import com.google.common.flogger.GoogleLogger;
import demo.fraud.FraudEventOuterClass.FraudEvent;
import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.util.Properties;
import java.util.Random;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.function.Function;
import org.apache.commons.cli.CommandLine;
import org.apache.commons.cli.CommandLineParser;
import org.apache.commons.cli.DefaultParser;
import org.apache.commons.cli.Options;
import org.apache.commons.cli.ParseException;

/** Simple Proto Message producer for Kafka. */
public final class KafkaProtoProducerApp {

  private static final GoogleLogger logger = GoogleLogger.forEnclosingClass();

  /** Runs an unbounded Kafka Producer threads based provided configuration. */
  public static void main(String[] args) throws Exception {

    var config = parseArgs(args);

    Function<Integer, KafkaProtoProducer<FraudEvent>> createProducer =
        (Integer threadId) -> {
          var producer =
              new KafkaProtoProducer<>(
                  threadId,
                  config,
                  new FraudEventCreatorFn(new Random(), Clock.systemUTC()),
                  config.sendBatchSize);
          producer.init();
          return producer;
        };

    var pool = Executors.newFixedThreadPool(config.threads());
    logger.atInfo().log("total threads = %s", config.threads());

    for (int thread = 0; thread < config.threads(); thread++) {
      pool.execute(createProducer.apply(thread));
    }

    pool.shutdown();
    logger.atInfo().log("waiting %s minutes", config.runDurationMinutes());
    if (config.runDurationMinutes() != 0) {
      pool.awaitTermination(config.runDurationMinutes(), TimeUnit.MINUTES);
    }
  }

  @VisibleForTesting
  static KafkaArgs parseArgs(String[] args) throws ParseException, IOException {
    CommandLineParser parser = new DefaultParser();
    CommandLine parsed =
        parser.parse(
            new Options()
                .addOption("x", "threads", true, "number of concurrent threads")
                .addOption("s", "speed", true, "speed of the producer thread")
                .addOption("t", "topic", true, "Kafka Topic to push messages")
                .addOption("k", "bootStrapServer", true, "Kafka bootstrap server address")
                .addOption("c", "protoClass", true, "ProtoClassName")
                .addOption("d", "duration", true, "Duration of the producer thread in minutes")
                .addOption("p", "properties", true, "Properties file to use for Kafka Producer")
                .addOption("b", "batchSize", true, "Kafka sending batch size"),
            args);

    int threadCount = Integer.parseInt(parsed.getOptionValue("x", "1"));
    int speed = Integer.parseInt(parsed.getOptionValue("s", "100"));
    String bootStrapServer = parsed.getParsedOptionValue("k", "localhost:9092");
    String topic = checkNotNull(parsed.getParsedOptionValue("t"));
    String protoClassName = checkNotNull(parsed.getOptionValue("c", FraudEvent.class.getName()));
    int runDurationMinutes = Integer.parseInt(parsed.getOptionValue("d", "10"));
    int sendBatchSize = Integer.parseInt(parsed.getOptionValue("b", "" + DEFAULT_SEND_BATCH_SIZE));

    checkArgument(runDurationMinutes >= 0, "runDurationMinutes should be >= 0");

    String propertiesFile = parsed.getOptionValue("p");
    Properties properties = null;
    if (!isNullOrEmpty(propertiesFile)) {
      properties = new Properties();
      properties.load(new BufferedReader(new FileReader(propertiesFile, StandardCharsets.UTF_8)));
    }

    return new KafkaArgs(
        threadCount,
        speed,
        runDurationMinutes,
        bootStrapServer,
        topic,
        protoClassName,
        properties,
        sendBatchSize);
  }

  /** Configuration for running Kafka producer that is gathered from CLI. */
  public record KafkaArgs(
      int threads,
      int speed,
      int runDurationMinutes,
      String kafkaBootStrapServer,
      String topic,
      String protoClassName,
      Properties properties,
      int sendBatchSize) {

    /** Simplified constructor that uses default sendBatchSize. */
    public KafkaArgs(
        int threads,
        int speed,
        int runDurationMinutes,
        String kafkaBootStrapServer,
        String topic,
        String protoClassName,
        Properties properties) {
      this(
          threads,
          speed,
          runDurationMinutes,
          kafkaBootStrapServer,
          topic,
          protoClassName,
          properties,
          DEFAULT_SEND_BATCH_SIZE);
    }
  }
}
