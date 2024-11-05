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
	"reflect"
	"testing"

	"github.com/golang/glog"
)

func TestNewNodes(t *testing.T) {
	type args struct {
		cpuPerNode    CPU
		memoryPerNode Memory
		numNodes      int
	}
	validNode, err := newNode(2, GiBToBytes(2))
	if err != nil {
		glog.Errorf("Failed to create a new node with %d cpus and %d GiB memory", 2, 2)
	}
	tests := []struct {
		name    string
		args    args
		want    *Nodes
		wantErr bool
	}{
		{"number of nodes is less than 0", args{cpuPerNode: 2, memoryPerNode: GiBToBytes(2), numNodes: -1}, nil, true},
		{"number of nodes is 0", args{cpuPerNode: 2, memoryPerNode: GiBToBytes(2), numNodes: 0}, nil, true},
		{"number of nodes is greater than the maximum number of nodes", args{cpuPerNode: 2, memoryPerNode: GiBToBytes(2), numNodes: 20000}, nil, true},
		{"valid nodes", args{cpuPerNode: 2, memoryPerNode: GiBToBytes(2), numNodes: 2}, &Nodes{
			nodes: []Node{
				*validNode, *validNode,
			},
			cpuPerNode:    2,
			memoryPerNode: GiBToBytes(2),
		}, false},
		{"number of cpu is greater than the maximum number of cpu per node", args{cpuPerNode: 210, memoryPerNode: GiBToBytes(128), numNodes: 2}, nil, true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := NewNodes(tt.args.cpuPerNode, tt.args.memoryPerNode, tt.args.numNodes)
			if (err != nil) != tt.wantErr {
				t.Errorf("NewNodes() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if !reflect.DeepEqual(got, tt.want) {
				t.Errorf("NewNodes() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestNodes_SchedulableCPU(t *testing.T) {
	type fields struct {
		nodes         []Node
		cpuPerNode    CPU
		memoryPerNode Memory
	}
	type args struct {
		cpuUsage CPU
	}
	validNodes, err := NewNodes(2, GiBToBytes(2), 2)
	if err != nil {
		glog.Errorf("Failed to create new nodes with %d cpus and %d GiB memory and %d nodes", 2, 2, 2)
	}
	validFields := fields{nodes: validNodes.nodes, cpuPerNode: 2, memoryPerNode: GiBToBytes(2)}
	tests := []struct {
		name   string
		fields fields
		args   args
		want   bool
	}{
		{"schedulable", validFields, args{0.01}, true},
		{"not schedulable", validFields, args{1.5}, false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			n := &Nodes{
				nodes:         tt.fields.nodes,
				cpuPerNode:    tt.fields.cpuPerNode,
				memoryPerNode: tt.fields.memoryPerNode,
			}
			if got := n.SchedulableCPU(tt.args.cpuUsage); got != tt.want {
				t.Errorf("Nodes.SchedulableCPU() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestNodes_SchedulableMemory(t *testing.T) {
	type fields struct {
		nodes         []Node
		cpuPerNode    CPU
		memoryPerNode Memory
	}
	type args struct {
		memoryUsage Memory
	}
	validNodes, err := NewNodes(2, GiBToBytes(2), 2)
	if err != nil {
		glog.Errorf("Failed to create new nodes with %d cpus and %d GiB memory and %d nodes", 2, 2, 2)
	}
	validFields := fields{nodes: validNodes.nodes, cpuPerNode: 2, memoryPerNode: GiBToBytes(2)}
	tests := []struct {
		name   string
		fields fields
		args   args
		want   bool
	}{
		{"schedulable", validFields, args{MiBToBytes(100)}, true},
		{"not schedulable", validFields, args{GiBToBytes(2)}, false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			n := &Nodes{
				nodes:         tt.fields.nodes,
				cpuPerNode:    tt.fields.cpuPerNode,
				memoryPerNode: tt.fields.memoryPerNode,
			}
			if got := n.SchedulableMemory(tt.args.memoryUsage); got != tt.want {
				t.Errorf("Nodes.SchedulableMemory() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestNodes_CanScheduleAllMemoryUsages(t *testing.T) {
	type fields struct {
		nodes         []Node
		cpuPerNode    CPU
		memoryPerNode Memory
	}
	type args struct {
		memoryUsages []Memory
	}
	validNodes, err := NewNodes(2, GiBToBytes(2), 2)
	if err != nil {
		glog.Errorf("Failed to create new nodes with %d cpus and %d GiB memory and %d nodes", 2, 2, 2)
	}
	validFields := fields{nodes: validNodes.nodes, cpuPerNode: 2, memoryPerNode: GiBToBytes(2)}
	tests := []struct {
		name   string
		fields fields
		args   args
		want   bool
	}{
		{"schedulable", validFields, args{[]Memory{MiBToBytes(100), MiBToBytes(200)}}, true},
		{"not schedulable", validFields, args{[]Memory{MiBToBytes(500), MiBToBytes(600)}}, false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			n := &Nodes{
				nodes:         tt.fields.nodes,
				cpuPerNode:    tt.fields.cpuPerNode,
				memoryPerNode: tt.fields.memoryPerNode,
			}
			if got := n.CanScheduleAllMemoryUsages(tt.args.memoryUsages); got != tt.want {
				t.Errorf("Nodes.CanScheduleAllMemoryUsages() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestNodes_FirstFitDecreasingByCPU(t *testing.T) {
	type fields struct {
		nodes         []Node
		cpuPerNode    CPU
		memoryPerNode Memory
	}
	type args struct {
		cpuUsages []CPU
	}
	validNodes1, err := NewNodes(2, GiBToBytes(2), 2)
	if err != nil {
		glog.Errorf("Failed to create new nodes with %d cpus and %d GiB memory and %d nodes", 2, 2, 2)
	}
	validNodes2, err := NewNodes(2, GiBToBytes(2), 2)
	if err != nil {
		glog.Errorf("Failed to create new nodes with %d cpus and %d GiB memory and %d nodes", 2, 2, 2)
	}
	validNodes3, err := NewNodes(2, GiBToBytes(2), 2)
	if err != nil {
		glog.Errorf("Failed to create new nodes with %d cpus and %d GiB memory and %d nodes", 2, 2, 2)
	}
	validFields1 := fields{nodes: validNodes1.nodes, cpuPerNode: 2, memoryPerNode: GiBToBytes(2)}
	validFields2 := fields{nodes: validNodes2.nodes, cpuPerNode: 2, memoryPerNode: GiBToBytes(2)}
	validFields3 := fields{nodes: validNodes3.nodes, cpuPerNode: 2, memoryPerNode: GiBToBytes(2)}
	tests := []struct {
		name    string
		fields  fields
		args    args
		want    int
		wantErr bool
	}{
		{"max cpu usage is bigger than node size", validFields1, args{[]CPU{0.1, 2.1, 0.5}}, 0, true},
		{"schedulable without appending new nodes", validFields2, args{[]CPU{0.1, 0.2, 0.3}}, 2, false},
		{"schedulable with appending new nodes", validFields3, args{[]CPU{0.5, 0.5, 0.5}}, 3, false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			n := &Nodes{
				nodes:         tt.fields.nodes,
				cpuPerNode:    tt.fields.cpuPerNode,
				memoryPerNode: tt.fields.memoryPerNode,
			}
			got, err := n.FirstFitDecreasingByCPU(tt.args.cpuUsages)
			if (err != nil) != tt.wantErr {
				t.Errorf("Nodes.FirstFitDecreasingByCPU() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if got != tt.want {
				t.Errorf("Nodes.FirstFitDecreasingByCPU() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestMaxCPU(t *testing.T) {
	type args struct {
		cpus []CPU
	}
	tests := []struct {
		name string
		args args
		want CPU
	}{
		{"all numbers are different", args{[]CPU{0.5, 0.7, 0.3}}, 0.7},
		{"all numbers are same", args{[]CPU{0.2, 0.2, 0.2}}, 0.2},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := MaxCPU(tt.args.cpus); got != tt.want {
				t.Errorf("MaxCPU() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestMaxMemory(t *testing.T) {
	type args struct {
		memories []Memory
	}
	tests := []struct {
		name string
		args args
		want Memory
	}{
		{"all numbers are different", args{[]Memory{MiBToBytes(50), MiBToBytes(70), MiBToBytes(30)}}, MiBToBytes(70)},
		{"all numbers are same", args{[]Memory{MiBToBytes(20), MiBToBytes(20), MiBToBytes(20)}}, MiBToBytes(20)},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := MaxMemory(tt.args.memories); got != tt.want {
				t.Errorf("MaxMemory() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestNodes_appendOneNode(t *testing.T) {
	type fields struct {
		nodes         []Node
		cpuPerNode    CPU
		memoryPerNode Memory
	}
	validNodes, err := NewNodes(2, GiBToBytes(2), 2)
	if err != nil {
		glog.Errorf("Failed to create new nodes with %d cpus and %d GiB memory and %d nodes", 2, 2, 2)
	}
	limitNodes, err := NewNodes(2, GiBToBytes(2), MaxNumNodes)
	if err != nil {
		glog.Errorf("Failed to create new nodes with %d cpus and %d GiB memory and %d nodes", 2, 2, MaxNumNodes)
	}
	validFields := fields{nodes: validNodes.nodes, cpuPerNode: 2, memoryPerNode: GiBToBytes(2)}
	limitFields := fields{nodes: limitNodes.nodes, cpuPerNode: 2, memoryPerNode: GiBToBytes(2)}
	tests := []struct {
		name    string
		fields  fields
		wantErr bool
	}{
		{"successfully append a node", validFields, false},
		{"cannot append a node if it reaches the max number of nodes", limitFields, true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			n := &Nodes{
				nodes:         tt.fields.nodes,
				cpuPerNode:    tt.fields.cpuPerNode,
				memoryPerNode: tt.fields.memoryPerNode,
			}
			if err := n.appendOneNode(); (err != nil) != tt.wantErr {
				t.Errorf("Nodes.appendOneNode() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}
