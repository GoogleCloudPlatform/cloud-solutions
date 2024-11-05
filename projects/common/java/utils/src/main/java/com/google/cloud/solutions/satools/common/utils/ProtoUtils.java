/*
 * Copyright 2023 Google LLC
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

package com.google.cloud.solutions.satools.common.utils;

import com.google.protobuf.Message;
import com.google.protobuf.util.JsonFormat;

/** Utility class to convert Protobuf messages from/to JSON. */
public final class ProtoUtils {

  /**
   * Returns a proto message by parsing json for the given proto class.
   *
   * @param json the Json representation of the proto message.
   * @param protoClazz the proto class to deserialize
   * @param <T> the type of Proto class.
   */
  @SuppressWarnings("unchecked") // Use of generics for creation of Proto message from JSON.
  public static <T extends Message> T parseProtoJson(String json, Class<T> protoClazz) {
    try {
      var builder = (Message.Builder) protoClazz.getMethod("newBuilder").invoke(null);

      JsonFormat.parser().merge(json, builder);
      return (T) builder.build();
    } catch (Exception exception) {
      throw new RuntimeException("error converting\n" + json, exception);
    }
  }

  /**
   * Returns a proto message by parsing json for the given proto class with lenient parsing.
   *
   * <p>Proto parser ignores unknown fields.
   *
   * @param json the Json representation of the proto message.
   * @param protoClazz the proto class to deserialize
   * @param <T> the type of Proto class.
   */
  @SuppressWarnings("unchecked") // Use of generics for creation of Proto message from JSON.
  public static <T extends Message> T parseProtoJsonLenient(String json, Class<T> protoClazz) {
    try {
      var builder = (Message.Builder) protoClazz.getMethod("newBuilder").invoke(null);

      JsonFormat.parser().ignoringUnknownFields().merge(json, builder);
      return (T) builder.build();
    } catch (Exception exception) {
      throw new RuntimeException("error converting\n" + json, exception);
    }
  }

  /** Returns a JSON string representation for the given Protobuf object. */
  public static <T extends Message> String toJson(T protoObj) {
    try {
      return JsonFormat.printer().print(protoObj);
    } catch (Exception e) {
      throw new RuntimeException("error making json", e);
    }
  }

  public static <T extends Message.Builder> String toJson(T protoBuilder) {
    return toJson(protoBuilder.build());
  }
}
