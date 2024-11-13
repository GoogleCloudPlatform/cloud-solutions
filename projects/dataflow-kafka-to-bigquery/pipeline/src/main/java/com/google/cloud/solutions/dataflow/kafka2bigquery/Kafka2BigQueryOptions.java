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

import java.util.List;
import org.apache.beam.sdk.extensions.gcp.options.GcpOptions;
import org.apache.beam.sdk.io.gcp.bigquery.BigQueryOptions;
import org.apache.beam.sdk.options.ApplicationNameOptions;
import org.apache.beam.sdk.options.Description;
import org.apache.beam.sdk.options.Validation.Required;

public interface Kafka2BigQueryOptions extends GcpOptions, BigQueryOptions, ApplicationNameOptions {

  @Required
  String getKafkaTopic();

  void setKafkaTopic(String kafkaTopic);

  @Required
  String getKafkaBootstrapServers();

  void setKafkaBootstrapServers(String kafkaBootstrapServers);

  String getGcsKafkaConsumerConfigPropertiesUri();

  void setGcsKafkaConsumerConfigPropertiesUri(String gcsKafkaConsumerConfigPropertiesUri);

  List<String> getKafkaConsumerConfigProperties();

  void setKafkaConsumerConfigProperties(List<String> kafkaConsumerConfigProperties);

  @Required
  String getProtoClassName();

  void setProtoClassName(String protoClassName);

  @Required
  @Description("The GCS Location for JAR files containing the compiled proto class")
  String getProtoJarFile();

  void setProtoJarFile(String protoJarFile);

  @Required
  String getBigQueryTableSpec();

  void setBigQueryTableSpec(String bigQueryTableSpec);

  String getMismatchedMessageBigQueryTableSpec();

  void setMismatchedMessageBigQueryTableSpec(String mismatchedMessageBigQueryTableSpec);
}
