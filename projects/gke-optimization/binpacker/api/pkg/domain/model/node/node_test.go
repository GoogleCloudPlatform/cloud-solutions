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

func TestNode_ScheduleCPU(t *testing.T) {
	type fields struct {
		cpuOnGCE        CPU
		memoryOnGCE     Memory
		remainingCPU    CPU
		remainingMemory Memory
	}
	type args struct {
		cpuUsage CPU
	}
	validNode, err := newNode(2, GiBToBytes(2))
	if err != nil {
		glog.Errorf("Failed to create a new node with %d cpus and %d GiB memory", 2, 2)
	}
	validFields := fields{
		cpuOnGCE:        validNode.cpuOnGCE,
		memoryOnGCE:     validNode.memoryOnGCE,
		remainingCPU:    validNode.remainingCPU,
		remainingMemory: validNode.remainingMemory,
	}
	tests := []struct {
		name   string
		fields fields
		args   args
		want   bool
	}{
		{"Schedulable", validFields, args{0.5}, true},
		{"Schedulable (boundary)", validFields, args{0.93}, true},
		{"Not schedulable", validFields, args{1}, false},
		{"Not schedulable (boundary)", validFields, args{0.94}, false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			n := &Node{
				cpuOnGCE:        tt.fields.cpuOnGCE,
				memoryOnGCE:     tt.fields.memoryOnGCE,
				remainingCPU:    tt.fields.remainingCPU,
				remainingMemory: tt.fields.remainingMemory,
			}
			if got := n.ScheduleCPU(tt.args.cpuUsage); got != tt.want {
				t.Errorf("Node.ScheduleCPU() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestNode_ScheduleMemory(t *testing.T) {
	type fields struct {
		cpuOnGCE        CPU
		memoryOnGCE     Memory
		remainingCPU    CPU
		remainingMemory Memory
	}
	type args struct {
		memoryUsage Memory
	}
	validNode, err := newNode(2, GiBToBytes(2))
	if err != nil {
		glog.Errorf("Failed to create a new node with %d cpus and %d GiB memory", 2, 2)
	}
	validFields := fields{
		cpuOnGCE:        validNode.cpuOnGCE,
		memoryOnGCE:     validNode.memoryOnGCE,
		remainingCPU:    validNode.remainingCPU,
		remainingMemory: validNode.remainingMemory,
	}
	tests := []struct {
		name   string
		fields fields
		args   args
		want   bool
	}{
		{"Schedulable", validFields, args{MiBToBytes(100)}, true},
		{"Schedulable (boundary)", validFields, args{454662554}, true},
		{"Not schedulable", validFields, args{GiBToBytes(2)}, false},
		{"Not schedulable (boundary)", validFields, args{454662555}, false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			n := &Node{
				cpuOnGCE:        tt.fields.cpuOnGCE,
				memoryOnGCE:     tt.fields.memoryOnGCE,
				remainingCPU:    tt.fields.remainingCPU,
				remainingMemory: tt.fields.remainingMemory,
			}
			if got := n.ScheduleMemory(tt.args.memoryUsage); got != tt.want {
				t.Errorf("Node.ScheduleMemory() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestNode_SchedulableCPU(t *testing.T) {
	type fields struct {
		cpuOnGCE        CPU
		memoryOnGCE     Memory
		remainingCPU    CPU
		remainingMemory Memory
	}
	type args struct {
		cpuUsage CPU
	}
	validNode, err := newNode(2, GiBToBytes(2))
	if err != nil {
		glog.Errorf("Failed to create a new node with %d cpus and %d GiB memory", 2, 2)
	}
	validFields := fields{
		cpuOnGCE:        validNode.cpuOnGCE,
		memoryOnGCE:     validNode.memoryOnGCE,
		remainingCPU:    validNode.remainingCPU,
		remainingMemory: validNode.remainingMemory,
	}
	tests := []struct {
		name   string
		fields fields
		args   args
		want   bool
	}{
		{"Schedulable", validFields, args{0.5}, true},
		{"Schedulable (boundary)", validFields, args{0.93}, true},
		{"Not schedulable", validFields, args{1}, false},
		{"Not schedulable (boundary)", validFields, args{0.94}, false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			n := &Node{
				cpuOnGCE:        tt.fields.cpuOnGCE,
				memoryOnGCE:     tt.fields.memoryOnGCE,
				remainingCPU:    tt.fields.remainingCPU,
				remainingMemory: tt.fields.remainingMemory,
			}
			if got := n.SchedulableCPU(tt.args.cpuUsage); got != tt.want {
				t.Errorf("Node.SchedulableCPU() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestNode_SchedulableMemory(t *testing.T) {
	type fields struct {
		cpuOnGCE        CPU
		memoryOnGCE     Memory
		remainingCPU    CPU
		remainingMemory Memory
	}
	type args struct {
		memoryUsage Memory
	}
	validNode, err := newNode(2, GiBToBytes(2))
	if err != nil {
		glog.Errorf("Failed to create a new node with %d cpus and %d GiB memory", 2, 2)
	}
	validFields := fields{
		cpuOnGCE:        validNode.cpuOnGCE,
		memoryOnGCE:     validNode.memoryOnGCE,
		remainingCPU:    validNode.remainingCPU,
		remainingMemory: validNode.remainingMemory,
	}
	tests := []struct {
		name   string
		fields fields
		args   args
		want   bool
	}{
		{"Schedulable", validFields, args{MiBToBytes(100)}, true},
		{"Schedulable (boundary)", validFields, args{454662554}, true},
		{"Not schedulable", validFields, args{GiBToBytes(2)}, false},
		{"Not schedulable (boundary)", validFields, args{454662555}, false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			n := &Node{
				cpuOnGCE:        tt.fields.cpuOnGCE,
				memoryOnGCE:     tt.fields.memoryOnGCE,
				remainingCPU:    tt.fields.remainingCPU,
				remainingMemory: tt.fields.remainingMemory,
			}
			if got := n.SchedulableMemory(tt.args.memoryUsage); got != tt.want {
				t.Errorf("Node.SchedulableMemory() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestRoundCPU(t *testing.T) {
	type args struct {
		cpu CPU
	}
	tests := []struct {
		name string
		args args
		want CPU
	}{
		{"Correct (0.999999)", args{0.999999}, 1},
		{"Correct (1.111111)", args{1.111111}, 1.111},
		{"Correct (2.5555)", args{2.5555}, 2.556},
		{"Correct (3)", args{3}, 3},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := RoundCPU(tt.args.cpu); got != tt.want {
				t.Errorf("RoundCPU() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestGiBToBytes(t *testing.T) {
	type args struct {
		memoryInGiB MemoryInGiB
	}
	tests := []struct {
		name string
		args args
		want Memory
	}{
		{"Correct(1 GiB)", args{1}, 1073741824},
		{"Correct(2.25 GiB)", args{2.25}, 2415919104},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := GiBToBytes(tt.args.memoryInGiB); got != tt.want {
				t.Errorf("GiBToBytes() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestMiBToBytes(t *testing.T) {
	type args struct {
		memoryInMiB MemoryInMiB
	}
	tests := []struct {
		name string
		args args
		want Memory
	}{
		{"correct answer for 100 MiB", args{100}, 104857600},
		{"correct answer for 1 MiB", args{1}, 1048576},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := MiBToBytes(tt.args.memoryInMiB); got != tt.want {
				t.Errorf("MiBToBytes() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestByteToGiB(t *testing.T) {
	type args struct {
		memory Memory
	}
	tests := []struct {
		name string
		args args
		want MemoryInGiB
	}{
		{"correct answer for 1 GiB", args{1073741824}, 1},
		{"correct answer for 2.25 GiB", args{2415919104}, 2.25},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := ByteToGiB(tt.args.memory); got != tt.want {
				t.Errorf("ByteToGiB() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestMinRequiredCPU(t *testing.T) {
	type args struct {
		cpuUsage CPU
	}
	tests := []struct {
		name string
		args args
		want CPU
	}{
		{"zero", args{0.0}, 2},
		{"lower than the minimum number of cpus per node", args{0.001}, 2},
		{"bigger than the maximum numder of cpus per node", args{512}, MaxCPUPerNode},
		{"should return 4", args{2.9}, 4},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := MinRequiredCPU(tt.args.cpuUsage); got != tt.want {
				t.Errorf("MinRequiredCPU() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestCalculateMinMaxMemoryInGiBByCPU(t *testing.T) {
	type args struct {
		cpu CPU
	}
	tests := []struct {
		name  string
		args  args
		want  MemoryInGiB
		want1 MemoryInGiB
	}{
		{"lower than the minimum cpus", args{1}, 1, 8},
		{"minimum cpus", args{2}, 1, 16},
		{"16 cpus", args{16}, 8, 128},
		{"maximum cpus", args{80}, 40, 640},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, got1 := CalculateMinMaxMemoryInGiBByCPU(tt.args.cpu)
			if got != tt.want {
				t.Errorf("CalculateMinMaxMemoryInGiBByCPU() got = %v, want %v", got, tt.want)
			}
			if got1 != tt.want1 {
				t.Errorf("CalculateMinMaxMemoryInGiBByCPU() got1 = %v, want %v", got1, tt.want1)
			}
		})
	}
}

func Test_newNode(t *testing.T) {
	type args struct {
		cpuOnGCE    CPU
		memoryOnGCE Memory
	}
	tests := []struct {
		name    string
		args    args
		want    *Node
		wantErr bool
	}{
		{"cpu: less than minimum cpu per node", args{cpuOnGCE: 1, memoryOnGCE: GiBToBytes(2)}, nil, true},
		{"cpu: greater than maximum cpu per node", args{cpuOnGCE: 210, memoryOnGCE: GiBToBytes(128)}, nil, true},
		{"memory: less than minimum memory size per node", args{cpuOnGCE: 2, memoryOnGCE: GiBToBytes(0.5)}, nil, true},
		{"memory: greater than maximum memory size per node", args{cpuOnGCE: 128, memoryOnGCE: GiBToBytes(130)}, nil, true},
		{"memory: out of range based on the cpu", args{cpuOnGCE: 2, memoryOnGCE: GiBToBytes(128)}, nil, true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := newNode(tt.args.cpuOnGCE, tt.args.memoryOnGCE)
			if (err != nil) != tt.wantErr {
				t.Errorf("newNode() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if !reflect.DeepEqual(got, tt.want) {
				t.Errorf("newNode() = %v, want %v", got, tt.want)
			}
		})
	}
}

func Test_calculateRemainingCPU(t *testing.T) {
	type args struct {
		cpuOnGCE CPU
	}
	tests := []struct {
		name string
		args args
		want CPU
	}{
		{"2 CPUs node", args{2}, 0.93},
		{"16 CPUs node", args{16}, 14.89},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := calculateRemainingCPU(tt.args.cpuOnGCE); got != tt.want {
				t.Errorf("calculateRemainingCPU() = %v, want %v", got, tt.want)
			}
		})
	}
}

func Test_calculateRemainingMemory(t *testing.T) {
	type args struct {
		memoryOnGCE Memory
	}
	tests := []struct {
		name string
		args args
		want Memory
	}{
		{"2 GiB memory node", args{GiBToBytes(2)}, 454662554},
		{"16 GiB memory node", args{GiBToBytes(16)}, 12480570983},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := calculateRemainingMemory(tt.args.memoryOnGCE); got != tt.want {
				t.Errorf("calculateRemainingMemory() = %v, want %v", got, tt.want)
			}
		})
	}
}

func Test_reservedCPU(t *testing.T) {
	type args struct {
		cpuOnGCE CPU
	}
	tests := []struct {
		name string
		args args
		want CPU
	}{
		{"0.9 CPUs node", args{0.9}, 0.054},
		{"1.5 CPUs node", args{1.5}, 0.065},
		{"3 CPUs node", args{3}, 0.075},
		{"8 CPUs node", args{8}, 0.09},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := reservedCPU(tt.args.cpuOnGCE); got != tt.want {
				t.Errorf("reservedCPU() = %v, want %v", got, tt.want)
			}
		})
	}
}

func Test_reservedMemory(t *testing.T) {
	type args struct {
		memoryOnGCE Memory
	}
	tests := []struct {
		name string
		args args
		want Memory
	}{
		{"0.9 GiB memory node", args{GiBToBytes(0.9)}, 267386880},
		{"2 GiB memory node", args{GiBToBytes(2)}, 536870912},
		{"6 GiB memory node", args{GiBToBytes(6)}, 1503238553},
		{"12 GiB memory node", args{GiBToBytes(12)}, 2362232012},
		{"64 GiB memory node", args{GiBToBytes(64)}, 5884105195},
		{"128 GiB memory node", args{GiBToBytes(128)}, 10007273799},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := reservedMemory(tt.args.memoryOnGCE); got != tt.want {
				t.Errorf("reservedMemory() = %v, want %v", got, tt.want)
			}
		})
	}
}

func Test_validMemorySizeByCPU(t *testing.T) {
	type args struct {
		cpu    CPU
		memory Memory
	}
	tests := []struct {
		name string
		args args
		want bool
	}{
		{"valid memory size", args{cpu: 2, memory: GiBToBytes(2)}, true},
		{"memory size out of range (over)", args{cpu: 2, memory: GiBToBytes(64)}, false},
		{"memory size out of range (lower)", args{cpu: 64, memory: GiBToBytes(2)}, false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := validMemorySizeByCPU(tt.args.cpu, tt.args.memory); got != tt.want {
				t.Errorf("validMemorySizeByCPU() = %v, want %v", got, tt.want)
			}
		})
	}
}
