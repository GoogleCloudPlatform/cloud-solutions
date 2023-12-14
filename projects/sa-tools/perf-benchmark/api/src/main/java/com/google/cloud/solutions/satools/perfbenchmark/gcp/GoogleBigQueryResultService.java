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

package com.google.cloud.solutions.satools.perfbenchmark.gcp;

import com.google.cloud.bigquery.QueryJobConfiguration;
import com.google.cloud.solutions.satools.perfbenchmark.CustomBenchmarkResultService;
import com.google.cloud.solutions.satools.perfbenchmark.PerfkitRunnerConfig;
import com.google.cloud.solutions.satools.perfbenchmark.entity.BenchmarkJobEntity;
import com.google.cloud.solutions.satools.perfbenchmark.entity.BenchmarkJobResult;
import com.google.common.collect.ImmutableList;
import com.google.common.flogger.GoogleLogger;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.function.Function;
import java.util.regex.Pattern;
import org.apache.commons.text.StringSubstitutor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.Resource;
import org.springframework.stereotype.Service;

/** Google Cloud BigQuery service bean that provides implementation to fetch PKB results. */
@Service
public class GoogleBigQueryResultService implements CustomBenchmarkResultService {

  private static final GoogleLogger logger = GoogleLogger.forEnclosingClass();

  private final BigQueryClientFactory bqClientFactory;
  private final String resultsSql;

  private final PerfkitRunnerConfig config;

  /** Simple all parameter constructor to instantiate BigQuery service bean. */
  public GoogleBigQueryResultService(
      BigQueryClientFactory bqClientFactory,
      PerfkitRunnerConfig config,
      @Value("classpath:sqls/custom_benchmark_result.sql") Resource resultsSqlResource)
      throws IOException {
    this.bqClientFactory = bqClientFactory;
    this.config = config;
    this.resultsSql =
        new String(resultsSqlResource.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
  }

  @Override
  public BenchmarkJobResult retrieveResult(BenchmarkJobEntity benchmarkJobEntity) {

    var metricsResultBuilder = new ArrayList<BenchmarkJobResult.MetricResult>();

    try {
      var queryParameters = new HashMap<String, String>();
      queryParameters.put("BQ_PROJECT", config.resultsBqProject());
      queryParameters.put("BQ_DATASET", config.resultsBqDataset());
      queryParameters.put("BQ_TABLE", config.resultsBqTable());
      queryParameters.put("BUILD_ID", benchmarkJobEntity.getCloudBuildJobId());

      var query = StringSubstitutor.replace(resultsSql, queryParameters);
      bqClientFactory
          .create()
          .query(
              QueryJobConfiguration.newBuilder(query)
                  .setUseLegacySql(false)
                  .setUseQueryCache(true)
                  .build())
          .iterateAll()
          .forEach(
              row ->
                  metricsResultBuilder.add(
                      BenchmarkJobResult.MetricResult.getDefaultInstance()
                          .withTimestamp(row.get("test_timestamp").getTimestampInstant())
                          .withMetric(row.get("metric").getStringValue())
                          .withValue(row.get("value").getDoubleValue())
                          .withLabels(
                              row.get("labels")
                                  .getStringValue()
                                  .transform(new LabelSplitterFn()))));
    } catch (InterruptedException interruptedException) {
      logger.atSevere().withCause(interruptedException).log(
          "bqResults fetch failed for: %s", benchmarkJobEntity.getCloudBuildJobId());
    }

    return BenchmarkJobResult.withMetrics(metricsResultBuilder);
  }

  private static class LabelSplitterFn implements Function<String, List<String>> {

    private static final Pattern LABEL_PATTERN = Pattern.compile("\\|([^\\|]+)\\|");

    @Override
    public List<String> apply(String labels) {
      if (labels == null || labels.isBlank()) {
        return List.of();
      }

      var matcher = LABEL_PATTERN.matcher(labels);
      var resultsBuilder = ImmutableList.<String>builder();

      while (matcher.find()) {
        resultsBuilder.add(matcher.group(1));
      }

      return resultsBuilder.build();
    }
  }
}
