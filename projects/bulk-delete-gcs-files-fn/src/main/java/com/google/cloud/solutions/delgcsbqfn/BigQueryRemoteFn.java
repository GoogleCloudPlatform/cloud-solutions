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

import static com.google.common.base.Preconditions.checkNotNull;

import java.util.List;
import java.util.Map;
import org.checkerframework.checker.nullness.qual.Nullable;

/**
 * BigQuery Remote function interface.
 *
 * @see <a
 *     href="https://cloud.google.com/bigquery/docs/reference/standard-sql/remote-functions#input_format">
 *     Interface details</a>
 */
public interface BigQueryRemoteFn {

  /**
   * Implement the actual remote function's processing logic, that receives the request in the given
   * format and returns a response in the BigQuery remote function's response format.
   *
   * <p>The implementation can sometimes split the initial request into sub-requests to process them
   * parallelly and then combine the responses <b>In-Order</b> of the request item order.
   *
   * @param request the BigQuery remote func request
   * @return the processed output for the request items in the same order
   */
  BigQueryRemoteFnResponse process(BigQueryRemoteFnRequest request);

  /**
   * BigQuery Remote Function Request data model.
   *
   * @see <a
   *     href="https://cloud.google.com/bigquery/docs/reference/standard-sql/remote-functions#input_format">
   *     Input Format</a>
   */
  record BigQueryRemoteFnRequest(
      String requestId,
      String caller,
      String sessionUser,
      @Nullable Map<String, String> userDefinedContext,
      List<List<Object>> calls) {}

  /**
   * BigQuery Remote Function Response data model.
   *
   * @see <a
   *     href="https://cloud.google.com/bigquery/docs/reference/standard-sql/remote-functions#output_format">
   *     Output Format</a>
   */
  record BigQueryRemoteFnResponse(List<?> replies, String errorMessage) {

    public static BigQueryRemoteFnResponse withReplies(List<?> replies) {
      return new BigQueryRemoteFnResponse(checkNotNull(replies), null);
    }

    public static BigQueryRemoteFnResponse withErrorMessage(String errorMessage) {
      return new BigQueryRemoteFnResponse(null, errorMessage);
    }
  }
}
