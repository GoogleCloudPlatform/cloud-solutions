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

package com.google.cloud.solutions.satools.perfbenchmark.entity;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Objects;

/**
 * A record that represents the result of a benchmark job.
 *
 * <p>This can not be converted to a {@link Record} due to use of {@link
 * com.googlecode.objectify.Objectify}.
 */
public class BenchmarkJobResult {

  private ArrayList<MetricResult> metrics;

  public BenchmarkJobResult(ArrayList<MetricResult> metrics) {
    this.metrics = metrics;
  }

  public List<MetricResult> getMetrics() {
    return Collections.unmodifiableList(metrics);
  }

  public static BenchmarkJobResult withMetrics(List<MetricResult> metrics) {
    return new BenchmarkJobResult(metrics == null ? new ArrayList<>() : new ArrayList<>(metrics));
  }

  /**
   * Represents a metric from the PKB benchmark result.
   *
   * <p>This can not be converted to a {@link Record} due to use of {@link
   * com.googlecode.objectify.Objectify}.
   */
  public static class MetricResult {

    private Instant timestamp;
    private String metric;
    private Double value;
    private ArrayList<String> labels;

    /** All parameter constructor for the class. */
    public MetricResult(Instant timestamp, String metric, Double value, ArrayList<String> labels) {
      this.timestamp = timestamp;
      this.metric = metric;
      this.value = value;
      this.labels = labels;
    }

    public static MetricResult getDefaultInstance() {
      return new MetricResult(null, null, null, null);
    }

    public MetricResult withTimestamp(Instant timestamp) {

      return new MetricResult(timestamp, metric, value, labels);
    }

    public MetricResult withMetric(String metric) {

      return new MetricResult(timestamp, metric, value, labels);
    }

    public MetricResult withValue(Double value) {

      return new MetricResult(timestamp, metric, value, labels);
    }

    public MetricResult withLabels(List<String> labels) {
      return new MetricResult(timestamp, metric, value, new ArrayList<>(labels));
    }

    public Instant getTimestamp() {
      return timestamp;
    }

    public String getMetric() {
      return metric;
    }

    public Double getValue() {
      return value;
    }

    public List<String> getLabels() {
      return Collections.unmodifiableList(labels);
    }

    /** Required default constructor for Objectify. */
    private MetricResult() {}

    @Override
    public boolean equals(Object o) {
      if (this == o) {
        return true;
      }

      if (o == null || getClass() != o.getClass()) {
        return false;
      }

      MetricResult that = (MetricResult) o;
      return Objects.equals(timestamp, that.timestamp)
          && Objects.equals(metric, that.metric)
          && Objects.equals(value, that.value)
          && Objects.equals(labels, that.labels);
    }

    @Override
    public int hashCode() {
      return Objects.hash(timestamp, metric, value, labels);
    }
  }

  /** Default constructor for Objectify. */
  private BenchmarkJobResult() {}

  @Override
  public boolean equals(Object o) {
    if (this == o) {
      return true;
    }

    return (o instanceof BenchmarkJobResult that) && Objects.equals(metrics, that.metrics);
  }

  @Override
  public int hashCode() {
    return Objects.hash(metrics);
  }
}
