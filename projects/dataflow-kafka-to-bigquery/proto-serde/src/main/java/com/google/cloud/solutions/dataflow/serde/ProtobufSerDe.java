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

import static com.google.common.base.Preconditions.checkArgument;
import static com.google.common.base.Preconditions.checkNotNull;
import static com.google.common.base.Strings.isNullOrEmpty;

import com.google.common.flogger.GoogleLogger;
import com.google.protobuf.Message;
import java.util.Base64;
import java.util.Map;
import org.apache.kafka.common.serialization.Deserializer;
import org.apache.kafka.common.serialization.Serde;
import org.apache.kafka.common.serialization.Serializer;

/** A Serializer and Deserializer class for Proto objects. */
public class ProtobufSerDe implements Serde<Message> {

  private static final GoogleLogger logger = GoogleLogger.forEnclosingClass();

  private boolean isKey;
  private Map<String, ?> config;

  private Serializer<Message> serializer;
  private Deserializer<Message> deserializer;

  public ProtobufSerDe() {
    this.serializer = new ProtoSerializer();
    this.deserializer = new ProtoDeserializer();
  }

  @Override
  public Serializer<Message> serializer() {
    return serializer;
  }

  @Override
  public Deserializer<Message> deserializer() {
    return deserializer;
  }

  @Override
  public void configure(Map<String, ?> configs, boolean isKey) {
    this.config = configs;
    this.isKey = isKey;
    serializer.configure(configs, isKey);
    deserializer.configure(configs, isKey);
  }

  /** Generic Proto message serializer. */
  public static class ProtoSerializer implements Serializer<Message> {

    @Override
    public byte[] serialize(String topic, Message data) {
      checkNotNull(data, "provided proto should not be null");
      return data.toByteArray();
    }
  }

  /**
   * Deserializes a byte-array to a protocol buffer class.
   *
   * <p>Ensure that the protobuf compiled class is available on the classpath. Configure the
   * deserializer with the proto class name using key "protodeserilizer.classname"
   *
   * <p>Example:
   *
   * <pre>
   *   ProtoDeserializer deserializer = new ProtoDeserializer();
   *   deserializer.configure(Map.of("protodeserilizer.classname", FraudEvent.class.getName());
   * </pre>
   */
  public static class ProtoDeserializer implements Deserializer<Message> {

    public static final String DESERIALIZER_PROTO_CLASS_NAME_CONFIG = "protodeserilizer.classname";

    private Class<?> protoClass;

    public ProtoDeserializer(Class<? extends Message> protoClass) {
      this.protoClass = protoClass;
    }

    public ProtoDeserializer() {
      this.protoClass = null;
    }

    @Override
    public void configure(Map<String, ?> configs, boolean isKey) {

      if (protoClass != null) {
        logger.atInfo().log(
            "ProtoDeserializer using preconfigured protoClass: %s", protoClass.getName());
        return;
      }

      checkArgument(
          configs.containsKey(DESERIALIZER_PROTO_CLASS_NAME_CONFIG),
          "Proto Class name not configured.");

      String protoClassname = (String) configs.get(DESERIALIZER_PROTO_CLASS_NAME_CONFIG);
      checkArgument(!isNullOrEmpty(protoClassname), "Proto Class name is null or empty");

      try {
        protoClass = Class.forName(protoClassname);

        checkArgument(
            Message.class.isAssignableFrom(protoClass),
            "Provided protoClass is not valid Message class");

      } catch (ClassNotFoundException e) {
        throw new RuntimeException("class not found protoClassName: " + protoClassname, e);
      }
    }

    @Override
    public Message deserialize(String topic, byte[] data) {
      try {
        var builder = (Message.Builder) protoClass.getMethod("newBuilder").invoke(null);

        return builder.mergeFrom(data).build();

      } catch (Exception e) {
        logger.atSevere().withCause(e).log(
            "error deserializing topic: %s\ndata: %s",
            topic, Base64.getEncoder().encodeToString(data));
        return null;
      }
    }
  }
}
