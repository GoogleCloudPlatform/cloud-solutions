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

import com.google.cloud.solutions.trinoscaler.scaler.WorkerShutdownService;
import com.google.common.flogger.GoogleLogger;
import com.google.common.flogger.StackSize;
import java.io.IOException;
import java.time.Duration;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;

/**
 * A runnable task that sends {@code SHUTTING_DOWN} command to Trino Worker and stops the VM after
 * graceful shutdown of the Trino worker.
 *
 * <p>Refer to Trino <a href="https://trino.io/docs/current/admin/graceful-shutdown.html">Graceful
 * worker shutdown</a> for details of the shutdown protocol. The task waits for the Trino worker's
 * status to change from {@code SHUTTING_DOWN} to trigger and workerShutdown.
 */
public class TrinoWorkerShutdownTask implements Runnable {
  private static final GoogleLogger logger = GoogleLogger.forEnclosingClass();

  private static final Duration SHUTDOWN_POLLING_DURATION = Duration.ofSeconds(10);

  private final OkHttpClient okHttpClient;

  private final WorkerShutdownService workerShutdownService;

  private final Duration gracefulShutdownDuration;

  private final String workerName;

  private final String workerStateUrl;

  /** Simple all parameter constructor. */
  public TrinoWorkerShutdownTask(
      OkHttpClient okHttpClient,
      WorkerShutdownService workerShutdownService,
      Duration gracefulShutdownDuration,
      String workerName,
      int workerTrinoPort) {
    this.okHttpClient = okHttpClient;
    this.workerShutdownService = workerShutdownService;
    this.gracefulShutdownDuration = gracefulShutdownDuration;
    this.workerName = workerName;
    this.workerStateUrl = String.format("http://%s:%s/v1/info/state", workerName, workerTrinoPort);
  }

  public String getWorkerName() {
    return workerName;
  }

  @Override
  public void run() {
    try {
      sendShutDown();
      waitTillTrinoWorkerShutdown();
      workerShutdownService.shutdownWorker(workerName);
    } catch (IOException | InterruptedException exception) {
      logger.atSevere().withCause(exception).withStackTrace(StackSize.SMALL).log(
          "error shutting down worker: " + workerName);
    }
  }

  private void sendShutDown() throws IOException {
    var request =
        new Request.Builder()
            .url(workerStateUrl)
            .put(
                RequestBody.create(
                    TrinoWorkerStates.SHUTTING_DOWN.statusString(),
                    MediaType.get("application/json")))
            .addHeader("X-Trino-User", "admin")
            .build();

    try (var response = okHttpClient.newCall(request).execute()) {
      if (response.code() != 200) {
        throw new RuntimeException("Error shutting down worker " + workerName);
      }
      logger.atInfo().log("SHUTTING_DOWN sent successfully to: %s", workerName);
    }
  }

  private String getCurrentState() throws WorkerUnreachable {
    var request =
        new Request.Builder().url(workerStateUrl).addHeader("X-Trino-User", "admin").build();

    try (var response = okHttpClient.newCall(request).execute()) {
      return response.body().string().trim();
    } catch (IOException ioException) {
      throw new WorkerUnreachable("Error fetching status for worker " + workerName);
    }
  }

  private void waitTillTrinoWorkerShutdown() throws InterruptedException, IOException {

    try {
      workerShutdownService.markWorkerForShutdown(workerName);

      // Wait for graceful shutdown duration before polling the worker
      Thread.sleep(gracefulShutdownDuration.toMillis());
      do {
        Thread.sleep(SHUTDOWN_POLLING_DURATION.toMillis());
      } while (!isWorkerShutdown());

    } catch (IOException ex) {
      logger.atInfo().withCause(ex).withStackTrace(StackSize.SMALL).log(
          "error applying gce label for %s", workerName);
    }
  }

  private boolean isWorkerShutdown() {
    try {
      var status = getCurrentState();
      logger.atInfo().log("Worker [%s] status: %s", workerName, status);
      if (!TrinoWorkerStates.SHUTTING_DOWN.statusString().equals(status)) {
        logger.atInfo().log(
            "worker status( " + status + " ) changed from SHUTTING_DOWN: " + workerName);
        return true;
      }

    } catch (WorkerUnreachable workerUnreachable) {
      logger.atInfo().log("Worker probably down: " + workerName);
      return true;
    }

    return false;
  }

  enum TrinoWorkerStates {
    ACTIVE("\"ACTIVE\""),
    SHUTTING_DOWN("\"SHUTTING_DOWN\""),
    NO_RESPONSE("");
    private final String statusString;

    TrinoWorkerStates(String statusString) {
      this.statusString = statusString;
    }

    public String statusString() {
      return statusString;
    }
  }

  private static class WorkerUnreachable extends IOException {
    public WorkerUnreachable(String message) {
      super(message);
    }
  }
}
