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
import com.google.cloud.solutions.satools.common.testing.TestResourceLoader;
import java.io.IOException;
import java.util.Arrays;
import java.util.Properties;
import org.apache.commons.cli.ParseException;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;
import org.junit.runner.RunWith;
import org.junit.runners.Parameterized;
import org.junit.runners.Parameterized.Parameters;
import org.testcontainers.shaded.com.google.common.collect.ImmutableList;

@RunWith(Parameterized.class)
public class KafkaProtoProducerAppTest {

  @Rule public TemporaryFolder temporaryFolder = new TemporaryFolder();

  private final String[] args;
  private final KafkaArgs expectedArgs;
  private final String propertiesFile;

  private String[] testArgs;

  public KafkaProtoProducerAppTest(
      String testName, String[] args, KafkaArgs expectedArgs, String propertiesFile) {
    this.args = args;
    this.expectedArgs = expectedArgs;
    this.propertiesFile = propertiesFile;
  }

  @Before
  public void createPropertiesFile() throws IOException {
    var argsList = ImmutableList.<String>builder();
    argsList.addAll(Arrays.asList(args));

    if (propertiesFile != null) {
      var file =
          TestResourceLoader.classPath()
              .copyTo(temporaryFolder.newFolder())
              .createFileTestCopy(propertiesFile);
      argsList.add("-p").add(file.getAbsolutePath());
    }
    testArgs = argsList.build().toArray(new String[0]);
  }

  @Test
  public void parseArgs_valid() throws ParseException, IOException {
    // Act
    var kafkaArgs = KafkaProtoProducerApp.parseArgs(testArgs);

    // Assert
    assertThat(kafkaArgs).isEqualTo(expectedArgs);
  }

  @Parameters(name = "{0}")
  public static ImmutableList<Object[]> testParameters() {
    var propertiesFileName = "test_kafka.properties";
    var expectedProperties = new Properties();
    expectedProperties.put("someParameter.key", "someValue");

    return ImmutableList.<Object[]>builder()
        .add(
            new Object[] {
              /* testName= */ "noPropertiesFilesSmallOpts",
              /* args= */ new String[] {
                "-x", "2",
                "-s", "200",
                "-t", "test-kafka-topic",
                "-k", "my-kafka-broker:brokerPort",
                "-c", "someProtoClass",
                "-d", "5"
              },
              /* expectedArgs= */ new KafkaArgs(
                  /* threads= */ 2,
                  /* speed= */ 200,
                  /* runDurationMinutes= */ 5,
                  /* bootStrapServer= */ "my-kafka-broker:brokerPort",
                  /* topic= */ "test-kafka-topic",
                  /* protoClassName= */ "someProtoClass",
                  /* properties= */ null),
              /* propertiesFile= */ null
            })
        .add(
            new Object[] {
              /* testName= */ "noPropertiesFilesBigOpts",
              /* args= */ new String[] {
                "--threads", "2",
                "--speed", "200",
                "--topic", "test-kafka-topic",
                "--bootStrapServer", "my-kafka-broker:brokerPort",
                "--protoClass", "someProtoClass",
                "--duration", "5"
              },
              /* expectedArgs= */ new KafkaArgs(
                  /* threads= */ 2,
                  /* speed= */ 200,
                  /* runDurationMinutes= */ 5,
                  /* bootStrapServer= */ "my-kafka-broker:brokerPort",
                  /* topic= */ "test-kafka-topic",
                  /* protoClassName= */ "someProtoClass",
                  /* properties= */ null),
              /* propertiesFile= */ null
            })
        .add(
            new Object[] {
              /* testName= */ "propertiesFilesSmallOpts",
              /* args= */ new String[] {
                "-x", "2",
                "-s", "200",
                "-t", "test-kafka-topic",
                "-k", "my-kafka-broker:brokerPort",
                "-c", "someProtoClass",
                "-d", "5"
              },
              /* expectedArgs= */ new KafkaArgs(
                  /* threads= */ 2,
                  /* speed= */ 200,
                  /* runDurationMinutes= */ 5,
                  /* bootStrapServer= */ "my-kafka-broker:brokerPort",
                  /* topic= */ "test-kafka-topic",
                  /* protoClassName= */ "someProtoClass",
                  /* properties= */ expectedProperties),
              /* propertiesFile= */ propertiesFileName
            })
        .add(
            new Object[] {
              /* testName= */ "propertiesFilesBigOpts",
              /* args= */ new String[] {
                "--threads", "2",
                "--speed", "200",
                "--topic", "test-kafka-topic",
                "--bootStrapServer", "my-kafka-broker:brokerPort",
                "--protoClass", "someProtoClass",
                "--duration", "5"
              },
              /* expectedArgs= */ new KafkaArgs(
                  /* threads= */ 2,
                  /* speed= */ 200,
                  /* runDurationMinutes= */ 5,
                  /* bootStrapServer= */ "my-kafka-broker:brokerPort",
                  /* topic= */ "test-kafka-topic",
                  /* protoClassName= */ "someProtoClass",
                  /* properties= */ expectedProperties),
              /* propertiesFile= */ propertiesFileName
            })
        .add(
            new Object[] {
              /* testName= */ "userProvidedSendBatchSizeSmallOpts",
              /* args= */ new String[] {
                "-x", "2",
                "-s", "200",
                "-t", "test-kafka-topic",
                "-k", "my-kafka-broker:brokerPort",
                "-c", "someProtoClass",
                "-d", "5",
                "-b", "100"
              },
              /* expectedArgs= */ new KafkaArgs(
                  /* threads= */ 2,
                  /* speed= */ 200,
                  /* runDurationMinutes= */ 5,
                  /* bootStrapServer= */ "my-kafka-broker:brokerPort",
                  /* topic= */ "test-kafka-topic",
                  /* protoClassName= */ "someProtoClass",
                  /* properties= */ expectedProperties,
                  /* sendBatchSize= */ 100),
              /* propertiesFile= */ propertiesFileName
            })
        .add(
            new Object[] {
              /* testName= */ "userProvidedSendBatchSizeBigOpts",
              /* args= */ new String[] {
                "--threads", "2",
                "--speed", "200",
                "--topic", "test-kafka-topic",
                "--bootStrapServer", "my-kafka-broker:brokerPort",
                "--protoClass", "someProtoClass",
                "--duration", "5",
                "--batchSize", "150"
              },
              /* expectedArgs= */ new KafkaArgs(
                  /* threads= */ 2,
                  /* speed= */ 200,
                  /* runDurationMinutes= */ 5,
                  /* bootStrapServer= */ "my-kafka-broker:brokerPort",
                  /* topic= */ "test-kafka-topic",
                  /* protoClassName= */ "someProtoClass",
                  /* properties= */ expectedProperties,
                  /* sendBatchSize= */ 150),
              /* propertiesFile= */ propertiesFileName
            })
        .build();
  }
}
