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

import com.github.jengelman.gradle.plugins.shadow.tasks.ShadowJar

plugins {
    id("buildlogic.java-library-conventions")
    alias(libs.plugins.shadow.jar)
}

dependencies {
    implementation("commons-cli:commons-cli:1.9.0")
    implementation(project(":proto-serde"))
    implementation(libs.kafka.client)
    implementation(libs.bundles.common)
    implementation(libs.bundles.flogger)
    implementation(libs.bundles.proto.libs)
    implementation(project(":sample-proto"))

    // This module is a testing library
    implementation(libs.bundles.test.bundle)

    testImplementation(libs.testcontainers.kafka)
    testImplementation("com.google.cloud.solutions.satools.common:testing")
}

tasks.withType<ShadowJar> {
    isZip64 = true
    mergeServiceFiles()
    manifest {
        attributes(mapOf("Main-Class" to "com.google.cloud.solutions.dataflow.kafka2bigquery.kafkautils.KafkaProtoProducerApp"))
    }
}
