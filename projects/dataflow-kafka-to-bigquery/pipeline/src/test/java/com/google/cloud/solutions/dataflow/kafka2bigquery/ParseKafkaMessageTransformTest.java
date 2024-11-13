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
import com.google.cloud.solutions.dataflow.kafka2bigquery.testing.FixedTimeClockFactory;
import com.google.cloud.solutions.satools.common.testing.TestResourceLoader;
import java.io.IOException;
import java.util.Base64;
import java.util.List;
import org.apache.beam.sdk.testing.PAssert;
import org.apache.beam.sdk.testing.TestPipeline;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.values.KV;
import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public final class ParseKafkaMessageTransformTest {

  @Rule public TestPipeline testPipeline = TestPipeline.create();

  @Rule public TemporaryFolder temporaryFolder = new TemporaryFolder();

  private ParseKafkaMessageTransform parseXForm;

  private Base64.Decoder base64Decoder = Base64.getDecoder();

  @Before
  public void createXForm() throws IOException {
    // Stage JAR file
    var stagedJarFile =
        TestResourceLoader.classPath()
            .copyTo(temporaryFolder.newFolder())
            .createFileTestCopy("sample-proto.jar");

    parseXForm =
        ParseKafkaMessageTransform.builder()
            .topic("sometopic")
            .clockFactory(new FixedTimeClockFactory("2024-11-10T02:00:00.000Z"))
            .protoClassName("demo.fraud.FraudEventOuterClass$FraudEvent")
            .protoJarPath(stagedJarFile.getAbsolutePath())
            .build();
  }

  @Test
  public void expand_noSchemaDiff_nothingInErrorStream() throws ClassNotFoundException {

    // Arrange
    var sampleFraudEventBytes =
        Base64.getDecoder()
            .decode(
                TestResourceLoader.classPath().loadAsString("sample_fraud_event_bytes.txt").trim());

    TableRow sampleFraudEvent =
        TestResourceLoader.classPath().loadAsJson("sample_fraud_event.json", TableRow.class);

    // Act
    var pct =
        testPipeline
            .apply(Create.of(KV.of(new byte[] {}, sampleFraudEventBytes)))
            .apply(parseXForm);

    // Assert
    PAssert.that(pct.get(parseXForm.getOutputTag())).containsInAnyOrder(sampleFraudEvent);
    PAssert.that(pct.get(parseXForm.getSchemaErrorTag())).empty();

    testPipeline.run();
  }

  @Test
  public void expand_schemaEvolved_outputErrorStreamAndNormal() throws ClassNotFoundException {

    // Arrange
    TableRow sampleFraudEvent =
        TestResourceLoader.classPath().loadAsJson("sample_fraud_event.json", TableRow.class);

    var evolvedFraudEventBytes =
        base64Decoder.decode(
            TestResourceLoader.classPath()
                .loadAsString("sample_evolved_fraud_event_bytes.txt")
                .trim());

    // Act
    var pct =
        testPipeline
            .apply(Create.of(KV.of(new byte[] {2, 3}, evolvedFraudEventBytes)))
            .apply(parseXForm);

    // Assert
    PAssert.that(pct.get(parseXForm.getOutputTag())).containsInAnyOrder(sampleFraudEvent);
    PAssert.that(pct.get(parseXForm.getSchemaErrorTag()))
        .containsInAnyOrder(
            KafkaSchemaError.builder()
                .topic("sometopic")
                .timestamp("2024-11-10T02:00:00.000Z")
                .rawKey(new byte[] {2, 3})
                .rawMessage(evolvedFraudEventBytes)
                .unknownFieldIds(List.of(15, 20, 25))
                .build());

    testPipeline.run();
  }
}
