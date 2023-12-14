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

package com.google.cloud.solutions.satools.perfbenchmark.entity;

import static com.google.common.base.Preconditions.checkNotNull;

import com.google.common.base.Objects;
import com.googlecode.objectify.Key;
import com.googlecode.objectify.annotation.Entity;
import com.googlecode.objectify.annotation.Id;
import com.googlecode.objectify.annotation.Parent;
import java.time.Instant;

/** Objectify Entity to represent a Job Status event in Datastore. */
@Entity
public class BenchmarkJobStatus {

  @Parent private Key<BenchmarkJobEntity> jobKey;

  @Id private String status;

  private Instant timestamp;

  /** Simple all parameter constructor. */
  public BenchmarkJobStatus(Key<BenchmarkJobEntity> jobKey, String status, Instant timestamp) {
    this.jobKey = checkNotNull(jobKey);
    this.status = checkNotNull(status);
    this.timestamp = checkNotNull(timestamp);
  }

  public BenchmarkJobStatus(BenchmarkJobEntity job, Enum<?> status, Instant timestamp) {
    this(Key.create(job), status.name(), timestamp);
  }

  public Key<BenchmarkJobEntity> getJobKey() {
    return jobKey;
  }

  public String getStatus() {
    return status;
  }

  public Instant getTimestamp() {
    return timestamp;
  }

  @Override
  public boolean equals(Object o) {
    if (this == o) {
      return true;
    }

    return (o instanceof BenchmarkJobStatus that)
        && Objects.equal(jobKey, that.jobKey)
        && Objects.equal(status, that.status)
        && Objects.equal(timestamp, that.timestamp);
  }

  @Override
  public int hashCode() {
    return Objects.hashCode(jobKey, status, timestamp);
  }

  private BenchmarkJobStatus() {}
}
