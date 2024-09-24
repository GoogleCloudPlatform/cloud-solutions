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
	"sort"

	"github.com/golang/glog"
)

var (
	ErrNumNodesNegative  = errors.New("negative number of nodes")
	ErrNumNodesOverLimit = errors.New("number of nodes over limit")
)

type Nodes struct {
	nodes         []Node
	cpuPerNode    CPU
	memoryPerNode Memory
}

const MaxNumNodes = 15000

// NewNodes creates and initializes Nodes
func NewNodes(cpuPerNode CPU, memoryPerNode Memory, numNodes int) (*Nodes, error) {
	if numNodes <= 0 {
		return nil, fmt.Errorf("number of nodes must be positive, got %d: %w", numNodes, ErrNumNodesNegative)
	}
	if numNodes > MaxNumNodes {
		return nil, fmt.Errorf("number of nodes must be under %d, got %d: %w", MaxNumNodes, numNodes, ErrNumNodesOverLimit)
	}
	nodes := make([]Node, 0, numNodes)
	for i := 0; i < numNodes; i++ {
		node, err := newNode(cpuPerNode, memoryPerNode)
		if err != nil {
			return nil, err
		}
		nodes = append(nodes, *node)
	}
	return &Nodes{nodes, cpuPerNode, memoryPerNode}, nil
}

// NewNodesByCPU creates and initializes Nodes by specifying CPU only
func NewNodesByCPU(cpuPerNode CPU, numNodes int) (*Nodes, error) {
	if numNodes <= 0 {
		return nil, fmt.Errorf("number of nodes must be positive, got %d: %w", numNodes, ErrNumNodesNegative)
	}
	if numNodes > MaxNumNodes {
		return nil, fmt.Errorf("number of nodes must be under %d, got %d: %w", MaxNumNodes, numNodes, ErrNumNodesOverLimit)
	}
	nodes := make([]Node, 0, numNodes)
	minMemoryInGiB, _ := CalculateMinMaxMemoryInGiBByCPU(cpuPerNode)
	for i := 0; i < numNodes; i++ {
		node, err := newNode(cpuPerNode, GiBToBytes(minMemoryInGiB))
		if err != nil {
			return nil, err
		}
		nodes = append(nodes, *node)
	}
	return &Nodes{nodes, cpuPerNode, GiBToBytes(minMemoryInGiB)}, nil
}

func (n *Nodes) SchedulableCPU(cpuUsage CPU) bool {
	return n.nodes[0].SchedulableCPU(cpuUsage)
}

func (n *Nodes) SchedulableMemory(memoryUsage Memory) bool {
	return n.nodes[0].SchedulableMemory(memoryUsage)
}

func (n *Nodes) CanScheduleAllMemoryUsages(memoryUsages []Memory) bool {
	sort.SliceStable(memoryUsages, func(i, j int) bool {
		return memoryUsages[j] < memoryUsages[i]
	})
	for _, memoryUsage := range memoryUsages {
		foundAppropriateNode := false
		for i := range n.nodes {
			scheduled := n.nodes[i].ScheduleMemory(memoryUsage)
			if scheduled {
				foundAppropriateNode = true
				break
			}
		}
		if !foundAppropriateNode {
			return false
		}
	}
	return true
}

func (n *Nodes) FirstFitDecreasingByCPU(cpuUsages []CPU) (int, error) {
	sort.SliceStable(cpuUsages, func(i, j int) bool {
		return cpuUsages[j] < cpuUsages[i]
	})

	maxUsage := cpuUsages[0]

	if !n.nodes[0].SchedulableCPU(maxUsage) {
		return 0, errors.New("cannot find appropriate number of nodes")
	}

	for len(cpuUsages) > 0 {
		foundAppropriateNode := false
		for i := range n.nodes {
			scheduled := n.nodes[i].ScheduleCPU(cpuUsages[0])
			if scheduled {
				cpuUsages = cpuUsages[1:]
				foundAppropriateNode = true
				break
			}
		}
		if !foundAppropriateNode {
			err := n.appendOneNode()
			if err != nil {
				glog.Error("Failed to append one node")
			}
		}
	}
	return len(n.nodes), nil
}

func MaxCPU(cpus []CPU) CPU {
	var max CPU
	for _, cpu := range cpus {
		if cpu > max {
			max = cpu
		}
	}
	return max
}

func MaxMemory(memories []Memory) Memory {
	var max Memory
	for _, memory := range memories {
		if memory > max {
			max = memory
		}
	}
	return max
}

func (n *Nodes) CPUCapacityForUserWorkloads() CPU {
	return calculateRemainingCPU(n.nodes[0].cpuOnGCE)
}

func (n *Nodes) MemoryCapacityForUserWorkloads() Memory {
	return calculateRemainingMemory(n.nodes[0].memoryOnGCE)
}

func (n *Nodes) MemoryKernelUsage() Memory {
	return calculateKernelUsageMemory(n.nodes[0].memoryOnGCE)
}

func (n *Nodes) ReservedCPU() CPU {
	reserved := reservedCPU(n.nodes[0].cpuOnGCE)
	return reserved
}

func (n *Nodes) ReservedMemory() Memory {
	return reservedMemory(n.nodes[0].memoryOnGCE)
}

func (n *Nodes) appendOneNode() error {
	if len(n.nodes) >= MaxNumNodes {
		return fmt.Errorf("can't append a node over %d nodes", MaxNumNodes)
	}
	// The error won't occur since error must have been captured in NewNodes
	newNode, err := newNode(n.cpuPerNode, n.memoryPerNode)
	if err != nil {
		glog.Errorf("Failed to create a new node with %f cpus and %d GiB memory", n.cpuPerNode, n.memoryPerNode)
	}
	n.nodes = append(n.nodes, *newNode)
	return nil
}
