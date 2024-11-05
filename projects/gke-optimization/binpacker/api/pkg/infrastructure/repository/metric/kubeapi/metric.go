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

package kubeapi

import (
	"context"
	"fmt"
	"strings"

	compute "cloud.google.com/go/compute/apiv1"
	computepb "cloud.google.com/go/compute/apiv1/computepb"
	container "cloud.google.com/go/container/apiv1"

	"github.com/GoogleCloudPlatform/cloud-solutions/projects/sa-tools/gke_optimization/binpacker/api/pkg/domain/model/metric"

	"cloud.google.com/go/container/apiv1/containerpb"
	"github.com/golang/glog"
	corev1 "k8s.io/api/core/v1"
)

type MetricKubeapiRepository struct{}

func NewMetricKubeapiRepository() *MetricKubeapiRepository {
	return &MetricKubeapiRepository{}
}

// FetchMetrics fetches clusters, nodepools and pods via google cloud api and kubernetes endpoint
func (mr *MetricKubeapiRepository) FetchMetrics(ctx context.Context, projectID string) (*metric.Metric, error) {
	machineTypes, err := CreateMachineTypes(ctx, projectID)
	if err != nil {
		return nil, err
	}

	c, err := container.NewClusterManagerClient(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to get client for google kubernetes engine: %v", err)
	}
	defer c.Close()

	req := &containerpb.ListClustersRequest{
		Parent: fmt.Sprintf("projects/%s/locations/-", projectID),
	}
	resp, err := c.ListClusters(ctx, req)
	if err != nil {
		return nil, fmt.Errorf("failed to list clusters: %s", err)
	}

	standardClusters, err := extractStandardClusters(ctx, resp.GetClusters(), machineTypes, projectID)
	if err != nil {
		return nil, err
	}
	glog.Infof("Found %d GKE standard clusters", len(standardClusters))

	authConfigs, err := GenerateK8sClustersConfig(resp.Clusters, projectID)
	if err != nil {
		return nil, err
	}

	allClusters := make([]metric.Cluster, 0)
	allPods := make([]metric.Pod, 0)
	allNodePools := make([]metric.NodePool, 0)
	for _, cluster := range standardClusters {
		pods, err := cluster.GetWorkloads(ctx, authConfigs)
		if err != nil {
			return nil, err
		}
		allPods = append(allPods, pods...)
		allNodePools = append(allNodePools, cluster.NodePools...)
		allClusters = append(allClusters, metric.Cluster{
			Name:             cluster.Name,
			Location:         cluster.Location,
			NumNodes:         cluster.getTotalNumNodes(),
			TotalCPU:         cluster.getTotalVCPUs(),
			TotalMemoryInGiB: cluster.getTotalMemoryInGiB(),
		})
	}

	return &metric.Metric{
		Pods:      allPods,
		NodePools: allNodePools,
		Clusters:  allClusters,
	}, nil
}

// isSystemPod checks whether a pod is system pod or not
func isSystemPod(pod corev1.Pod) bool {
	return pod.Namespace == "kube-system"
}

// getTotalRequestsAndLimitsForPod calculates total resource request and limit for cpu and memory
func getTotalRequestsAndLimitsForPod(pod corev1.Pod) *metric.TotalRequestsAndLimits {
	var cpuRequest, cpuLimit float64
	var memoryRequest, memoryLimit int64
	for _, container := range pod.Spec.Containers {
		cpuRequest += container.Resources.Requests.Cpu().AsApproximateFloat64()
		cpuLimit += container.Resources.Limits.Cpu().AsApproximateFloat64()
		memoryRequest += int64(container.Resources.Requests.Memory().AsApproximateFloat64())
		memoryLimit += int64(container.Resources.Limits.Memory().AsApproximateFloat64())
	}
	return &metric.TotalRequestsAndLimits{
		TotalCPURequest:    cpuRequest,
		TotalCPULimit:      cpuLimit,
		TotalMemoryRequest: memoryRequest,
		TotalMemoryLimit:   memoryLimit,
	}
}

// extractStandardClusters filters standard GKE clusters and fetches nodepools per cluster
func extractStandardClusters(ctx context.Context, pbClusters []*containerpb.Cluster, machineTypes *MachineTypes, projectID string) ([]Cluster, error) {
	standardClusters := make([]Cluster, 0)
	for _, pbCluster := range pbClusters {
		glog.Infof("Found a cluster: %s(%s)", pbCluster.GetName(), pbCluster.GetLocation())
		if isAutopilotCluster(pbCluster) {
			glog.Infof("Cluster %s(%s) is Autopilot cluster and skipping...", pbCluster.GetName(), pbCluster.GetLocation())
			continue
		}
		nodePools := make([]metric.NodePool, 0, len(pbCluster.GetNodePools()))
		for _, pbNodePool := range pbCluster.GetNodePools() {
			numNodes := 0
			for _, instanceGroupURL := range pbNodePool.GetInstanceGroupUrls() {
				num, err := getNumNodesFromInstanceGroup(ctx, instanceGroupURL)
				if err != nil {
					return nil, err
				}
				numNodes += num
			}
			nodePools = append(nodePools, metric.NodePool{
				Name:             pbNodePool.GetName(),
				Cluster:          pbCluster.GetName(),
				ClusterLocation:  pbCluster.GetLocation(),
				MachineType:      pbNodePool.GetConfig().MachineType,
				NumNodes:         numNodes,
				CPU:              machineTypes.getCPU(pbNodePool.GetConfig().MachineType),
				MemoryInGiB:      machineTypes.getMemoryInGiB(pbNodePool.GetConfig().MachineType),
				TotalCPU:         machineTypes.getCPU(pbNodePool.GetConfig().MachineType) * numNodes,
				TotalMemoryInGiB: machineTypes.getMemoryInGiB(pbNodePool.GetConfig().MachineType) * float64(numNodes),
			})
		}
		standardClusters = append(standardClusters, Cluster{
			ProjectID: projectID,
			Name:      pbCluster.GetName(),
			Location:  pbCluster.GetLocation(),
			NodePools: nodePools,
		})
	}
	return standardClusters, nil
}

// getNumNodesFromInstanceGroup fetches number of nodes in an instance group
func getNumNodesFromInstanceGroup(ctx context.Context, url string) (int, error) {
	instanceGroupMetadata := extractProjectZoneAndInstanceGroup(url)
	instanceGroupClient, err := compute.NewInstanceGroupsRESTClient(ctx)
	if err != nil {
		return 0, fmt.Errorf("failed to create instance group client: %s", err)
	}
	reqIG := &computepb.GetInstanceGroupRequest{
		InstanceGroup: instanceGroupMetadata.InstanceGroup,
		Project:       instanceGroupMetadata.ProjectID,
		Zone:          instanceGroupMetadata.Zone,
	}
	ig, err := instanceGroupClient.Get(ctx, reqIG)
	if err != nil {
		return 0, fmt.Errorf("failed to get instance group: %s", err)
	}
	return int(ig.GetSize()), nil
}

// extractProjectZoneAndInstanceGroup returns project ID, zone and instance group from url
func extractProjectZoneAndInstanceGroup(url string) *metric.InstanceGroupMetadata {
	items := strings.Split(url, "/")
	return &metric.InstanceGroupMetadata{
		ProjectID:     items[6],
		Zone:          items[8],
		InstanceGroup: items[10],
	}
}

// isAutopilotCluster returns true when a GKE cluster is Autopilot
func isAutopilotCluster(cluster *containerpb.Cluster) bool {
	if cluster.GetAutopilot() == nil {
		return false
	}
	return cluster.GetAutopilot().Enabled
}
