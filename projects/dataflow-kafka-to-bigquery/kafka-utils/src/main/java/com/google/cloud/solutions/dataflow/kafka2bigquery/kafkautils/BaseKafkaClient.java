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
import com.google.protobuf.Message;
import java.util.Map;
import java.util.Properties;

/** Base class to ProtoProducer and ProtoConsumer that integrates properties processing. */
public abstract class BaseKafkaClient<T extends Message> {

  protected final KafkaArgs kafkaArgs;

  public BaseKafkaClient(KafkaArgs kafkaArgs) {
    this.kafkaArgs = kafkaArgs;
  }

  protected final Properties createClientProperties() {
    var properties = new Properties();
    properties.putAll(createKafkaProperties());

    if (kafkaArgs.properties() != null) {
      properties.putAll(kafkaArgs.properties());
    }

    return properties;
  }

  protected abstract Map<String, Object> createKafkaProperties();
}
