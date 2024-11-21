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

repositories {
    maven(url = "https://packages.confluent.io/maven/")
}

dependencies {
    implementation(project(":proto-serde"))
    implementation(libs.bundles.common)
    implementation(libs.bundles.apache.beam)
    implementation(libs.bundles.flogger)
    implementation(libs.kafka)

    compileOnly(libs.auto.value.annotations)
    annotationProcessor(libs.auto.value)
    testCompileOnly(libs.auto.value.annotations)
    testAnnotationProcessor(libs.auto.value)

    runtimeOnly(libs.bundles.logger.runtime)
    runtimeOnly(libs.beam.runners.google.cloud.dataflow.java)
    runtimeOnly("org.slf4j:slf4j-jdk14:2.0.16")

    testImplementation(libs.bundles.test.bundle)
    testImplementation(libs.beam.runners.direct.java)
    testImplementation(libs.kafka.client)
    testImplementation(libs.testcontainers.kafka)
    testImplementation("com.google.cloud.solutions.satools.common:testing")
    testImplementation("com.google.cloud.solutions.satools.common:utils")
    testImplementation(project(":kafka-utils"))
    testImplementation(libs.jsonassert)
    testRuntimeOnly(project(":proto-test-resources"))
}

tasks.withType<ShadowJar> {
    isZip64 = true
    mergeServiceFiles()
    manifest {
        attributes(mapOf("Main-Class" to "com.google.cloud.solutions.dataflow.kafka2bigquery.Kafka2BigQueryPipeline"))
    }
}

// Avoid extreme logging during test runs.
configurations.testRuntimeOnly {
    exclude("org.slf4j", "slf4j-jdk14")
}
