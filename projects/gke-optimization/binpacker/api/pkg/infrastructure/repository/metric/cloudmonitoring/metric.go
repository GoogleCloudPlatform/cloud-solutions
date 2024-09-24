// Copyright 2023 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package cloudmonitoring

import (
	"context"
	"fmt"
	"math"
	"os"

	"github.com/GoogleCloudPlatform/cloud-solutions/projects/sa-tools/gke_optimization/binpacker/api/pkg/domain/model/metric"
	"github.com/GoogleCloudPlatform/cloud-solutions/projects/sa-tools/gke_optimization/binpacker/api/pkg/domain/model/node"

	"google.golang.org/api/iterator"

	monitoring "cloud.google.com/go/monitoring/apiv3/v2"
	"cloud.google.com/go/monitoring/apiv3/v2/monitoringpb"
)

type MetricCloudMonitoringRepository struct{}

func NewMetricCloudMonitoringRepository() *MetricCloudMonitoringRepository {
	return &MetricCloudMonitoringRepository{}
}

const QueryCurrentWorkload = `fetch k8s_container
| metric 'kubernetes.io/container/uptime'
| filter namespace_name != 'kube-system'
| group_by [cluster_name, namespace_name,
	metadata.system_labels.top_level_controller_name, pod_name]
`

const QueryCPURequest = `fetch k8s_container
| metric 'kubernetes.io/container/cpu/request_cores'
| filter namespace_name != 'kube-system'
| group_by [cluster_name, namespace_name,
	metadata.system_labels.top_level_controller_name, pod_name],
	[value_request_cores_aggregate: aggregate(value.request_cores)]
| group_by 1h, mean(val())
`

const QueryCPULimit = `fetch k8s_container
| metric 'kubernetes.io/container/cpu/limit_cores'
| filter namespace_name != 'kube-system'
| group_by [cluster_name, namespace_name,
	metadata.system_labels.top_level_controller_name, pod_name],
	[value_limit_cores_aggregate: aggregate(value.limit_cores)]
| group_by 1h, mean(val())
`

const QueryMemoryRequest = `fetch k8s_container
| metric 'kubernetes.io/container/memory/request_bytes'
| filter namespace_name != 'kube-system'
| group_by [cluster_name, namespace_name,
	metadata.system_labels.top_level_controller_name, pod_name],
	[value_request_memory_aggregate: aggregate(request_bytes)]
| group_by 1h, mean(val())
`

const QueryMemoryLimit = `fetch k8s_container
| metric 'kubernetes.io/container/memory/limit_bytes'
| filter namespace_name != 'kube-system'
| group_by [cluster_name, namespace_name,
	metadata.system_labels.top_level_controller_name, pod_name],
	[value_limit_memory_aggregate: aggregate(limit_bytes)]
| group_by 1h, mean(val())
`

func CPURequests(m metric.Metrics) []node.CPU {
	result := make([]node.CPU, 0, len(m))
	for _, v := range m {
		result = append(result, node.CPU(v.CPURequest))
	}
	return result
}

func GetClusterNames(m metric.Metrics) []string {
	clusterNames := make(map[string]int, 0)
	for k := range m {
		if _, ok := clusterNames[k.ClusterName]; !ok {
			clusterNames[k.ClusterName] = 0
		}
	}
	names := make([]string, 0, len(m))
	for k := range clusterNames {
		names = append(names, k)
	}
	return names
}

func FilterByClusterName(m metric.Metrics, clusterName string) metric.Metrics {
	filtered := make(metric.Metrics)
	for k, v := range m {
		if k.ClusterName == clusterName {
			filtered[k] = v
		}
	}
	return filtered
}

func CPULimits(m metric.Metrics) []node.CPU {
	result := make([]node.CPU, 0, len(m))
	for _, v := range m {
		result = append(result, node.CPU(v.CPULimit))
	}
	return result
}

func MemoryRequests(m metric.Metrics) []node.Memory {
	result := make([]node.Memory, 0, len(m))
	for _, v := range m {
		result = append(result, node.Memory(v.MemoryRequest))
	}
	return result
}

func MemoryLimits(m metric.Metrics) []node.Memory {
	result := make([]node.Memory, 0, len(m))
	for _, v := range m {
		result = append(result, node.Memory(v.MemoryLimit))
	}
	return result
}

func (mr *MetricCloudMonitoringRepository) FetchMetrics(projectID string) (metric.Metrics, error) {
	ctx := context.Background()
	c, err := monitoring.NewQueryClient(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to create query client: %w", err)
	}
	defer c.Close()

	metrics := make(metric.Metrics)

	if err := currentWorkload(ctx, metrics, c, projectID); err != nil {
		return nil, err
	}
	if err := cpuRequest(ctx, metrics, c, projectID); err != nil {
		return nil, err
	}
	if err := cpuLimit(ctx, metrics, c, projectID); err != nil {
		return nil, err
	}
	if err := memoryRequest(ctx, metrics, c, projectID); err != nil {
		return nil, err
	}
	if err := memoryLimit(ctx, metrics, c, projectID); err != nil {
		return nil, err
	}

	return metrics, nil
}

