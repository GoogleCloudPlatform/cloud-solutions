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

# ---- Build Stage ----
# Use a specific, trusted builder image that includes Maven and JDK
FROM maven:3.9-eclipse-temurin-17 AS builder

# Set the working directory
WORKDIR /app

# Copy the project files into the container
COPY pom.xml .
COPY src ./src

# Build the application, skipping tests.
RUN mvn clean package -DskipTests

# ---- Final Image Stage ----
# Use a minimal, secure JRE image that supports both amd64 and arm64.
FROM eclipse-temurin:17-jre-jammy

# Set the working directory
WORKDIR /app

# Copy the executable JAR from the builder stage
# Note the artifact name is 'review-service'
COPY --from=builder /app/target/review-service-*.jar ./app.jar

# Expose the port the application runs on (8081)
EXPOSE 8081

# The command to run the application
ENTRYPOINT ["java", "-jar", "app.jar"]
