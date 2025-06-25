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

/** Verifies that the Client created the expected request and then returns a constant response. */
public class VerifyingUnaryCallableFactory<RequestT, ResponseT>
    extends BaseUnaryApiFuture.ApiFutureFactory<RequestT, ResponseT> {
  private final ResponseT provideResponse;

  private final AssertValidator<RequestT> inputValidator;

  /**
   * Simple constructor to instantiate the class.
   *
   * @param requestClass the type of Request
   * @param responseClass the type of Response
   * @param inputValidator the assertion validator for the request
   * @param provideResponse the response to return to the caller when request passed {@code
   *     inputValidator}
   */
  public VerifyingUnaryCallableFactory(
      Class<RequestT> requestClass,
      Class<ResponseT> responseClass,
      AssertValidator<RequestT> inputValidator,
      ResponseT provideResponse) {
    super(requestClass, responseClass);
    this.inputValidator = inputValidator;
    this.provideResponse = provideResponse;
  }

  @Override
  public BaseUnaryApiFuture<ResponseT> create(RequestT request, ApiCallContext context) {
    inputValidator.validate(request);
    return new BaseUnaryApiFuture<>(provideResponse);
  }
}
