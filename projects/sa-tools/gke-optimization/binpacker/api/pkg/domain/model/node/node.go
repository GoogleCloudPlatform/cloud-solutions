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

package node

import (
	"errors"
	"fmt"
	"math"

	"github.com/golang/glog"
)

var (
	ErrCPUNegative      = errors.New("negative CPU")
	ErrMemoryNegative   = errors.New("negative memory")
	ErrCPUOverLimit     = errors.New("over CPU limit")
	ErrMemoryOverLimit  = errors.New("over memory limit")
	ErrMemoryOutOfRange = errors.New("memory out of range")
)

type CPU float64
type Memory int64
type MemoryInGiB float64
type MemoryInMiB float64

type Node struct {
	cpuOnGCE        CPU
	memoryOnGCE     Memory
	remainingCPU    CPU
	remainingMemory Memory
}

const (
	MinCPUPerNode                = 2.0   // N2 custom
	MaxCPUPerNode                = 80.0  // N2 custom
	MinMemoryInGiBPerNode        = 1.0   // N2 custom
	MaxMemoryInGiBPerNode        = 640.0 // N2 custom
	MinMemoryPerNode             = MinMemoryInGiBPerNode * 1024 * 1024 * 1024
	MaxMemoryPerNode             = MaxMemoryInGiBPerNode * 1024 * 1024 * 1024
	CPUUnit                      = 2
	CPUUsageBySystemResources    = 1.0
	MemoryUnitInGiB              = 0.25
	MemoryUsageRatioByKernel     = 0.05
	MemoryUsageBySystemResources = 900 * 1024 * 1024
	EvictionThreshold            = 100 * 1024 * 1024
)

// ScheduleCPU assigns cpu for the node and return true if it's scheduled
func (n *Node) ScheduleCPU(cpuUsage CPU) bool {
	if n.remainingCPU >= cpuUsage {
		n.remainingCPU -= cpuUsage
		return true
	}
	return false
}

// ScheduleMemory assigns memory for the node and return true if it's scheduled
func (n *Node) ScheduleMemory(memoryUsage Memory) bool {
	if n.remainingMemory >= memoryUsage {
		n.remainingMemory -= memoryUsage
		return true
	}
	return false
}

// SchedulableCPU checks whether the specific cpu is assignable
func (n *Node) SchedulableCPU(cpuUsage CPU) bool {
	return n.remainingCPU >= cpuUsage
}

// SchedulableMemory checks whether the specific memory is assignable
func (n *Node) SchedulableMemory(memoryUsage Memory) bool {
	return n.remainingMemory >= memoryUsage
}

// RoundCPU rounds cpu with 3 decimal places as it is defined in Kubernetes world
func RoundCPU(cpu CPU) CPU {
	return CPU(math.Round(float64(cpu)*1000) / 1000)
}

// GiBToBytes transforms the memory size in GiB to byte
func GiBToBytes(memoryInGiB MemoryInGiB) Memory {
	return Memory(memoryInGiB * 1024 * 1024 * 1024)
}

// MiBToBytes transforms the memory size in MiB to byte
func MiBToBytes(memoryInMiB MemoryInMiB) Memory {
	return Memory(memoryInMiB * 1024 * 1024)
}

// ByteToGiB transforms the memory size in byte to GiB
func ByteToGiB(memory Memory) MemoryInGiB {
	return MemoryInGiB(memory) / 1024 / 1024 / 1024
}

// MinRequeredCPU finds the minimum CPU of a node to assign the cpuUsage
func MinRequiredCPU(cpuUsage CPU) CPU {
	var start int
	if cpuUsage <= 0 {
		start = MinCPUPerNode
	} else {
		start = int(math.Ceil(float64(cpuUsage)))
		if start%2 != 0 {
			start++
		}
	}
	for cpu := start; cpu <= MaxCPUPerNode; cpu += CPUUnit {
		// Error won't happen here since "cpu" is normalized
		node, err := newNode(CPU(cpu), GiBToBytes(MemoryInGiB(cpu)))
		if err != nil {
			glog.Errorf("Failed to create a new node with %d cpus and %f GiB memory", cpu, MemoryInGiB(cpu))
		}
		if node.SchedulableCPU(cpuUsage) {
			return CPU(cpu)
		}
	}
	return MaxCPUPerNode
}

// CalculateMinMaxMemoryInGiBByCPU calculates the range of the memory size
// based on the specified CPU
// ref. https://cloud.google.com/compute/docs/general-purpose-machines#custom_machine_types
func CalculateMinMaxMemoryInGiBByCPU(cpu CPU) (MemoryInGiB, MemoryInGiB) {
	minMemory := MemoryInGiB(cpu / 2)
	if minMemory < MinMemoryInGiBPerNode {
		minMemory = MinMemoryInGiBPerNode
	}
	maxMemory := MemoryInGiB(cpu * 8)
	if maxMemory > MaxMemoryInGiBPerNode {
		maxMemory = MaxMemoryInGiBPerNode
	}
	return minMemory, maxMemory
}

