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

package com.google.cloud.solutions.trinoscaler.gcp;

import static com.google.common.collect.ImmutableList.toImmutableList;
import static com.google.common.collect.ImmutableSet.toImmutableSet;

import com.google.api.LabelDescriptor;
import com.google.cloud.compute.v1.Instance;
import com.google.cloud.compute.v1.InstancesClient;
import com.google.cloud.compute.v1.ListInstancesRequest;
import com.google.cloud.monitoring.v3.QueryServiceClient;
import com.google.cloud.solutions.trinoscaler.ClusterInformation;
import com.google.cloud.solutions.trinoscaler.ClusterInspectionService;
import com.google.cloud.solutions.trinoscaler.ClusterMetrics;
import com.google.cloud.solutions.trinoscaler.Factory;
import com.google.common.collect.ImmutableList;
import com.google.common.flogger.GoogleLogger;
import com.google.monitoring.v3.QueryTimeSeriesRequest;
import com.google.protobuf.Timestamp;
import com.google.protobuf.util.Timestamps;
import java.io.IOException;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;
import java.util.stream.StreamSupport;
import org.apache.commons.lang3.tuple.ImmutablePair;
import org.apache.commons.lang3.tuple.Pair;

/** Extracts Dataproc cluster metrics using Cloud Monitoring. */
public class DataprocClusterInspectionService implements ClusterInspectionService {
  private static final GoogleLogger logger = GoogleLogger.forEnclosingClass();

  private final ClusterInformation clusterInfo;
  private final Factory<QueryServiceClient> queryServiceClientFactory;
  private final Factory<InstancesClient> gceInstancesClientFactory;
  private final String cpuUtilizationMql;
  private final String queryParent;

  /** Simple all parameter constructor. */
  public DataprocClusterInspectionService(
      ClusterInformation clusterInfo,
      Factory<QueryServiceClient> queryServiceClientFactory,
      Factory<InstancesClient> gceInstancesClientFactory,
      String cpuUtilizationMql) {
    this.clusterInfo = clusterInfo;
    this.queryServiceClientFactory = queryServiceClientFactory;
    this.gceInstancesClientFactory = gceInstancesClientFactory;
    this.cpuUtilizationMql = cpuUtilizationMql;
    this.queryParent = String.format("projects/%s", clusterInfo.projectId());
  }

  @Override
  public ClusterMetrics inspectCluster() throws IOException {
    // Fetch cluster metrics
    try (var metricsExtractor = createMetricsExtractor()) {
      var rawMetrics =
          metricsExtractor.extractMetrics().entrySet().stream()
              .map(
                  instanceMetric ->
                      ClusterMetrics.WorkerMetrics.create(
                          instanceMetric.getKey(),
                          instanceMetric.getValue().stream()
                              .mapToDouble(ImmutablePair::getValue)
                              .average()
                              .getAsDouble()))
              .collect(Collectors.toList());

      var clusterAvgCpuUtilizationRunningWorkers =
          rawMetrics.stream()
              .mapToDouble(ClusterMetrics.WorkerMetrics::avgCpuUtilization)
              .average()
              .orElse(0);

      logger.atInfo().log(
          "avgCpu: %s, workers: %s", clusterAvgCpuUtilizationRunningWorkers, rawMetrics.size());

      var secondaryRunningWorkerNames = listRunningSecondaryWorkerNames();
      logger.atInfo().log("Running Secondary Worker Names: %s", secondaryRunningWorkerNames);

      var secondaryWorkersMetrics =
          rawMetrics.stream()
              .filter(
                  instanceMetrics ->
                      secondaryRunningWorkerNames.contains(instanceMetrics.workerName()))
              .collect(Collectors.toList());

      logger.atInfo().log("Secondary WorkerMetrics:%n%s", secondaryWorkersMetrics);

      return ClusterMetrics.create(
          clusterInfo, clusterAvgCpuUtilizationRunningWorkers, secondaryWorkersMetrics);
    }
  }

  private Set<String> listRunningSecondaryWorkerNames() throws IOException {

    try (var gceInstancesClient = gceInstancesClientFactory.create()) {

      return StreamSupport.stream(
              gceInstancesClient
                  .list(
                      ListInstancesRequest.newBuilder()
                          .setProject(clusterInfo.projectId())
                          .setZone(clusterInfo.zone())
                          .setFilter("name:" + clusterInfo.name() + "-sw*")
                          .build())
                  .iterateAll()
                  .spliterator(),
              false)
          .filter(
              item ->
                  item.getStatus().equals("RUNNING")
                      && !item.containsLabels(
                          DataprocInstanceShutdownService.TRINO_WORKER_SHUTTING_DOWN_LABEL_KEY))
          .map(Instance::getName)
          .collect(toImmutableSet());
    }
  }

  private InstanceTimeSeriesExtractor createMetricsExtractor() throws IOException {
    return new InstanceTimeSeriesExtractor(
        queryServiceClientFactory.create(),
        queryParent,
        String.format(cpuUtilizationMql, clusterInfo.region(), clusterInfo.name()));
  }

  private static class InstanceTimeSeriesExtractor implements AutoCloseable {

    private final QueryServiceClient queryServiceClient;
    private final String parent;
    private final String query;

    public InstanceTimeSeriesExtractor(
        QueryServiceClient queryServiceClient, String parent, String query) {
      this.queryServiceClient = queryServiceClient;
      this.parent = parent;
      this.query = query;
    }

    @Override
    public void close() {
      queryServiceClient.close();
      queryServiceClient.shutdown();
    }

    Map<String, ImmutableList<ImmutablePair<Timestamp, Double>>> extractMetrics() {
      logger.atInfo().log("monitoring metrics for timeseries query:%n%s", query);

      var pagedResponse =
          queryServiceClient.queryTimeSeries(
              QueryTimeSeriesRequest.newBuilder().setName(parent).setQuery(query).build());

      return StreamSupport.stream(pagedResponse.iteratePages().spliterator(), false)
          .flatMap(
              page -> {
                logger.atInfo().log("Processing Metrics Page");
                var index =
                    page.getResponse()
                        .getTimeSeriesDescriptor()
                        .getLabelDescriptorsList()
                        .indexOf(
                            LabelDescriptor.newBuilder().setKey("metric.instance_name").build());

                return StreamSupport.stream(page.getValues().spliterator(), false)
                    .flatMap(
                        value -> {
                          String instanceName = value.getLabelValues(index).getStringValue();

                          return value.getPointDataList().stream()
                              .map(
                                  pointData ->
                                      Pair.of(
                                          instanceName,
                                          ImmutablePair.of(
                                              pointData.getTimeInterval().getEndTime(),
                                              pointData.getValues(0).getDoubleValue())));
                        });
              })
          .collect(
              Collectors.groupingBy(
                  Pair::getKey,
                  Collectors.mapping(
                      Pair::getValue,
                      Collectors.collectingAndThen(
                          Collectors.toList(),
                          x ->
                              x.stream()
                                  .sorted((o1, o2) -> Timestamps.compare(o1.left, o2.left))
                                  .collect(toImmutableList())))));
    }
  }
}
