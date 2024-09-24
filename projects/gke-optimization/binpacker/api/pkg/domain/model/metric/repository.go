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

package metric

import "context"

type Repository interface {
	FetchMetrics(ctx context.Context, projectID string) (*Metric, error)
}

type Metric struct {
	Pods      []Pod
	NodePools []NodePool
	Clusters  []Cluster
}

type Metadata struct {
	ClusterName    string
	NamespaceName  string
	ControllerName string
	PodName        string
	NodePool       string
}

type Pod struct {
	Name            string
	Cluster         string
	ClusterLocation string
	Namespace       string
	NodePool        string
	Status          string
	Parent          string
	ParentType      string
	CPURequest      float64
	CPULimit        float64
	MemoryRequest   int64
	MemoryLimit     int64
}

type Cluster struct {
	Name             string
	Location         string
	NumNodes         int
	TotalCPU         int
	TotalMemoryInGiB float64
}

type NodePool struct {
	Name             string
	Cluster          string
	ClusterLocation  string
	MachineType      string
	NumNodes         int
	CPU              int
	MemoryInGiB      float64
	TotalCPU         int
	TotalMemoryInGiB float64
}

type ServiceMetric struct {
	CPURequest    float64
	CPULimit      float64
	MemoryRequest int64
	MemoryLimit   int64
}

type Float struct {
	Metadata Metadata
	Value    float64
}

type Int struct {
	Metadata Metadata
	Value    int64
}

type Metrics map[Metadata]*ServiceMetric

type TotalRequestsAndLimits struct {
	TotalCPURequest    float64
	TotalCPULimit      float64
	TotalMemoryRequest int64
	TotalMemoryLimit   int64
}

type InstanceGroupMetadata struct {
	ProjectID     string
	Zone          string
	InstanceGroup string
}
