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
    // Apply the common convention plugin for shared build configuration
    // between library and application projects.
    id("buildlogic.java-common-conventions")

    // Apply the java-library plugin for API and implementation separation.
    `java-library`
    id("com.google.protobuf")
}

val libs = extensions.getByType<VersionCatalogsExtension>().named("libs")

dependencies {
    compileOnly(libs.findBundle("proto-libs").get())
}

protobuf {
    protoc {
        artifact = "com.google.protobuf:protoc:${libs.findVersion("protobuf").get()}"
    }
}
