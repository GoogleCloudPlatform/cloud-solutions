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

plugins {
    java
    jacoco
    id("com.diffplug.spotless")
    idea
}

group = "com.google.cloud.solutions.dataflow.kafka2bigquery"

val libs = extensions.getByType<VersionCatalogsExtension>().named("libs")

repositories {
    // Use Maven Central for resolving dependencies.
    mavenLocal()
    mavenCentral()
    gradlePluginPortal()
    maven(url = "https://packages.confluent.io/maven/")
}

dependencies {
    testImplementation(libs.findBundle("test-bundle").get())
}

tasks.test {
    finalizedBy(tasks.jacocoTestReport)
    testLogging.events("passed", "skipped", "failed", "standardOut", "standardError")
    testLogging.showStandardStreams = true
}

tasks.withType<JavaCompile> {
    options.encoding = "UTF-8"
}

tasks.jacocoTestReport {
    dependsOn(tasks.test)
    reports {
        xml.required = true
        csv.required = false
    }
}

jacoco {
    toolVersion = "0.8.12"
}

spotless {
    java {
        targetExclude("**/generated/**/*.java")
        googleJavaFormat("1.24.0").reflowLongStrings().reorderImports(true)
        trimTrailingWhitespace()
        endWithNewline()
    }
}
