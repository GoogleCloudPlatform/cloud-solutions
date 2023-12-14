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

	"github.com/GoogleCloudPlatform/cloud-solutions/projects/sa-tools/gke_optimization/binpacker/api/pkg/domain/model/metric"

	"github.com/golang/glog"
	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
)

const REPLICASET string = "ReplicaSet"

type Cluster struct {
	ProjectID   string
	Name        string
	Location    string
	NodePools   []metric.NodePool
	Pods        *corev1.PodList
	ReplicaSets *appsv1.ReplicaSetList
}

func (c *Cluster) GetWorkloads(ctx context.Context, authConfigs *K8sAuthConfigs) ([]metric.Pod, error) {
	glog.Infof("Start fetching data from %s", c.getNameWithLocation())

	config, err := authConfigs.GetK8sConfig(c.getClusterNameForAuthConfig())
	if err != nil {
		return nil, fmt.Errorf("failed to get k8s config for %s: %v", c.getNameWithLocation(), err)
	}

	clientset, err := kubernetes.NewForConfig(config)
	if err != nil {
		return nil, fmt.Errorf("failed to create clientset for %s: %v", c.getNameWithLocation(), err)
	}

	c.Pods, err = clientset.CoreV1().Pods("").List(ctx, metav1.ListOptions{})
	if err != nil {
		return nil, fmt.Errorf("failed to fetch pods from %s: %v", c.getNameWithLocation(), err)
	}
	glog.Infof("Fetched %d pods from %s", len(c.Pods.Items), c.getNameWithLocation())

	c.ReplicaSets, err = clientset.AppsV1().ReplicaSets("").List(ctx, metav1.ListOptions{})
	if err != nil {
		return nil, fmt.Errorf("failed to fetch replicasets: %v", err)
	}
	glog.Infof("Fetched %d replicasets from %s", len(c.ReplicaSets.Items), c.getNameWithLocation())

	pods := make([]metric.Pod, 0, len(c.Pods.Items))
	for _, pod := range c.Pods.Items {
		if isSystemPod(pod) {
			continue
		}
		parent, parentType := c.getParentFromPod(pod)
		totalRequestAndLimit := getTotalRequestsAndLimitsForPod(pod)
		pods = append(pods, metric.Pod{
			Name:            pod.Name,
			Cluster:         c.Name,
			ClusterLocation: c.Location,
			Namespace:       pod.Namespace,
			NodePool:        c.getNodePoolName(pod.Spec.NodeName),
			Status:          string(pod.Status.Phase),
			Parent:          parent,
			ParentType:      parentType,
			CPURequest:      totalRequestAndLimit.TotalCPURequest,
			CPULimit:        totalRequestAndLimit.TotalCPULimit,
			MemoryRequest:   totalRequestAndLimit.TotalMemoryRequest,
			MemoryLimit:     totalRequestAndLimit.TotalMemoryLimit,
		})
	}

	return pods, nil
}

func (c *Cluster) getParentFromPod(pod corev1.Pod) (string, string) {
	if len(pod.OwnerReferences) != 1 {
		return "", ""
	}
	owner := pod.OwnerReferences[0]
	switch owner.Kind {
	case REPLICASET:
		return c.getParentFromReplicaSet(owner.Name, pod.Namespace)
	case "DaemonSet", "StatefulSet", "Node", "Job", "CronJob":
		return owner.Name, owner.Kind
	default:
		glog.Errorf("Unknown kind: %s, Name: %s", owner.Kind, owner.Name)
		return "", ""
	}
}

func (c *Cluster) getNodePoolName(nodeName string) string {
	if len(nodeName) < 1 {
		return ""
	}
	for _, nodePool := range c.NodePools {
		nodePoolSubString := fmt.Sprintf("gke-%s-%s-", c.Name, nodePool.Name)
		if !strings.Contains(nodeName, nodePoolSubString) {
			continue
		}
		if len(strings.Split(strings.ReplaceAll(nodeName, nodePoolSubString, ""), "-")) == 2 {
			return nodePool.Name
		}
	}
	glog.Errorf("Failed to find nodepool for node: %s", nodeName)
	return ""
}

func (c *Cluster) getTotalNumNodes() int {
	totalNumNodes := 0
	for _, nodepool := range c.NodePools {
		totalNumNodes += nodepool.NumNodes
	}
	return totalNumNodes
}

func (c *Cluster) getTotalVCPUs() int {
	totalVCPUs := 0
	for _, nodePool := range c.NodePools {
		totalVCPUs += nodePool.CPU * nodePool.NumNodes
	}
	return totalVCPUs
}

func (c *Cluster) getTotalMemoryInGiB() float64 {
	totalMemoryInGiB := 0.0
	for _, nodePool := range c.NodePools {
		totalMemoryInGiB += nodePool.MemoryInGiB * float64(nodePool.NumNodes)
	}
	return totalMemoryInGiB
}

func (c *Cluster) getParentFromReplicaSet(replicaSetName string, namespace string) (string, string) {
	for _, replicaSet := range c.ReplicaSets.Items {
		if replicaSet.Name != replicaSetName || replicaSet.Namespace != namespace {
			continue
		}
		if len(replicaSet.OwnerReferences) != 1 {
			return replicaSet.Name, REPLICASET
		}
		owner := replicaSet.OwnerReferences[0]
		switch owner.Kind {
		case "Deployment":
			return owner.Name, owner.Kind
		default:
			glog.Errorf("Unknown kind: %s", owner.Kind)
			return "", REPLICASET
		}
	}
	return "", REPLICASET
}

func (c *Cluster) getNameWithLocation() string {
	return fmt.Sprintf("%s(%s)", c.Name, c.Location)
}

func (c *Cluster) getClusterNameForAuthConfig() string {
	return fmt.Sprintf("gke_%s_%s_%s", c.ProjectID, c.Location, c.Name)
}
