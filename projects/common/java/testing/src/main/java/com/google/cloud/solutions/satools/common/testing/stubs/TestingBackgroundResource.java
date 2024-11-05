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

import com.google.api.gax.core.BackgroundResource;
import java.io.Serializable;
import java.util.concurrent.TimeUnit;

/**
 * Static implementation of {@link com.google.api.gax.core.BackgroundResource} providing testing
 * safe values. Use of this class simplifies implementing most of Google Cloud's gRPC API client
 * fakes.
 */
public class TestingBackgroundResource implements BackgroundResource, Serializable {

  private boolean closed;
  private boolean shutdown;

  public TestingBackgroundResource() {
    this.closed = false;
    this.shutdown = false;
  }

  @Override
  public void close() {
    closed = true;
  }

  @Override
  public void shutdown() {
    close();
    shutdown = true;
  }

  @Override
  public boolean isShutdown() {
    return shutdown;
  }

  @Override
  public boolean isTerminated() {
    return (closed && shutdown);
  }

  @Override
  public void shutdownNow() {
    shutdown = true;
  }

  @Override
  public boolean awaitTermination(long l, TimeUnit timeUnit) {
    shutdown();
    return shutdown;
  }
}
