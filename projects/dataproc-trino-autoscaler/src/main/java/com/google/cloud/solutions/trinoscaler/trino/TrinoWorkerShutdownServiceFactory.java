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

package com.google.cloud.solutions.trinoscaler.trino;

import static java.util.Objects.requireNonNullElse;

import com.google.cloud.solutions.trinoscaler.Factory;
import com.google.cloud.solutions.trinoscaler.scaler.WorkerShutdownService;
import com.google.common.flogger.GoogleLogger;
import com.google.common.flogger.StackSize;
import java.io.IOException;
import java.time.Duration;
import okhttp3.OkHttpClient;

/** Creates a task that gracefully shutdowns a Trino worker. */
public class TrinoWorkerShutdownServiceFactory {

  private static final int DEFAULT_TRINO_WORKER_PORT = 8060;

  private final Factory<OkHttpClient> okHttpClientFactory;

  private final Factory<WorkerShutdownService> workerShutdownServiceFactory;

  private final Duration gracefulShutdownDuration;

  private final int trinoWorkerPort;

  /** Simple all parameter constructor. */
  public TrinoWorkerShutdownServiceFactory(
      Factory<OkHttpClient> okHttpClientFactory,
      Factory<WorkerShutdownService> workerShutdownServiceFactory,
      Duration gracefulShutdownDuration,
      Integer trinoWorkerPort) {
    this.okHttpClientFactory = okHttpClientFactory;
    this.workerShutdownServiceFactory = workerShutdownServiceFactory;
    this.gracefulShutdownDuration = gracefulShutdownDuration;
    this.trinoWorkerPort = requireNonNullElse(trinoWorkerPort, DEFAULT_TRINO_WORKER_PORT);
  }

  /** Returns a runnable task to shut down a specific worker specified using the worker name. */
  public TrinoWorkerShutdownTask createWorkerShutdownTask(String workerName) {
    try {
      return new TrinoWorkerShutdownTask(
          okHttpClientFactory.create(),
          workerShutdownServiceFactory.create(),
          gracefulShutdownDuration,
          workerName,
          trinoWorkerPort);
    } catch (IOException ioException) {
      GoogleLogger.forEnclosingClass()
          .atSevere()
          .withCause(ioException)
          .withStackTrace(StackSize.SMALL)
          .log("error creating Trino Shutdown Task");
      throw new RuntimeException(
          "error creating Trino Shutdown Task (" + workerName + ")", ioException);
    }
  }
}