// validMemorySizeByCPU checks whether specified CPU and memory size are valid
func validMemorySizeByCPU(cpu CPU, memory Memory) bool {
	memoryInGiB := ByteToGiB(memory)
	minMemoryInGiB, maxMemoryInGiB := CalculateMinMaxMemoryInGiBByCPU(cpu)
	return minMemoryInGiB <= memoryInGiB && memoryInGiB <= maxMemoryInGiB
}

func newNode(cpuOnGCE CPU, memoryOnGCE Memory) (*Node, error) {
	if cpuOnGCE < MinCPUPerNode {
		return nil, fmt.Errorf("cpu must be greater than or equal to %f, got %f: %w", MinCPUPerNode, cpuOnGCE, ErrCPUNegative)
	}
	if cpuOnGCE > MaxCPUPerNode {
		return nil, fmt.Errorf("cpu must be less than or equal to %f, got %f: %w", MaxCPUPerNode, cpuOnGCE, ErrCPUOverLimit)
	}
	if memoryOnGCE < MinMemoryPerNode {
		return nil, fmt.Errorf("memory must be greater than or equal to %f, got %d: %w", MinMemoryPerNode, memoryOnGCE, ErrMemoryNegative)
	}
	if memoryOnGCE > MaxMemoryPerNode {
		return nil, fmt.Errorf("memory must be less than or equal to %f, got %d: %w", MaxMemoryPerNode, memoryOnGCE, ErrMemoryOverLimit)
	}
	if !validMemorySizeByCPU(cpuOnGCE, memoryOnGCE) {
		return nil, fmt.Errorf("memory size is out of range based on the number of cpu: %w", ErrMemoryOutOfRange)
	}

	remainingCPU := calculateRemainingCPU(cpuOnGCE)
	remainingMemory := calculateRemainingMemory(memoryOnGCE)

	return &Node{
		cpuOnGCE,
		memoryOnGCE,
		remainingCPU,
		remainingMemory,
	}, nil
}

func calculateRemainingCPU(cpuOnGCE CPU) CPU {
	return RoundCPU(cpuOnGCE -
		reservedCPU(cpuOnGCE) -
		CPUUsageBySystemResources)
}

func calculateRemainingMemory(memoryOnGCE Memory) Memory {
	return memoryOnGCE -
		calculateKernelUsageMemory(memoryOnGCE) -
		reservedMemory(memoryOnGCE) -
		EvictionThreshold -
		MemoryUsageBySystemResources
}

func calculateKernelUsageMemory(memoryOnGCE Memory) Memory {
	return Memory(float64(memoryOnGCE) * MemoryUsageRatioByKernel)
}

// reservedCPU calculates the amount of reserved CPU resources
// from the amount of CPU resources on Google Compute Engine
// ref. https://cloud.google.com/kubernetes-engine/docs/concepts/plan-node-sizes?hl=ja#cpu_reservations
func reservedCPU(cpuOnGCE CPU) CPU {
	var reserved CPU
	if cpuOnGCE < 1 {
		return RoundCPU(cpuOnGCE * 0.06)
	}
	reserved += 1 * 0.06
	if cpuOnGCE < 2 {
		reserved += (cpuOnGCE - 1) * 0.01
		return RoundCPU(reserved)
	}
	reserved += 1 * 0.01
	if cpuOnGCE < 4 {
		reserved += (cpuOnGCE - 2) * 0.005
		return RoundCPU(reserved)
	}
	reserved += 2 * 0.005
	reserved += (cpuOnGCE - 4) * 0.0025
	return RoundCPU(reserved)
}

// reservedMemory calculates the amount of reserved memory resources
// from the amount of memory resources on Google Compute Engine
// ref. https://cloud.google.com/kubernetes-engine/docs/concepts/plan-node-sizes?hl=ja#memory_reservations
func reservedMemory(memoryOnGCE Memory) Memory {
	var reserved Memory
	if memoryOnGCE < GiBToBytes(1) {
		return MiBToBytes(255)
	}
	if memoryOnGCE < GiBToBytes(4) {
		return Memory(float64(memoryOnGCE) * 0.25)
	}
	reserved += GiBToBytes(1) // 4GiB * 25%
	if memoryOnGCE < GiBToBytes(8) {
		reserved += Memory(float64(memoryOnGCE-GiBToBytes(4)) * 0.2)
		return reserved
	}
	reserved += GiBToBytes(4 * 0.2)
	if memoryOnGCE < GiBToBytes(16) {
		reserved += Memory(float64(memoryOnGCE-GiBToBytes(8)) * 0.1)
		return reserved
	}
	reserved += GiBToBytes(8 * 0.1)
	if memoryOnGCE < GiBToBytes(128) {
		reserved += Memory(float64(memoryOnGCE-GiBToBytes(16)) * 0.06)
		return reserved
	}
	reserved += GiBToBytes(112 * 0.06)
	reserved += Memory(float64(memoryOnGCE-GiBToBytes(128)) * 0.02)
	return reserved
}
