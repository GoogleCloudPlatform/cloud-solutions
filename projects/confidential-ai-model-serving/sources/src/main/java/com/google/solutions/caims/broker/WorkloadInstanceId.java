//
// Copyright 2025 Google LLC
//
// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements.  See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership.  The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License.  You may obtain a copy of the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an
// "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
// KIND, either express or implied.  See the License for the
// specific language governing permissions and limitations
// under the License.
//

package com.google.solutions.caims.broker;

import com.google.common.base.Preconditions;
import org.jetbrains.annotations.NotNull;

/** Identifies a workload instance. */
public record WorkloadInstanceId(
    @NotNull String projectId, @NotNull String zone, @NotNull String instanceName) {
  public WorkloadInstanceId {
    Preconditions.checkArgument(!projectId.isBlank(), "projectId");
    Preconditions.checkArgument(!zone.isBlank(), "zone");
    Preconditions.checkArgument(!instanceName.isBlank(), "instanceName");
  }

  /** Create a compact, textual representation. */
  @Override
  public String toString() {
    return this.projectId + "/" + this.zone + "/" + this.instanceName;
  }

  /** Convert a value created by {@see toString} to an object. */
  public static @NotNull WorkloadInstanceId fromString(@NotNull String value) {
    Preconditions.checkNotNull(value, "value");

    var parts = value.split("/");
    Preconditions.checkArgument(parts.length == 3, "value");

    return new WorkloadInstanceId(parts[0], parts[1], parts[2]);
  }
}
