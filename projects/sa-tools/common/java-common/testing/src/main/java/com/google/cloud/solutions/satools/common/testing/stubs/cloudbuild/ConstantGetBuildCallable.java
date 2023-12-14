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

import com.google.api.gax.rpc.ApiCallContext;
import com.google.cloud.solutions.satools.common.testing.stubs.BaseUnaryApiFuture;
import com.google.cloudbuild.v1.Build;
import com.google.cloudbuild.v1.GetBuildRequest;

/** Constant validator for CloudBuild request. */
public class ConstantGetBuildCallable
    extends BaseUnaryApiFuture.ApiFutureFactory<GetBuildRequest, Build> {

  private final Build constantBuildResponse;

  public ConstantGetBuildCallable(Build constantBuildResponse) {
    super(GetBuildRequest.class, Build.class);
    this.constantBuildResponse = constantBuildResponse;
  }

  @Override
  public BaseUnaryApiFuture<Build> create(GetBuildRequest request, ApiCallContext context) {
    return new BaseUnaryApiFuture<>(constantBuildResponse);
  }
}
