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

package com.google.cloud.solutions.trinoscaler;

import com.google.auto.value.AutoValue;

/** Record class to encapsulate details of the Dataproc cluster. */
@AutoValue
public abstract class ClusterInformation {
  public abstract String projectId();

  public abstract String region();

  public abstract String zone();

  public abstract String name();

  public static ClusterInformation create(
      String projectId, String region, String zone, String name) {
    return new AutoValue_ClusterInformation(projectId, region, zone, name);
  }
}
