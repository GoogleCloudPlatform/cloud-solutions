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
	"strings"

	"github.com/GoogleCloudPlatform/cloud-solutions/projects/sa-tools/gke_optimization/binpacker/api/pkg/domain/model/metric"
	"github.com/GoogleCloudPlatform/cloud-solutions/projects/sa-tools/gke_optimization/binpacker/api/pkg/usecase"
	pb "github.com/GoogleCloudPlatform/cloud-solutions/projects/sa-tools/gke_optimization/binpacker/api/proto"

	"github.com/golang/glog"
	"github.com/julienschmidt/httprouter"
	"google.golang.org/protobuf/encoding/protojson"
)

type MetricHandler interface {
	FetchAll(w http.ResponseWriter, r *http.Request, _ httprouter.Params)
}

type metricHandler struct {
	metricUsecase usecase.MetricUsecase
}

func NewMetricHandler(mu usecase.MetricUsecase) MetricHandler {
	return &metricHandler{
		metricUsecase: mu,
	}
}

func fetchAllErrorResponse(w http.ResponseWriter, m protojson.MarshalOptions, message string, details string, err error, status uint) {
	errResponse, marshalErr := m.Marshal(&pb.BinpackingCalculateErrorResponse{
		Message: message,
		Details: details,
	})
	if marshalErr != nil {
		glog.Errorf("Failed to marshal error response: %s", err.Error())
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(int(status))
	_, writeErr := w.Write(errResponse)
	if writeErr != nil {
		glog.Errorf("Failed to write error response: %s", errResponse)
	}
}

func (mh metricHandler) FetchAll(w http.ResponseWriter, r *http.Request, _ httprouter.Params) {
	m := protojson.MarshalOptions{
		EmitUnpopulated: true,
	}

	body, err := io.ReadAll(r.Body)
	if err != nil {
		fetchAllErrorResponse(w, m, "failed to read request json", err.Error(), err, http.StatusBadRequest)
		return
	}

	var request pb.MetricFetchAllRequest
	err = protojson.Unmarshal(body, &request)
	if err != nil {
		fetchAllErrorResponse(w, m, "invalid data provided", err.Error(), err, http.StatusBadRequest)
		return
	}

	if len(request.GetProjectId()) == 0 {
		fetchAllErrorResponse(w, m, "invalid data provided", "no project ID provided", err, http.StatusBadRequest)
		return
	}

	ctx := context.Background()

	metrics, err := mh.metricUsecase.FetchAll(ctx, request.ProjectId)
	if err != nil {
		fetchAllErrorResponse(w, m, "failed to fetch metrics", err.Error(), err, http.StatusInternalServerError)
		return
	}

	response, err := m.Marshal(&pb.MetricFetchAllResponse{
		Pods:      transformToProtoPods(metrics.Pods),
		Nodepools: transformToProtoNodepools(metrics.NodePools),
		Clusters:  transformToProtoClusters(metrics.Clusters),
	})
	if err != nil {
		fetchAllErrorResponse(w, m, "failed to encode json", err.Error(), err, http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_, err = w.Write(response)
	if err != nil {
		glog.Errorf("Failed to write response: %s", err.Error())
	}
}

func transformToProtoPods(pods []metric.Pod) []*pb.Pod {
	protoPods := make([]*pb.Pod, 0, len(pods))
	for _, pod := range pods {
		protoPods = append(protoPods, &pb.Pod{
			Name:            pod.Name,
			Cluster:         pod.Cluster,
			ClusterLocation: pod.ClusterLocation,
			Namespace:       pod.Namespace,
			Nodepool:        pod.NodePool,
			Status:          pod.Status,
			Parent:          pod.Parent,
			ParentType:      pb.ParentType(pb.ParentType_value[strings.ToUpper(pod.ParentType)]),
			CpuRequest:      pod.CPURequest,
			CpuLimit:        pod.CPULimit,
			MemoryRequest:   pod.MemoryRequest,
			MemoryLimit:     pod.MemoryLimit,
		})
	}
	return protoPods
}

func transformToProtoNodepools(nodepools []metric.NodePool) []*pb.Nodepool {
	protoNodepools := make([]*pb.Nodepool, 0, len(nodepools))
	for _, nodepool := range nodepools {
		protoNodepools = append(protoNodepools, &pb.Nodepool{
			Name:             nodepool.Name,
			Cluster:          nodepool.Cluster,
			ClusterLocation:  nodepool.ClusterLocation,
			MachineType:      nodepool.MachineType,
			NumberOfNodes:    int32(nodepool.NumNodes),
			Cpu:              int32(nodepool.CPU),
			MemoryInGib:      nodepool.MemoryInGiB,
			TotalCpu:         int32(nodepool.TotalCPU),
			TotalMemoryInGib: nodepool.TotalMemoryInGiB,
		})
	}
	return protoNodepools
}

func transformToProtoClusters(clusters []metric.Cluster) []*pb.Cluster {
	protoClusters := make([]*pb.Cluster, 0, len(clusters))
	for _, cluster := range clusters {
		protoClusters = append(protoClusters, &pb.Cluster{
			Name:             cluster.Name,
			Location:         cluster.Location,
			NumberOfNodes:    int32(cluster.NumNodes),
			TotalCpu:         int32(cluster.TotalCPU),
			TotalMemoryInGib: cluster.TotalMemoryInGiB,
		})
	}
	return protoClusters
}
