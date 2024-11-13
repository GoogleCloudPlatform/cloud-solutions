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

import static com.google.common.base.MoreObjects.firstNonNull;
import static com.google.common.truth.Truth.assertThat;

import com.google.api.services.bigquery.model.Table;
import com.google.api.services.bigquery.model.TableReference;
import com.google.cloud.solutions.dataflow.kafka2bigquery.testing.FakeBigQueryServices;
import com.google.cloud.solutions.dataflow.kafka2bigquery.testing.FakeDatasetService;
import com.google.cloud.solutions.dataflow.kafka2bigquery.testing.FixedTimeClockFactory;
import com.google.cloud.solutions.satools.common.testing.TestResourceLoader;
import com.google.common.collect.ImmutableList;
import com.google.common.flogger.GoogleLogger;
import java.io.IOException;
import java.time.Duration;
import java.util.Base64;
import java.util.LinkedList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.apache.beam.sdk.options.PipelineOptionsFactory;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.testing.TestPipelineOptions;
import org.apache.kafka.clients.admin.Admin;
import org.apache.kafka.clients.admin.AdminClientConfig;
import org.apache.kafka.clients.admin.NewTopic;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.serialization.ByteArraySerializer;
import org.apache.kafka.common.serialization.StringSerializer;
import org.json.JSONArray;
import org.json.JSONException;
import org.junit.After;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;
import org.junit.runner.RunWith;
import org.junit.runners.Parameterized;
import org.junit.runners.Parameterized.Parameters;
import org.skyscreamer.jsonassert.JSONAssert;
import org.testcontainers.kafka.KafkaContainer;

@RunWith(Parameterized.class)
public class Kafka2BigQueryPipelineTest {

  private static final String FIXED_TEST_TIMESTAMP = "2024-11-10T01:59:00.000Z";
  private static final GoogleLogger logger = GoogleLogger.forEnclosingClass();

  private static final String TEST_KAFKA_TOPIC = "it-test-topic";

  @Rule public KafkaContainer kafkaContainer = new KafkaContainer("apache/kafka-native:3.8.1");

  @Rule public TestPipeline testPipeline = TestPipeline.create();
  @Rule public TemporaryFolder temporaryFolder = new TemporaryFolder();

  private TestKafkaProducerRunner kafkaRunner;

  private final String[] cliArgs;
  private final List<byte[]> messages;
  private final JSONArray expectedOutput;
  private final JSONArray expectedErrors;

  private String stagedJarFileLocation;

  public Kafka2BigQueryPipelineTest(
      String testName,
      String[] cliArgs,
      List<byte[]> messages,
      JSONArray expectedOutput,
      JSONArray expectedErrors) {
    this.cliArgs = cliArgs;
    this.messages = messages;
    this.expectedOutput = expectedOutput;
    this.expectedErrors = expectedErrors;
  }

  @Before
  public void makeTestPipelineAsync() {
    testPipeline.getOptions().as(TestPipelineOptions.class).setBlockOnRun(false);
  }

  @Before
  public void copyJarFileToTemp() throws IOException {
    stagedJarFileLocation =
        TestResourceLoader.classPath()
            .copyTo(temporaryFolder.newFolder())
            .createFileTestCopy("sample-proto.jar")
            .getAbsolutePath();
  }

  @After
  public void tearDown() {
    if (kafkaRunner != null) {
      kafkaRunner.tearDown();
    }
  }

  @Test
  public void run_valid()
      throws InterruptedException, IOException, ClassNotFoundException, JSONException {
    // Arrange:1: Setup TestPipeline
    var options = PipelineOptionsFactory.fromArgs(cliArgs).as(Kafka2BigQueryOptions.class);

    // Set Kafka properties
    options.setKafkaBootstrapServers(kafkaContainer.getBootstrapServers());
    var consumerProperties =
        firstNonNull(
            options.getKafkaConsumerConfigProperties(),
            // Set offset to earliest to ensure the test picks up all messages.
            new LinkedList<String>());
    consumerProperties.add(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG + "=earliest");
    options.setKafkaConsumerConfigProperties(consumerProperties);

    // Update CLI options with Staged JAR file.
    options.setProtoJarFile(stagedJarFileLocation);

    FakeDatasetService.init(
        /* existingTables= */ Map.of(
            new TableReference()
                .setProjectId("fake-project")
                .setDatasetId("fake_dataset")
                .setTableId("FraudEvents"),
            new Table()),
        Set.of(),
        Map.of());

    // Setup Kafka producer
    kafkaRunner = new TestKafkaProducerRunner();
    kafkaRunner.init();

    // setup pipeline
    new Kafka2BigQueryPipeline(
            testPipeline,
            options,
            new TestServiceBigQueryWriterFactory(
                new FakeBigQueryServices(new FakeDatasetService())),
            new FixedTimeClockFactory(FIXED_TEST_TIMESTAMP))
        .setup();

    // Act: Run Pipeline
    var result = testPipeline.run();
    kafkaRunner.run();
    // Wait for pipeline to run
    logger.atInfo().log("Cancelling TestPipeline After 10 seconds");
    Thread.sleep(Duration.ofSeconds(10).toMillis());
    result.cancel();

    // Assert
    assertThat(FakeDatasetService.insertedRows)
        .containsKey("fake-project.fake_dataset.FraudEvents");
    JSONAssert.assertEquals(
        /* expected= */ expectedOutput,
        /* actual= */ new JSONArray(
            FakeDatasetService.insertedRows
                .get("fake-project.fake_dataset.FraudEvents")
                .toString()),
        /* strict= */ false);

    if (options.getMismatchedMessageBigQueryTableSpec() != null) {
      assertThat(FakeDatasetService.insertedRows)
          .containsKey("fake-project.fake_dataset.KafkaSchemaErrors");

      JSONAssert.assertEquals(
          /* expected= */ expectedErrors,
          /* actual= */ new JSONArray(
              FakeDatasetService.insertedRows
                  .get("fake-project.fake_dataset.KafkaSchemaErrors")
                  .toString()),
          /* strict= */ false // Allows elements out of order.
          );
    }
  }

