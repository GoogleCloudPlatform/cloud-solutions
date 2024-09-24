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
	"strconv"
	"strings"

	compute "cloud.google.com/go/compute/apiv1"
	computepb "cloud.google.com/go/compute/apiv1/computepb"
	"google.golang.org/api/iterator"
)

const CustomKeyword = "custom"

type Spec struct {
	CPU         int
	MemoryInGiB float64
}

type MachineTypes struct {
	Types map[string]Spec
}

func getSpecFromCustomMachineType(customMachineType string) (*Spec, error) {
	parts := strings.Split(customMachineType, "-")

	// Custom machine type will be following form
	// e.g. e2-custom-6-3072, n2d-custom-4-5120
	if len(parts) != 4 {
		return nil, fmt.Errorf("failed to get spec from custom machine type: %s", customMachineType)
	}

	cpu, err := strconv.Atoi(parts[2])
	if err != nil {
		return nil, fmt.Errorf("failed to convert cpu in custom machine type: %s", customMachineType)
	}
	memoryInMiB, err := strconv.Atoi(parts[3])
	if err != nil {
		return nil, fmt.Errorf("failed to convert memory in custom machine type: %s", customMachineType)
	}

	return &Spec{
		CPU:         cpu,
		MemoryInGiB: float64(memoryInMiB) / 1024,
	}, nil
}

func (m *MachineTypes) getCPU(machineType string) int {
	if strings.Contains(machineType, CustomKeyword) {
		spec, err := getSpecFromCustomMachineType(machineType)
		if err != nil {
			return 0
		}
		return spec.CPU
	}
	return m.Types[machineType].CPU
}

func (m *MachineTypes) getMemoryInGiB(machineType string) float64 {
	if strings.Contains(machineType, CustomKeyword) {
		spec, err := getSpecFromCustomMachineType(machineType)
		if err != nil {
			return 0.0
		}
		return spec.MemoryInGiB
	}
	return m.Types[machineType].MemoryInGiB
}

func CreateMachineTypes(ctx context.Context, projectID string) (*MachineTypes, error) {
	client, err := compute.NewMachineTypesRESTClient(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to create machine type client: %s", err)
	}
	req := &computepb.ListMachineTypesRequest{
		Project: projectID,
		Zone:    "us-central1-c", // The zone where all machine types are available
	}

	machineTypes := &MachineTypes{}
	machineTypes.Types = make(map[string]Spec)

	it := client.List(ctx, req)
	for {
		resp, err := it.Next()
		if err == iterator.Done {
			break
		}
		if err != nil {
			return nil, fmt.Errorf("failed to list machine type: %v", err)
		}
		machineTypes.Types[resp.GetName()] = Spec{
			CPU:         int(resp.GetGuestCpus()),
			MemoryInGiB: float64(resp.GetMemoryMb() / 1024),
		}
	}
	return machineTypes, nil
}
