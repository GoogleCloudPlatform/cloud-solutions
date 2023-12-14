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

import com.google.common.base.Objects;
import com.googlecode.objectify.annotation.Entity;
import com.googlecode.objectify.annotation.Id;
import com.googlecode.objectify.annotation.Index;
import java.time.Instant;

/** Model to store PKB job related information in Datastore using Objectify. */
@Entity
public class BenchmarkJobEntity {
  @Id private long id;

  @Index private String creatorEmail;

  private String benchmarkJobInformationJson;

  private Instant created;

  @Index private String cloudBuildJobId;

  private String cloudBuildLogUri;

  private BenchmarkJobResult result;

  public static BenchmarkJobEntity getDefaultInstance() {
    return new BenchmarkJobEntity();
  }

  /**
   * Default constructor as required by Objectify to instantiate the model object.
   *
   * @param id the Datastore key for the job
   * @param creatorEmail the hashed email of the user that created the PKB job
   * @param benchmarkJobInformationJson the PKB Job information proto stored as JSON string
   * @param created the timestamp the PKB Job was created.
   * @param cloudBuildJobId the Cloud Build job-id that is executing this PKB job
   * @param cloudBuildLogUri the Cloud Build URI to access the logs from Cloud Build job
   * @param result the final output from PKB for jobs that have completed.
   */
  public BenchmarkJobEntity(
      long id,
      String creatorEmail,
      String benchmarkJobInformationJson,
      Instant created,
      String cloudBuildJobId,
      String cloudBuildLogUri,
      BenchmarkJobResult result) {
    this.id = id;
    this.creatorEmail = creatorEmail;
    this.benchmarkJobInformationJson = benchmarkJobInformationJson;
    this.created = created;
    this.cloudBuildJobId = cloudBuildJobId;
    this.cloudBuildLogUri = cloudBuildLogUri;
    this.result = result;
  }

  /** Fluent builder for adding a job-id to an existing BenchmarkJob. */
  public BenchmarkJobEntity withId(long id) {
    return new BenchmarkJobEntity(
        id,
        creatorEmail,
        benchmarkJobInformationJson,
        created,
        cloudBuildJobId,
        cloudBuildLogUri,
        result);
  }

  /** Fluent builder for adding creator's hashed email to an existing BenchmarkJob. */
  public BenchmarkJobEntity withCreatorEmail(String creatorEmail) {
    return new BenchmarkJobEntity(
        id,
        creatorEmail,
        benchmarkJobInformationJson,
        created,
        cloudBuildJobId,
        cloudBuildLogUri,
        result);
  }

  /** Fluent builder for adding a PKB job-information JSON string to an existing BenchmarkJob. */
  public BenchmarkJobEntity withJobInformationJson(String benchmarkJobInformationJson) {
    return new BenchmarkJobEntity(
        id,
        creatorEmail,
        benchmarkJobInformationJson,
        created,
        cloudBuildJobId,
        cloudBuildLogUri,
        result);
  }

  /** Fluent builder for adding a create timestamp to an existing BenchmarkJob. */
  public BenchmarkJobEntity withCreated(Instant created) {
    return new BenchmarkJobEntity(
        id,
        creatorEmail,
        benchmarkJobInformationJson,
        created,
        cloudBuildJobId,
        cloudBuildLogUri,
        result);
  }

  /** Fluent builder for adding a Cloud Build job-id to an existing BenchmarkJob. */
  public BenchmarkJobEntity withCloudBuildJobId(String cloudBuildJobId) {
    return new BenchmarkJobEntity(
        id,
        creatorEmail,
        benchmarkJobInformationJson,
        created,
        cloudBuildJobId,
        cloudBuildLogUri,
        result);
  }

  /** Fluent builder for adding a Cloud Build log URI to an existing BenchmarkJob. */
  public BenchmarkJobEntity withCloudBuildLogUri(String cloudBuildLogUri) {
    return new BenchmarkJobEntity(
        id,
        creatorEmail,
        benchmarkJobInformationJson,
        created,
        cloudBuildJobId,
        cloudBuildLogUri,
        result);
  }

  /** Fluent builder for adding a results to an existing {@code FINISHED} BenchmarkJob. */
  public BenchmarkJobEntity withResult(BenchmarkJobResult result) {
    return new BenchmarkJobEntity(
        id,
        creatorEmail,
        benchmarkJobInformationJson,
        created,
        cloudBuildJobId,
        cloudBuildLogUri,
        result);
  }

  @Override
  public boolean equals(Object o) {
    if (this == o) {
      return true;
    }
    if (o == null || getClass() != o.getClass()) {
      return false;
    }
    BenchmarkJobEntity that = (BenchmarkJobEntity) o;
    return Objects.equal(id, that.id)
        && Objects.equal(creatorEmail, that.creatorEmail)
        && Objects.equal(benchmarkJobInformationJson, that.benchmarkJobInformationJson)
        && Objects.equal(created, that.created)
        && Objects.equal(cloudBuildJobId, that.cloudBuildJobId)
        && Objects.equal(cloudBuildLogUri, that.cloudBuildLogUri)
        && Objects.equal(result, that.result);
  }

  @Override
  public int hashCode() {
    return Objects.hashCode(
        id,
        creatorEmail,
        benchmarkJobInformationJson,
        created,
        cloudBuildJobId,
        cloudBuildLogUri,
        result);
  }

  public long getId() {
    return id;
  }

  public String getCreatorEmail() {
    return creatorEmail;
  }

  public String getBenchmarkJobInformationJson() {
    return benchmarkJobInformationJson;
  }

  public Instant getCreated() {
    return created;
  }

  public String getCloudBuildJobId() {
    return cloudBuildJobId;
  }

  public String getCloudBuildLogUri() {
    return cloudBuildLogUri;
  }

  public BenchmarkJobResult getResult() {
    return result;
  }

  /** Private no-args constructor for Objectify. */
  private BenchmarkJobEntity() {}
}
