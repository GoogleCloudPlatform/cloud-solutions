/*
 * Copyright 2023 Google LLC
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

package com.google.cloud.solutions.satools.perfbenchmark;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;

/** Model to deserialize Perfkit Runner config from {@code application.properties}. */
@ConfigurationProperties(prefix = "perfkitrunner")
public record PerfkitRunnerConfig(
    String projectId,
    String jobConfigGcsBucket,
    boolean allowCors,
    String clientId,
    String baseImage,
    Duration buildTimeout,
    String perfkitFolder,
    String resultsBqProject,
    String resultsBqDataset,
    String resultsBqTable) {}
