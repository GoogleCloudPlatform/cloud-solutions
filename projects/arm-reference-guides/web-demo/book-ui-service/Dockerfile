# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# ---- STAGE 1: Build ----
# Use a specific, trusted builder image that includes Maven and a JDK
# This image supports multi-architecture builds
FROM maven:3.9-eclipse-temurin-17 AS builder

# Set the working directory inside the container
WORKDIR /app

# Copy the Maven project file first to leverage Docker layer caching
COPY pom.xml .

# Copy the rest of the source code
COPY src ./src

# Run the Maven build to compile the application and create the executable JAR.
# We skip running tests for a faster build pipeline.
RUN mvn clean package -DskipTests


# ---- STAGE 2: Final Image ----
# Use a minimal, secure, multi-architecture-compatible Java Runtime Environment image
FROM eclipse-temurin:17-jre-jammy

# Set the working directory for the final application
WORKDIR /app

# Copy the executable JAR built in the 'builder' stage into the final image
# Note the name matches the artifactId in pom.xml
COPY --from=builder /app/target/book-ui-service-*.jar ./app.jar

# Expose the port the application is configured to run on (from application.properties)
EXPOSE 8080

# The command that will be executed when the container starts
ENTRYPOINT ["java", "-jar", "app.jar"]
