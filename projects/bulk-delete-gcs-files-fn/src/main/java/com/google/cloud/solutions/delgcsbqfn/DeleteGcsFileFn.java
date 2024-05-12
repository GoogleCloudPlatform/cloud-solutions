/*
 * Copyright 2024 Google LLC
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

package com.google.cloud.solutions.delgcsbqfn;

import com.google.cloud.storage.BlobId;
import com.google.cloud.storage.StorageBatchResult;
import com.google.cloud.storage.StorageException;
import com.google.common.collect.Lists;
import java.util.List;
import java.util.concurrent.Callable;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import org.apache.commons.lang3.tuple.ImmutablePair;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

/**
 * Implementation of BigQuery remote function that micro-batches and deletes files on Cloud Storage
 * using the Storage Batch API.
 */
@Component
public class DeleteGcsFileFn implements BigQueryRemoteFn {

  private static final int GCS_BATCH_MAX_SIZE = 100;

  @Autowired StorageClientFactory storageClientFactory;

  protected ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor();

  @Override
  public BigQueryRemoteFnResponse process(BigQueryRemoteFnRequest request) {

    var uriList = request.calls().stream().map(List::getFirst).map(Object::toString).toList();

    var results =
        Lists.partition(uriList, GCS_BATCH_MAX_SIZE).stream()
            .map(batchedUris -> new BatchDeleteRunner(batchedUris, storageClientFactory))
            .map(runner -> CompletableFuture.supplyAsync(runner::call, executor))
            .map(CompletableFuture::join)
            .flatMap(List::stream)
            .toList();

    return BigQueryRemoteFnResponse.withReplies(results);
  }

  private record BatchDeleteRunner(List<String> uris, StorageClientFactory storageFactory)
      implements Callable<List<String>> {

    @Override
    public List<String> call() {
      try (var client = storageFactory.getObject()) {
        // client is built in previous step and would not be null.
        @SuppressWarnings("ConstantConditions")
        var deleteBatch = client.batch();
        var resultsFuture =
            uris.stream()
                .map(
                    uri ->
                        new GcsBatchDeleteResult(
                            uri, deleteBatch.delete(BlobId.fromGsUtilUri(uri))))
                .toList();
        deleteBatch.submit();

        return resultsFuture.stream()
            .map(GcsBatchDeleteResult::get)
            .map(ImmutablePair::getValue)
            .toList();
      } catch (Exception e) {
        throw new RuntimeException(e);
      }
    }
  }

  private record GcsBatchDeleteResult(String uri, StorageBatchResult<Boolean> resultFuture) {

    public ImmutablePair<String, String> get() {
      return ImmutablePair.of(uri, readResult());
    }

    private String readResult() {
      try {
        return resultFuture.get() ? "Completed" : "NotFound";
      } catch (StorageException exp) {
        return "Not Deleted: " + exp.getMessage();
      }
    }
  }
}
