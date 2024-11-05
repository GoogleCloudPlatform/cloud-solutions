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
import com.google.api.gax.rpc.ApiCallContext;
import com.google.api.gax.rpc.OperationCallable;
import com.google.api.gax.rpc.UnaryCallable;
import java.io.Serializable;
import java.util.ArrayList;
import java.util.function.Supplier;

/**
 * A composable Services stub that implements a Fake client stub based on provided
 * ApiFutureFactories (REST Client) or OperationFutureFactory (gRPC Client).
 */
public class PatchyStub extends TestingBackgroundResource implements Serializable {

  private final ArrayList<BaseOperationFuture.OperationFutureFactory<?, ?, ?>>
      operationCallableFactories = new ArrayList<>();
  private final ArrayList<BaseUnaryApiFuture.ApiFutureFactory<?, ?>> unaryCallableFactories =
      new ArrayList<>();

  public void addUnaryCallableFactory(
      BaseUnaryApiFuture.ApiFutureFactory<?, ?> unaryCallableFactory) {
    unaryCallableFactories.add(unaryCallableFactory);
  }

  public void addOperationCallableFactory(
      BaseOperationFuture.OperationFutureFactory<?, ?, ?> operationCallableFactory) {
    operationCallableFactories.add(operationCallableFactory);
  }

  public void clearAllFactories() {
    operationCallableFactories.clear();
    unaryCallableFactories.clear();
  }

  /**
   * Returns the correct gRPC operations callable.
   *
   * <p>Matches from the registered list by matching request and response classes.
   */
  @SuppressWarnings("unchecked") // Checks are done in PatchyUnaryCallable#matchIO
  public <I, O, M> OperationCallable<I, O, M> findOperationsCallable(
      Class<I> inputClass,
      Class<O> outputClass,
      Supplier<OperationCallable<I, O, M>> defaultCallable) {
    if (isShutdown() || isTerminated()) {
      throw new RuntimeException("Stub already shutdown or terminated");
    }

    return operationCallableFactories.stream()
        .filter(factory -> factory.matchIo(inputClass, outputClass))
        .findFirst()
        .map(PatchyOperationsCallable::new)
        .map(p -> (OperationCallable<I, O, M>) p)
        .orElseGet(defaultCallable);
  }

  /**
   * Returns the correct gRPC service callable.
   *
   * <p>Matches from the registered list by matching request and response classes.
   */
  @SuppressWarnings("unchecked") // Checks are done in PatchyUnaryCallable#matchIO
  public <I, O> UnaryCallable<I, O> findCallable(
      Class<I> inputClass, Class<O> outputClass, Supplier<UnaryCallable<I, O>> defaultCallable) {
    if (isShutdown() || isTerminated()) {
      throw new RuntimeException("Stub already shutdown or terminated");
    }

    return unaryCallableFactories.stream()
        .filter(factory -> factory.matchIo(inputClass, outputClass))
        .findFirst()
        .map(PatchyCallable::new)
        .map(p -> (UnaryCallable<I, O>) p)
        .orElseGet(defaultCallable);
  }

  private static final class PatchyCallable<I, O> extends UnaryCallable<I, O>
      implements Serializable {
    private final BaseUnaryApiFuture.ApiFutureFactory<I, O> factory;

    public PatchyCallable(BaseUnaryApiFuture.ApiFutureFactory<I, O> factory) {
      this.factory = factory;
    }

    @Override
    public ApiFuture<O> futureCall(I request, ApiCallContext context) {
      return factory.create(request, context);
    }
  }

  /** Callable Wrapper that instantiates a callable and returns the function. */
  private static final class PatchyOperationsCallable<RequestT, ResponseT, MetadataT>
      extends OperationCallable<RequestT, ResponseT, MetadataT> implements Serializable {

    private final BaseOperationFuture.OperationFutureFactory<RequestT, ResponseT, MetadataT>
        factory;

    public PatchyOperationsCallable(
        BaseOperationFuture.OperationFutureFactory<RequestT, ResponseT, MetadataT> factory) {
      this.factory = factory;
    }

    @Override
    public OperationFuture<ResponseT, MetadataT> futureCall(
        RequestT request, ApiCallContext context) {
      return factory.create(request, context);
    }

    @Override
    public OperationFuture<ResponseT, MetadataT> resumeFutureCall(
        String operationName, ApiCallContext context) {
      throw new UnsupportedOperationException("resume not supported");
    }

    @Override
    public ApiFuture<Void> cancel(String operationName, ApiCallContext context) {
      throw new UnsupportedOperationException("resume not supported");
    }
  }
}