func currentWorkload(ctx context.Context, m metric.Metrics, c *monitoring.QueryClient, projectID string) error {
	fmt.Fprint(os.Stderr, "Querying CurrentWorkload... \t")
	req := &monitoringpb.QueryTimeSeriesRequest{
		Name:  fmt.Sprintf("projects/%s", projectID),
		Query: QueryCurrentWorkload,
	}

	results, err := queryFloatValue(ctx, c, req)
	if err != nil {
		return err
	}
	for _, result := range results {
		if _, ok := m[result.Metadata]; !ok {
			m[result.Metadata] = &metric.ServiceMetric{}
		}
	}
	fmt.Fprintln(os.Stderr, "Done")
	return nil
}

func cpuRequest(ctx context.Context, m metric.Metrics, c *monitoring.QueryClient, projectID string) error {
	fmt.Fprint(os.Stderr, "Querying CPURequst... \t")
	req := &monitoringpb.QueryTimeSeriesRequest{
		Name:  fmt.Sprintf("projects/%s", projectID),
		Query: QueryCPURequest,
	}

	results, err := queryFloatValue(ctx, c, req)
	if err != nil {
		return err
	}
	for _, result := range results {
		if _, ok := m[result.Metadata]; ok {
			m[result.Metadata].CPURequest = RoundOffCPU(result.Value)
		}
	}
	fmt.Fprintln(os.Stderr, "Done")
	return nil
}

func cpuLimit(ctx context.Context, m metric.Metrics, c *monitoring.QueryClient, projectID string) error {
	fmt.Fprint(os.Stderr, "Querying CPULimit... \t")
	req := &monitoringpb.QueryTimeSeriesRequest{
		Name:  fmt.Sprintf("projects/%s", projectID),
		Query: QueryCPULimit,
	}

	results, err := queryFloatValue(ctx, c, req)
	if err != nil {
		return err
	}
	for _, result := range results {
		if _, ok := m[result.Metadata]; ok {
			m[result.Metadata].CPULimit = RoundOffCPU(result.Value)
		}
	}
	fmt.Fprintln(os.Stderr, "Done")
	return nil
}

func memoryRequest(ctx context.Context, m metric.Metrics, c *monitoring.QueryClient, projectID string) error {
	fmt.Fprint(os.Stderr, "Querying MemoryRequest... \t")
	req := &monitoringpb.QueryTimeSeriesRequest{
		Name:  fmt.Sprintf("projects/%s", projectID),
		Query: QueryMemoryRequest,
	}

	results, err := queryFloatValue(ctx, c, req)
	if err != nil {
		return err
	}
	for _, result := range results {
		if _, ok := m[result.Metadata]; ok {
			m[result.Metadata].MemoryRequest = int64(result.Value)
		}
	}
	fmt.Fprintln(os.Stderr, "Done")
	return nil
}

func memoryLimit(ctx context.Context, m metric.Metrics, c *monitoring.QueryClient, projectID string) error {
	fmt.Fprint(os.Stderr, "Querying MemoryLimit... \t")
	req := &monitoringpb.QueryTimeSeriesRequest{
		Name:  fmt.Sprintf("projects/%s", projectID),
		Query: QueryMemoryLimit,
	}

	results, err := queryFloatValue(ctx, c, req)
	if err != nil {
		return err
	}
	for _, result := range results {
		if _, ok := m[result.Metadata]; ok {
			m[result.Metadata].MemoryLimit = int64(result.Value)
		}
	}
	fmt.Fprintln(os.Stderr, "Done")
	return nil
}

func queryFloatValue(ctx context.Context, c *monitoring.QueryClient, req *monitoringpb.QueryTimeSeriesRequest) ([]metric.Float, error) {
	metrics := make([]metric.Float, 0)

	it := c.QueryTimeSeries(ctx, req)
	for {
		resp, err := it.Next()
		if err == iterator.Done {
			break
		}
		if err != nil {
			fmt.Println(err)
			return nil, err
		}
		metricMetadata := buildMetadataMetricFromLabels(resp.GetLabelValues())
		value := resp.PointData[0].GetValues()[0].GetDoubleValue()
		metrics = append(metrics, metric.Float{Metadata: metricMetadata, Value: value})
	}
	return metrics, nil
}

// func queryIntValue(ctx context.Context, c *monitoring.QueryClient, req *monitoringpb.QueryTimeSeriesRequest) []MetricInt {
// 	metrics := make([]MetricInt, 0)

// 	it := c.QueryTimeSeries(ctx, req)
// 	for {
// 		resp, err := it.Next()
// 		if err == iterator.Done {
// 			break
// 		}
// 		if err != nil {
// 			log.Fatal(err)
// 		}
// 		fmt.Println(resp.GetLabelValues())
// 		fmt.Println(resp.GetPointData())
// 		metricMetadata := buildMetadataMetricFromLabels(resp.GetLabelValues())
// 		value := resp.PointData[0].GetValues()[0].GetInt64Value()
// 		metrics = append(metrics, MetricInt{Metadata: metricMetadata, Value: value})
// 	}
// 	return metrics
// }

func buildMetadataMetricFromLabels(labels []*monitoringpb.LabelValue) metric.Metadata {
	return metric.Metadata{
		ClusterName:    labels[0].GetStringValue(),
		NamespaceName:  labels[1].GetStringValue(),
		ControllerName: labels[2].GetStringValue(),
		PodName:        labels[3].GetStringValue(),
	}
}

func RoundOffCPU(cpu float64) float64 {
	return math.Round(cpu*1000) / 1000
}
