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

package binpacking

import (
	"errors"
	"fmt"
	"sort"

	"github.com/GoogleCloudPlatform/cloud-solutions/projects/sa-tools/gke_optimization/binpacker/api/pkg/domain/model/node"

	"github.com/golang/glog"
)

type Solution struct {
	Recommendation *Recommendation
	Rationale      *RecommendationRationale
}

type WorkloadMetrics struct {
	CPURequest    node.CPU
	CPULimit      node.CPU
	MemoryRequest node.Memory
	MemoryLimit   node.Memory
}

type Recommendation struct {
	CPU         node.CPU
	MemoryInGiB node.MemoryInGiB
	NumNodes    int
}

type RecommendationRationale struct {
	CPU    *CPURationale
	Memory *MemoryRationale
}

type CPURationale struct {
	MaxCPULimit           node.CPU
	TotalCPURequest       node.CPU
	NodeSize              node.CPU // vCPUs on GCE
	Reserved              node.CPU
	SystemResourcesUsage  node.CPU
	CapacityUserWorkloads node.CPU
}

type MemoryRationale struct {
	MaxMemoryLimit        node.Memory
	TotalMemoryRequest    node.Memory
	NodeSize              node.Memory // Memory on GCE
	KernelUsage           node.Memory
	Reserved              node.Memory
	EvictionThreshold     node.Memory
	SystemResourcesUsage  node.Memory
	CapacityUserWorkloads node.Memory
}

// ref. https://cloud.google.com/compute/vm-instance-pricing#e2_custommachinetypepricing
const (
	UnitPricePerCPUPerHour    = 0.028026
	UnitPricePerMemoryPerHour = 0.003739
)

func (s Recommendation) String() string {
	return fmt.Sprintf("CPU: %f, Memory: %f, Num: %d", s.CPU, s.MemoryInGiB, s.NumNodes)
}

func (r RecommendationRationale) String() string {
	return fmt.Sprintf("MaxCPULimit: %f, TotalCPURequest: %f, CPUReserved: %f, CPUSystemResourcesUsage: %f, CPUUserWorkloads: %f, MemoryMaxLimit: %d, TotalMemoryRequest: %d, MemoryKernelUsage: %d, MemoryReserved: %d, MemoryEvictionThreshold: %d, MemorySystemResourcesUsage: %d, MemoryUserWorkloads: %d", r.CPU.MaxCPULimit, r.CPU.TotalCPURequest, r.CPU.Reserved, r.CPU.SystemResourcesUsage, r.CPU.CapacityUserWorkloads, r.Memory.MaxMemoryLimit, r.Memory.TotalMemoryRequest, r.Memory.KernelUsage, r.Memory.Reserved, r.Memory.EvictionThreshold, r.Memory.SystemResourcesUsage, r.Memory.CapacityUserWorkloads)
}

// FindRecommendation calculates and finds the most efficient spec
// and number of nodes are required to schedule all workloads
func FindRecommendation(workloadsMetrics []WorkloadMetrics, minNodes int) (*Recommendation, error) {
	// logInputs(cpuRequests, cpuLimits, memoryRequests, memoryLimits)

	cpuRequests := make([]node.CPU, 0, len(workloadsMetrics))
	cpuLimits := make([]node.CPU, 0, len(workloadsMetrics))
	memoryRequests := make([]node.Memory, 0, len(workloadsMetrics))
	memoryLimits := make([]node.Memory, 0, len(workloadsMetrics))
	for _, workloadMetrics := range workloadsMetrics {
		cpuRequests = append(cpuRequests, workloadMetrics.CPURequest)
		cpuLimits = append(cpuLimits, workloadMetrics.CPULimit)
		memoryRequests = append(memoryRequests, workloadMetrics.MemoryRequest)
		memoryLimits = append(memoryLimits, workloadMetrics.MemoryLimit)
	}

	maxCPULimit := node.MaxCPU(cpuLimits)
	recommendations, err := findRecommendationsByCPU(maxCPULimit, cpuRequests, minNodes)
	if err != nil {
		return nil, err
	}

	glog.Infof("Found recommendations by CPU: %v", recommendations)

	maxMemoryLimit := node.MaxMemory(memoryLimits)

	// Find efficient memory size per recommendation calculated based on CPU
	for i := range recommendations {
		efficientMemory, err := findEfficientMemorySize(recommendations[i].CPU, maxMemoryLimit, memoryRequests, recommendations[i].NumNodes)
		if err != nil {
			continue
		}
		recommendations[i].MemoryInGiB = efficientMemory
	}

	glog.Infof("Calculated required memory: %v", recommendations)
	return getBestRecommendation(recommendations), nil
}