  @Parameters(name = "{0}")
  public static ImmutableList<Object[]> testParameters() throws JSONException {

    var base64Decoder = Base64.getDecoder();

    var sampleFraudEventBytes =
        base64Decoder.decode(
            TestResourceLoader.classPath().loadAsString("sample_fraud_event_bytes.txt").trim());

    var sampleFraudEventJson =
        TestResourceLoader.classPath().loadAsString("sample_fraud_event.json");

    var sampleEvolvedFraudEventBytes =
        base64Decoder.decode(
            TestResourceLoader.classPath()
                .loadAsString("sample_evolved_fraud_event_bytes.txt")
                .trim());

    return ImmutableList.<Object[]>builder()
        .add(
            new Object[] {
              /* testName= */ "Additional ConsumerConfig",
              /* cliArgs= */ new String[] {
                "--kafkaTopic=" + TEST_KAFKA_TOPIC,
                "--protoClassName=demo.fraud.FraudEventOuterClass$FraudEvent",
                "--bigQueryTableSpec=fake-project.fake_dataset.FraudEvents",
                "--kafkaConsumerConfigProperties=security.providers=PLAINTEXT\n"
                    + "kafkaKey.someKey=someKeyValue"
              },
              /* messages= */ List.of(
                  sampleEvolvedFraudEventBytes,
                  sampleEvolvedFraudEventBytes,
                  sampleFraudEventBytes),
              /* expectedOutput= */ new JSONArray(
                  List.of(sampleFraudEventJson, sampleFraudEventJson, sampleFraudEventJson)
                      .toString()),
              /* expectedErrorOutput= */ null
            })
        .add(
            new Object[] {
              /* testName= */ "Schema Evolved output clean and errors",
              /* cliArgs= */ new String[] {
                "--kafkaTopic=" + TEST_KAFKA_TOPIC,
                "--protoClassName=demo.fraud.FraudEventOuterClass$FraudEvent",
                "--bigQueryTableSpec=fake-project.fake_dataset.FraudEvents",
                "--mismatchedMessageBigQueryTableSpec=fake-project.fake_dataset.KafkaSchemaErrors",
              },
              /* messages= */ List.of(
                  sampleEvolvedFraudEventBytes,
                  sampleEvolvedFraudEventBytes,
                  sampleEvolvedFraudEventBytes),
              /* expectedOutput= */ new JSONArray(
                  List.of(sampleFraudEventJson, sampleFraudEventJson, sampleFraudEventJson)
                      .toString()),
              /* expectedErrorOutput= */ new JSONArray(
                  TestResourceLoader.classPath().loadAsString("expected_schema_errors.json"))
            })
        .add(
            new Object[] {
              /* testName= */ "Schema Evolved output clean no errors",
              /* cliArgs= */ new String[] {
                "--kafkaTopic=" + TEST_KAFKA_TOPIC,
                "--protoClassName=demo.fraud.FraudEventOuterClass$FraudEvent",
                "--bigQueryTableSpec=fake-project.fake_dataset.FraudEvents"
              },
              /* messages= */ List.of(
                  sampleEvolvedFraudEventBytes,
                  sampleEvolvedFraudEventBytes,
                  sampleEvolvedFraudEventBytes),
              /* expectedOutput= */ new JSONArray(
                  List.of(sampleFraudEventJson, sampleFraudEventJson, sampleFraudEventJson)
                      .toString()),
              /* expectedErrorOutput= */ null
            })
        .build();
  }

  private class TestKafkaProducerRunner {

    private KafkaProducer<String, byte[]> kafkaProducer;

    void init() {
      // Start Kafka Test Container
      kafkaContainer.start();
      try (var kafkaAdmin =
          Admin.create(
              Map.of(
                  AdminClientConfig.BOOTSTRAP_SERVERS_CONFIG,
                  kafkaContainer.getBootstrapServers()))) {
        var topicConfig =
            new NewTopic(
                TEST_KAFKA_TOPIC, /* numPartitions= */ 1, /* replicationFactor= */ (short) 1);
        kafkaAdmin.createTopics(List.of(topicConfig));
      }

      kafkaProducer =
          new KafkaProducer<>(
              Map.of(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, kafkaContainer.getBootstrapServers()),
              new StringSerializer(),
              new ByteArraySerializer());
    }

    void tearDown() {
      if (kafkaProducer != null) {
        kafkaProducer.flush();
        kafkaProducer.close();
      }
    }

    void run() {
      for (int messageIndex = 0; messageIndex < messages.size(); messageIndex++) {
        kafkaProducer.send(
            new ProducerRecord<>(
                TEST_KAFKA_TOPIC, "1-" + messageIndex, messages.get(messageIndex)));
        logger.atInfo().log("KafkaProducer (send): key: 1-%s", messageIndex);
      }
      kafkaProducer.flush();
    }
  }
}
