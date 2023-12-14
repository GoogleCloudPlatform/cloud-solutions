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

package com.google.cloud.solutions.satools.common.testing.stubs;

import com.google.api.gax.rpc.ApiCallContext;
import com.google.cloud.solutions.satools.common.testing.AssertValidator;

/**
 * Verifies that the client created the expected request and then returns a constant
 * operation-response.
 */
public class VerifyingConstantOperationFuture<I, O, M>
    extends BaseOperationFuture.OperationFutureFactory<I, O, M> {
  private final BaseOperationFuture.OperationData<O, M> constantResponse;

  private final AssertValidator<I> inputValidator;

  /** Simple constructor. */
  public VerifyingConstantOperationFuture(
      Class<I> requestClass,
      Class<O> responseClass,
      AssertValidator<I> inputValidator,
      BaseOperationFuture.OperationData<O, M> constantResponse) {
    super(requestClass, responseClass);
    this.constantResponse = constantResponse;
    this.inputValidator = inputValidator;
  }

  @Override
  public BaseOperationFuture<O, M> create(I request, ApiCallContext context) {
    inputValidator.validate(request);
    return new BaseOperationFuture<>(constantResponse);
  }
}
