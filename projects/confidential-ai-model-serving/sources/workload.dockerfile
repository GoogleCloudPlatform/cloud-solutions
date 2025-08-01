#
# Copyright 2025 Google LLC
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#

#
# Build stage.
#
FROM maven:3.9.8-eclipse-temurin-22-alpine AS build
WORKDIR /app

# Copy local code to the container image.
COPY . ./

# Build the JAR
RUN mvn clean package -DskipTests

#
# Package stage.
#

# Use latest available image
# hadolint ignore=DL3007
FROM gcr.io/distroless/java17-debian12:latest
WORKDIR /app

COPY --from=build /app/target/confidential-model-serving-1.0.0-jar-with-dependencies.jar app.jar

EXPOSE 8080
CMD ["app.jar", "workload"]
