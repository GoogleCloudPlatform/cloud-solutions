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
    // Support convention plugins written in Kotlin. Convention plugins are build scripts
    // in 'src/main' that automatically become available as plugins in the main build.
    `kotlin-dsl`
}

repositories {
    // Use the plugin portal to apply community plugins in convention plugins.
    mavenCentral()
    gradlePluginPortal()
    maven {
        url = uri("https://plugins.gradle.org/m2/")
    }
}

val libs = extensions.getByType<VersionCatalogsExtension>().named("libs")

dependencies {
    implementation("com.diffplug.spotless:spotless-plugin-gradle:${libs.findVersion("spotless-plugin").get()}")
    implementation("com.google.protobuf:protobuf-gradle-plugin:${libs.findVersion("protobuf-plugin").get()}")
}
