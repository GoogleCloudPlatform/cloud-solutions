/*
 * Copyright (C) 2024 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may not
 * use this file except in compliance with the License. You may obtain a copy of
 * the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations under
 * the License.
 */

package com.google.cloud.solutions.dataflow.avrotospannerscd.utils;

import com.google.api.gax.retrying.RetrySettings;
import com.google.api.gax.rpc.FixedHeaderProvider;
import com.google.cloud.spanner.SpannerOptions;
import java.io.Serializable;
import org.apache.beam.sdk.io.gcp.spanner.SpannerConfig;
import org.threeten.bp.Duration;

/** Provides SpannerOptions. */
public interface SpannerOptionsFactory extends Serializable {
  SpannerOptions getSpannerOptions();

  /** Provides SpannerOptions for the production pipeline. */
  class DefaultSpannerOptionsFactory implements SpannerOptionsFactory {

    private final SpannerConfig spannerConfig;

    public DefaultSpannerOptionsFactory(SpannerConfig spannerConfig) {
      this.spannerConfig = spannerConfig;
    }

    @Override
    public SpannerOptions getSpannerOptions() {
      SpannerOptions.Builder optionsBuilder =
          SpannerOptions.newBuilder()
              .setHeaderProvider(
                  FixedHeaderProvider.create(
                      "User-Agent", "cloud-solutions/dataflow-gcs-avro-to-spanner-scd-v2"));

      if (spannerConfig.getProjectId() != null && spannerConfig.getProjectId().get() != null) {
        optionsBuilder.setProjectId(spannerConfig.getProjectId().get());
      }

      RetrySettings retrySettings =
          RetrySettings.newBuilder()
              .setInitialRpcTimeout(Duration.ofHours(2))
              .setMaxRpcTimeout(Duration.ofHours(2))
              .setTotalTimeout(Duration.ofHours(2))
              .setRpcTimeoutMultiplier(1.0)
              .setInitialRetryDelay(Duration.ofSeconds(2))
              .setMaxRetryDelay(Duration.ofSeconds(60))
              .setRetryDelayMultiplier(1.5)
              .setMaxAttempts(100)
              .build();

      optionsBuilder.getSpannerStubSettingsBuilder().readSettings().setRetrySettings(retrySettings);

      optionsBuilder
          .getSpannerStubSettingsBuilder()
          .batchWriteSettings()
          .setRetrySettings(retrySettings);

      optionsBuilder
          .getSpannerStubSettingsBuilder()
          .beginTransactionSettings()
          .setRetrySettings(retrySettings);

      optionsBuilder
          .getSpannerStubSettingsBuilder()
          .applyToAllUnaryMethods(
              builder -> {
                builder.setRetrySettings(retrySettings);
                return null;
              });

      return optionsBuilder.build();
    }
  }
}
