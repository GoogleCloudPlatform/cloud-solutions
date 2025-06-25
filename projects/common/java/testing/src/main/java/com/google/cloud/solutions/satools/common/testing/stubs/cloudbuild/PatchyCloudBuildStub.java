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

package com.google.cloud.solutions.satools.common.testing.stubs.cloudbuild;

import com.google.api.gax.rpc.OperationCallable;
import com.google.api.gax.rpc.UnaryCallable;
import com.google.cloud.devtools.cloudbuild.v1.stub.CloudBuildStub;
import com.google.cloud.solutions.satools.common.testing.stubs.PatchyStub;
import com.google.cloud.solutions.satools.common.testing.stubs.TestingBackgroundResource;
import com.google.cloudbuild.v1.Build;
import com.google.cloudbuild.v1.BuildOperationMetadata;
import com.google.cloudbuild.v1.CreateBuildRequest;
import com.google.cloudbuild.v1.GetBuildRequest;
import java.io.Serializable;
import java.util.concurrent.TimeUnit;

/** Fake Google Cloud Build Client Stub. */
public class PatchyCloudBuildStub extends CloudBuildStub implements Serializable {

  private final PatchyStub patchyStub;
  private final TestingBackgroundResource backgroundResource = new TestingBackgroundResource();

  public PatchyCloudBuildStub(PatchyStub patchyStub) {
    this.patchyStub = patchyStub;
  }

  @Override
  public OperationCallable<CreateBuildRequest, Build, BuildOperationMetadata>
      createBuildOperationCallable() {
    return patchyStub.findOperationsCallable(
        CreateBuildRequest.class, Build.class, super::createBuildOperationCallable);
  }

  @Override
  public UnaryCallable<GetBuildRequest, Build> getBuildCallable() {
    return patchyStub.findCallable(GetBuildRequest.class, Build.class, super::getBuildCallable);
  }

  @Override
  public void close() {
    backgroundResource.close();
  }

  @Override
  public void shutdown() {
    backgroundResource.shutdown();
  }

  @Override
  public boolean isShutdown() {
    return backgroundResource.isShutdown();
  }

  @Override
  public boolean isTerminated() {
    return backgroundResource.isTerminated();
  }

  @Override
  public void shutdownNow() {
    backgroundResource.shutdownNow();
  }

  @Override
  public boolean awaitTermination(long l, TimeUnit timeUnit) {
    return backgroundResource.awaitTermination(l, timeUnit);
  }
}
