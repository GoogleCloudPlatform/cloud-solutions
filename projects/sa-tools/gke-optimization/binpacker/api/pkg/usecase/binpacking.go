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

package usecase

import (
	"context"
	"fmt"

	"github.com/GoogleCloudPlatform/cloud-solutions/projects/sa-tools/gke_optimization/binpacker/api/pkg/domain/model/node"
	"github.com/GoogleCloudPlatform/cloud-solutions/projects/sa-tools/gke_optimization/binpacker/api/pkg/domain/service/binpacking"
)

type BinpackingUsecase interface {
	Calculate(ctx context.Context, cpuRequests, cpuLimits []float64, memoryRequests, memoryLimits []int64, numNodes int) (*binpacking.Solution, error)
}

type binpackingUsecase struct{}

func NewBinpackingUsecase() BinpackingUsecase {
	return &binpackingUsecase{}
}

func (b binpackingUsecase) Calculate(_ context.Context, cpuRequests, cpuLimits []float64, memoryRequests, memoryLimits []int64, minNumNodes int) (*binpacking.Solution, error) {
	workloadsMetrics, err := convertToWorkloadsMetrics(cpuRequests, cpuLimits, memoryRequests, memoryLimits)
	if err != nil {
		return nil, err
	}
	recommendation, err := binpacking.FindRecommendation(workloadsMetrics, minNumNodes)
	if err != nil {
		return nil, err
	}
	rationale, err := binpacking.GetRationale(workloadsMetrics, *recommendation)
	if err != nil {
		return nil, err
	}
	return &binpacking.Solution{
		Recommendation: recommendation,
		Rationale:      rationale,
	}, nil
}

func convertToWorkloadsMetrics(cpuRequests, cpuLimits []float64, memoryRequests, memoryLimits []int64) ([]binpacking.WorkloadMetrics, error) {
	if len(cpuRequests) != len(cpuLimits) || len(memoryRequests) != len(memoryLimits) || len(cpuRequests) != len(memoryRequests) {
		return nil, fmt.Errorf("count of workload metrics didn't match: cpuRequests: %d, cpuLimits: %d, memoryRequests: %d, memoryLimits: %d", len(cpuRequests), len(cpuLimits), len(memoryRequests), len(memoryLimits))
	}
	workloadsMetrics := make([]binpacking.WorkloadMetrics, 0, len(cpuRequests))
	for i := 0; i < len(cpuRequests); i++ {
		workloadsMetrics = append(workloadsMetrics, binpacking.WorkloadMetrics{
			CPURequest:    node.CPU(cpuRequests[i]),
			CPULimit:      node.CPU(cpuLimits[i]),
			MemoryRequest: node.Memory(memoryRequests[i]),
			MemoryLimit:   node.Memory(memoryLimits[i]),
		})
	}
	return workloadsMetrics, nil
}

// func convertToCPUs(values []float64) []node.CPU {
// 	cpus := make([]node.CPU, 0, len(values))
// 	for _, value := range values {
// 		cpus = append(cpus, node.CPU(value))
// 	}
// 	return cpus
// }

// func convertToMemories(values []int64) []node.Memory {
// 	memories := make([]node.Memory, 0, len(values))
// 	for _, value := range values {
// 		memories = append(memories, node.Memory(value))
// 	}
// 	return memories
// }