func GetRationale(workloadsMetrics []WorkloadMetrics, recommendation Recommendation) (*RecommendationRationale, error) {
	var totalCPURequest node.CPU
	var totalMemoryRequest node.Memory
	var maxCPULimit node.CPU
	var maxMemoryLimit node.Memory
	for _, workloadMetrics := range workloadsMetrics {
		totalCPURequest += workloadMetrics.CPURequest
		totalMemoryRequest += workloadMetrics.MemoryRequest
		if maxCPULimit < workloadMetrics.CPULimit {
			maxCPULimit = workloadMetrics.CPULimit
		}
		if maxMemoryLimit < workloadMetrics.MemoryLimit {
			maxMemoryLimit = workloadMetrics.MemoryLimit
		}
	}

	nodes, err := node.NewNodes(recommendation.CPU, node.GiBToBytes(recommendation.MemoryInGiB), recommendation.NumNodes)
	if err != nil {
		return nil, err
	}

	return &RecommendationRationale{
		CPU: &CPURationale{
			MaxCPULimit:           maxCPULimit,
			TotalCPURequest:       node.RoundCPU(totalCPURequest),
			NodeSize:              recommendation.CPU,
			Reserved:              nodes.ReservedCPU(),
			SystemResourcesUsage:  node.CPUUsageBySystemResources,
			CapacityUserWorkloads: nodes.CPUCapacityForUserWorkloads(),
		},
		Memory: &MemoryRationale{
			MaxMemoryLimit:        maxMemoryLimit,
			TotalMemoryRequest:    totalMemoryRequest,
			NodeSize:              node.GiBToBytes(recommendation.MemoryInGiB),
			KernelUsage:           nodes.MemoryKernelUsage(),
			Reserved:              nodes.ReservedMemory(),
			EvictionThreshold:     node.EvictionThreshold,
			SystemResourcesUsage:  node.MemoryUsageBySystemResources,
			CapacityUserWorkloads: nodes.MemoryCapacityForUserWorkloads(),
		},
	}, nil
}

// getBestRecommendation evaluates and picks the best recommendation from multiple recommendations
func getBestRecommendation(recommendations []Recommendation) *Recommendation {
	sort.SliceStable(recommendations, func(i, j int) bool {
		return (float64(recommendations[i].CPU*UnitPricePerCPUPerHour)+float64(recommendations[i].MemoryInGiB*UnitPricePerMemoryPerHour))*float64(recommendations[i].NumNodes) < (float64(recommendations[j].CPU*UnitPricePerCPUPerHour)+float64(recommendations[j].MemoryInGiB*UnitPricePerMemoryPerHour))*float64(recommendations[j].NumNodes)
	})

	return &recommendations[0]
}

// findRecommendationsByCPU finds what specs of nodes and how many nodes are required
// to schedule all cpu requests and max limit
func findRecommendationsByCPU(maxLimit node.CPU, cpuRequests []node.CPU, minNumNodes int) ([]Recommendation, error) {
	var totalCPURequest node.CPU
	for _, v := range cpuRequests {
		totalCPURequest += v
	}

	requiredCPU := totalCPURequest
	if maxLimit > totalCPURequest {
		requiredCPU = maxLimit
	}

	recommendationMap := make(map[int]node.CPU, 0)
	for cpu := node.CPU(node.MinCPUPerNode); cpu <= node.MinRequiredCPU(requiredCPU); cpu += node.CPUUnit {
		// Memory size is not used at this moment
		nodes, err := node.NewNodesByCPU(cpu, minNumNodes)
		if err != nil {
			return nil, err
		}
		if !nodes.SchedulableCPU(maxLimit) {
			continue
		}
		// FirstFitDecreasingByCPU returns error if the biggest request is not schedulable
		numNodes, err := nodes.FirstFitDecreasingByCPU(cpuRequests)
		if err != nil {
			continue
		}
		// Only put smallest one
		if _, exists := recommendationMap[numNodes]; exists {
			continue
		}
		recommendationMap[numNodes] = cpu
	}

	recommendations := make([]Recommendation, 0)
	for numNodes, cpu := range recommendationMap {
		recommendations = append(recommendations, Recommendation{CPU: cpu, MemoryInGiB: 0, NumNodes: numNodes})
	}
	return recommendations, nil
}

// findEfficentMemorySize finds the minumum memory size to schedule all memory requests
// and the max memory limit in a specific number of nodes
func findEfficientMemorySize(cpu node.CPU, maxLimit node.Memory, memoryRequests []node.Memory, numNodes int) (node.MemoryInGiB, error) {
	minMemoryInGiB, maxMemoryInGiB := node.CalculateMinMaxMemoryInGiBByCPU(cpu)
	for memoryInGiB := minMemoryInGiB; memoryInGiB <= maxMemoryInGiB; memoryInGiB += node.MemoryUnitInGiB {
		nodes, err := node.NewNodes(cpu, node.GiBToBytes(memoryInGiB), numNodes)
		if err != nil {
			return 0, err
		}
		if !nodes.SchedulableMemory(maxLimit) {
			continue
		}
		if nodes.CanScheduleAllMemoryUsages(memoryRequests) {
			return memoryInGiB, nil
		}
	}
	return 0, errors.New("failed to find efficient memory size")
}
