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

package handler

import (
	"context"
	"io"
	"net/http"

	"github.com/GoogleCloudPlatform/cloud-solutions/projects/sa-tools/gke_optimization/binpacker/api/pkg/domain/model/node"
	"github.com/GoogleCloudPlatform/cloud-solutions/projects/sa-tools/gke_optimization/binpacker/api/pkg/usecase"
	pb "github.com/GoogleCloudPlatform/cloud-solutions/projects/sa-tools/gke_optimization/binpacker/api/proto"

	"google.golang.org/protobuf/encoding/protojson"

	"github.com/golang/glog"
	"github.com/julienschmidt/httprouter"
)

type requestMetrics struct {
	CPURequests    []float64
	CPULimits      []float64
	MemoryRequests []int64
	MemoryLimits   []int64
	MinNumNode     int
}

type BinpackingHandler interface {
	Calculate(w http.ResponseWriter, r *http.Request, pr httprouter.Params)
}

type binpackingHandler struct {
	binpackingUsecase usecase.BinpackingUsecase
}

func NewBinpackingHandler(bu usecase.BinpackingUsecase) BinpackingHandler {
	return &binpackingHandler{
		binpackingUsecase: bu,
	}
}

func calculateErrorResponse(w http.ResponseWriter, m protojson.MarshalOptions, message string, details string, err error) {
	errResponse, marshalErr := m.Marshal(&pb.BinpackingCalculateErrorResponse{
		Message: message,
		Details: details,
	})
	if marshalErr != nil {
		glog.Errorf("Failed to marshal error response: %s", err.Error())
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusBadRequest)
	_, writeErr := w.Write(errResponse)
	if writeErr != nil {
		glog.Errorf("Failed to write error response: %s", errResponse)
	}
}

func (bh binpackingHandler) Calculate(w http.ResponseWriter, r *http.Request, _ httprouter.Params) {
	m := protojson.MarshalOptions{
		EmitUnpopulated: true,
	}
	body, err := io.ReadAll(r.Body)
	if err != nil {
		calculateErrorResponse(w, m, "failed to read request json", err.Error(), err)
		return
	}

	var request pb.BinpackingCalculateRequest
	err = protojson.Unmarshal(body, &request)
	if err != nil {
		calculateErrorResponse(w, m, "invalid data provided", err.Error(), err)
		return
	}

	if len(request.Workloads) == 0 {
		calculateErrorResponse(w, m, "invalid data provided", "no workload provided", err)
		return
	}
	if request.MinNumNodes == 0 {
		request.MinNumNodes = 1
	}

	metrics := extractMetrics(&request)

	ctx := context.Background()
	solution, err := bh.binpackingUsecase.Calculate(
		ctx,
		metrics.CPURequests,
		metrics.CPULimits,
		metrics.MemoryRequests,
		metrics.MemoryLimits,
		metrics.MinNumNode,
	)
	if err != nil {
		calculateErrorResponse(w, m, "failed to find solution", err.Error(), err)
		return
	}

	response, err := m.Marshal(&pb.BinpackingCalculateResponse{
		Recommendation: &pb.BinpackingRecommendation{
			Cpu:      float64(solution.Recommendation.CPU),
			Memory:   float64(solution.Recommendation.MemoryInGiB),
			NumNodes: int32(solution.Recommendation.NumNodes),
		},
		RequestDetail: &pb.BinpackingRequestDetail{
			TotalCpuRequest:    float64(solution.Rationale.CPU.TotalCPURequest),
			MaxCpuLimit:        float64(solution.Rationale.CPU.MaxCPULimit),
			TotalMemoryRequest: int64(solution.Rationale.Memory.TotalMemoryRequest),
			MaxMemoryLimit:     int64(solution.Rationale.Memory.MaxMemoryLimit),
		},
		RecommendationBreakdown: &pb.RecommendationBreakdown{
			Cpu: &pb.CpuBreakdown{
				NodeSize:              float64(solution.Recommendation.CPU),
				Reserved:              float64(solution.Rationale.CPU.Reserved),
				SystemUsage:           float64(solution.Rationale.CPU.SystemResourcesUsage),
				CapacityUserWorkloads: float64(solution.Rationale.CPU.CapacityUserWorkloads),
			},
			Memory: &pb.MemoryBreakdown{
				NodeSize:              int64(node.GiBToBytes(solution.Recommendation.MemoryInGiB)),
				KernelUsage:           int64(solution.Rationale.Memory.KernelUsage),
				Reserved:              int64(solution.Rationale.Memory.Reserved),
				EvictionThreshold:     int64(solution.Rationale.Memory.EvictionThreshold),
				SystemUsage:           int64(solution.Rationale.Memory.SystemResourcesUsage),
				CapacityUserWorkloads: int64(solution.Rationale.Memory.CapacityUserWorkloads),
			},
		},
	})

	if err != nil {
		calculateErrorResponse(w, m, "failed to encode json", err.Error(), err)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	_, writeErr := w.Write(response)
	if writeErr != nil {
		glog.Errorf("Failed to write response: %s", response)
	}
}

func extractMetrics(r *pb.BinpackingCalculateRequest) *requestMetrics {
	cpuRequests := make([]float64, 0, len(r.Workloads))
	cpuLimits := make([]float64, 0, len(r.Workloads))
	memoryRequests := make([]int64, 0, len(r.Workloads))
	memoryLimits := make([]int64, 0, len(r.Workloads))
	for _, workload := range r.Workloads {
		cpuRequests = append(cpuRequests, workload.CpuRequest)
		cpuLimits = append(cpuLimits, workload.CpuLimit)
		memoryRequests = append(memoryRequests, workload.MemoryRequest)
		memoryLimits = append(memoryLimits, workload.MemoryLimit)
	}
	minNumNode := r.MinNumNodes
	return &requestMetrics{
		CPURequests:    cpuRequests,
		CPULimits:      cpuLimits,
		MemoryRequests: memoryRequests,
		MemoryLimits:   memoryLimits,
		MinNumNode:     int(minNumNode),
	}
}
