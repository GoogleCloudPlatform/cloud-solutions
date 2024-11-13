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

package com.google.cloud.solutions.dataflow.serde;

import static com.google.common.truth.Truth.assertThat;
import static com.google.common.truth.extensions.proto.ProtoTruth.assertThat;
import static org.junit.Assert.assertThrows;

import com.google.cloud.solutions.dataflow.serde.ProtobufSerDe.ProtoDeserializer;
import com.google.cloud.solutions.dataflow.serde.ProtobufSerDe.ProtoSerializer;
import com.google.cloud.solutions.satools.common.testing.TestResourceLoader;
import demo.fraud.FraudEventOuterClass.FraudEvent;
import java.util.Map;
import org.junit.Test;
import org.junit.experimental.runners.Enclosed;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(Enclosed.class)
public final class ProtobufSerDeTest {

  @RunWith(JUnit4.class)
  public static final class ValidTests {
    @Test
    public void serde_valid() {
      var serializer = new ProtoSerializer();
      var deserializer = new ProtoDeserializer();

      var protoMessage =
          TestResourceLoader.classPath()
              .forProto(FraudEvent.class)
              .loadText("sample_fraud_event.txtpb");

      deserializer.configure(
          Map.of(
              ProtoDeserializer.DESERIALIZER_PROTO_CLASS_NAME_CONFIG, FraudEvent.class.getName()),
          false);
      var testMessage = serializer.serialize("test", protoMessage);

      assertThat(deserializer.deserialize("test", testMessage)).isEqualTo(protoMessage);
    }

    @Test
    public void serde_typeSpecific_valid() {
      var serializer = new ProtoSerializer();
      var deserializer = new ProtoDeserializer(FraudEvent.class);

      var protoMessage =
          TestResourceLoader.classPath()
              .forProto(FraudEvent.class)
              .loadText("sample_fraud_event.txtpb");

      var testMessage = serializer.serialize("test", protoMessage);

      assertThat(deserializer.deserialize("test", testMessage)).isEqualTo(protoMessage);
    }
  }

  @RunWith(JUnit4.class)
  public static final class ExceptionTests {
    @Test
    public void deserializer_configNoProtoClass_throwsException() {
      var exception =
          assertThrows(
              IllegalArgumentException.class,
              () -> {
                new ProtoDeserializer().configure(Map.of(), false);
              });

      assertThat(exception).hasMessageThat().isEqualTo("Proto Class name not configured.");
    }

    @Test
    public void deserializer_configEmptyProtoClassName_throwsException() {
      var exception =
          assertThrows(
              IllegalArgumentException.class,
              () -> {
                new ProtoDeserializer()
                    .configure(
                        Map.of(ProtoDeserializer.DESERIALIZER_PROTO_CLASS_NAME_CONFIG, ""), false);
              });

      assertThat(exception).hasMessageThat().isEqualTo("Proto Class name is null or empty");
    }

    @Test
    public void deserializer_classNotFound_throwsException() {
      var runtimeException =
          assertThrows(
              RuntimeException.class,
              () -> {
                new ProtoDeserializer()
                    .configure(
                        Map.of(
                            ProtoDeserializer.DESERIALIZER_PROTO_CLASS_NAME_CONFIG,
                            "com.google.randomProto"),
                        false);
              });

      assertThat(runtimeException)
          .hasMessageThat()
          .isEqualTo("class not found protoClassName: com.google.randomProto");
    }

    @Test
    public void deserializer_invalidProtoClass_throwsException() {
      var exception =
          assertThrows(
              IllegalArgumentException.class,
              () -> {
                new ProtoDeserializer()
                    .configure(
                        Map.of(
                            ProtoDeserializer.DESERIALIZER_PROTO_CLASS_NAME_CONFIG,
                            "java.util.Map"),
                        false);
              });

      assertThat(exception)
          .hasMessageThat()
          .isEqualTo("Provided protoClass is not valid Message class");
    }
  }
}
