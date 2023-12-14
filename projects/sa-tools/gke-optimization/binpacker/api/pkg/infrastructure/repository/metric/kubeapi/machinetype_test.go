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
	"reflect"
	"testing"
)

func Test_getSpecFromCustomMachineType(t *testing.T) {
	type args struct {
		customMachineType string
	}
	tests := []struct {
		name    string
		args    args
		want    *Spec
		wantErr bool
	}{
		{"Not custom machine type", args{"e2-medium"}, nil, true},
		{"Valid custom machine type: e2", args{"e2-custom-6-3072"}, &Spec{CPU: 6, MemoryInGiB: 3}, false},
		{"Valid custom machine type: n2d", args{"n2d-custom-4-5120"}, &Spec{CPU: 4, MemoryInGiB: 5}, false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := getSpecFromCustomMachineType(tt.args.customMachineType)
			if (err != nil) != tt.wantErr {
				t.Errorf("getSpecFromCustomMachineType() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if !reflect.DeepEqual(got, tt.want) {
				t.Errorf("getSpecFromCustomMachineType() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestMachineTypes_getCPU(t *testing.T) {
	type fields struct {
		Types map[string]Spec
	}
	type args struct {
		machineType string
	}
	tests := []struct {
		name   string
		fields fields
		args   args
		want   int
	}{
		// TODO: Add test cases.
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			m := &MachineTypes{
				Types: tt.fields.Types,
			}
			if got := m.getCPU(tt.args.machineType); got != tt.want {
				t.Errorf("MachineTypes.getCPU() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestMachineTypes_getMemoryInGiB(t *testing.T) {
	type fields struct {
		Types map[string]Spec
	}
	type args struct {
		machineType string
	}
	tests := []struct {
		name   string
		fields fields
		args   args
		want   float64
	}{
		// TODO: Add test cases.
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			m := &MachineTypes{
				Types: tt.fields.Types,
			}
			if got := m.getMemoryInGiB(tt.args.machineType); got != tt.want {
				t.Errorf("MachineTypes.getMemoryInGiB() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestCreateMachineTypes(t *testing.T) {
	type args struct {
		ctx       context.Context
		projectID string
	}
	tests := []struct {
		name    string
		args    args
		want    *MachineTypes
		wantErr bool
	}{
		// TODO: Add test cases.
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := CreateMachineTypes(tt.args.ctx, tt.args.projectID)
			if (err != nil) != tt.wantErr {
				t.Errorf("CreateMachineTypes() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if !reflect.DeepEqual(got, tt.want) {
				t.Errorf("CreateMachineTypes() = %v, want %v", got, tt.want)
			}
		})
	}
}
