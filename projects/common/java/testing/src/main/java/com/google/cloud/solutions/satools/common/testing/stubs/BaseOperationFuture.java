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
import com.google.api.gax.longrunning.OperationFuture;
import com.google.api.gax.longrunning.OperationSnapshot;
import com.google.api.gax.retrying.RetryingFuture;
import com.google.api.gax.rpc.ApiCallContext;
import java.io.Serializable;
import java.util.concurrent.Executor;
import java.util.concurrent.TimeUnit;

/**
 * Stub implementation for help in simplifying {@link com.google.api.core.ApiFuture} returns from
 * fake clients.
 */
public class BaseOperationFuture<ResponseT, MetadataT>
    implements OperationFuture<ResponseT, MetadataT> {

  private final ResponseT response;
  private final MetadataT metadata;

  public BaseOperationFuture(ResponseT response, MetadataT metadata) {
    this.response = response;
    this.metadata = metadata;
  }

  public BaseOperationFuture(OperationData<ResponseT, MetadataT> operationData) {
    this(operationData.response(), operationData.metadata());
  }

  /** Helper class to simplify the creation of {@link OperationFuture}s. */
  public record OperationData<ResponseT, MetadataT>(ResponseT response, MetadataT metadata) {
    public static <ResponseT, MetadataT> OperationData<ResponseT, MetadataT> of(
        ResponseT response, MetadataT metadata) {
      return new OperationData<>(response, metadata);
    }
  }

  /** Helper abstract class to simplify the creation of {@link OperationFuture}s. for testing. */
  public abstract static class OperationFutureFactory<RequestT, ResponseT, MetadataT>
      implements Serializable {

    private final Class<RequestT> requestClass;

    private final Class<ResponseT> responseClass;

    public OperationFutureFactory(Class<RequestT> requestClass, Class<ResponseT> responseClass) {
      this.requestClass = requestClass;
      this.responseClass = responseClass;
    }

    public abstract BaseOperationFuture<ResponseT, MetadataT> create(
        RequestT request, ApiCallContext context);

    public final boolean matchIo(Class<?> requestClass, Class<?> responseClass) {
      return (this.requestClass.equals(requestClass) && this.responseClass.equals(responseClass));
    }
  }

  @Override
  public String getName() {
    return null;
  }

  @Override
  public ApiFuture<OperationSnapshot> getInitialFuture() {
    return null;
  }

  @Override
  public RetryingFuture<OperationSnapshot> getPollingFuture() {
    return null;
  }

  @Override
  public ApiFuture<MetadataT> peekMetadata() {
    return null;
  }

  @Override
  public ApiFuture<MetadataT> getMetadata() {
    return new BaseUnaryApiFuture<>(metadata);
  }

  @Override
  public void addListener(Runnable listener, Executor executor) {
    throw new UnsupportedOperationException("addListener not supported in stub");
  }

  @Override
  public boolean cancel(boolean mayInterruptIfRunning) {
    return false;
  }

  @Override
  public boolean isCancelled() {
    return false;
  }

  @Override
  public boolean isDone() {
    return true;
  }

  @Override
  public ResponseT get() {
    return response;
  }

  @Override
  public ResponseT get(long timeout, TimeUnit unit) {
    return response;
  }
}
