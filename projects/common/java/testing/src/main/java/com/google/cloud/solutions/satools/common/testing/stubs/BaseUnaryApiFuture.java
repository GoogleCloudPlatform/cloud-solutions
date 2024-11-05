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

import com.google.api.core.ApiFuture;
import com.google.api.gax.rpc.ApiCallContext;
import java.io.Serializable;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.Executor;
import java.util.concurrent.TimeUnit;

/**
 * Stub implementation for help in simplifying {@link com.google.api.gax.rpc.UnaryCallable} returns
 * from fake clients.
 */
public class BaseUnaryApiFuture<ResponseT> implements ApiFuture<ResponseT>, Serializable {

  private final ResponseT constantResponse;

  public BaseUnaryApiFuture(ResponseT constantResponse) {
    this.constantResponse = constantResponse;
  }

  /** Helper class to create {@link BaseUnaryApiFuture} instances for testing. */
  public abstract static class ApiFutureFactory<RequestT, ResponseT> implements Serializable {

    private final Class<RequestT> requestClass;
    private final Class<ResponseT> responseClass;

    public ApiFutureFactory(Class<RequestT> requestClass, Class<ResponseT> responseClass) {
      this.requestClass = requestClass;
      this.responseClass = responseClass;
    }

    public abstract BaseUnaryApiFuture<ResponseT> create(RequestT request, ApiCallContext context);

    public final boolean matchIo(Class<?> requestClass, Class<?> responseClass) {
      return (this.requestClass.equals(requestClass) && this.responseClass.equals(responseClass));
    }
  }

  @Override
  public final void addListener(Runnable runnable, Executor executor) {
    executor.execute(runnable);
  }

  @Override
  public final boolean cancel(boolean b) {
    return false;
  }

  @Override
  public final boolean isCancelled() {
    return false;
  }

  @Override
  public final boolean isDone() {
    return true;
  }

  public ResponseT get() {
    return constantResponse;
  }

  @Override
  @SuppressWarnings("NullableProblems")
  public final ResponseT get(long l, TimeUnit timeUnit)
      throws ExecutionException, InterruptedException {
    return get();
  }
}
