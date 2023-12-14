// Copyright 2023 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package helper

import (
	"reflect"
	"testing"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/util/intstr"
)

func TestBuildMasterPod4Locust(t *testing.T) {
	type args struct {
		ns       string
		img      string
		id       string
		scenario string
		trsConf  string
	}
	tests := []struct {
		name string
		args args
		want *corev1.Pod
	}{}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := BuildMasterPod4Locust(tt.args.ns, tt.args.img, tt.args.id, tt.args.scenario, tt.args.trsConf); !reflect.DeepEqual(got, tt.want) {
				t.Errorf("BuildMasterPod4Locust() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestBuildMasterService4Locust(t *testing.T) {
	type args struct {
		ns       string
		svcType  corev1.ServiceType
		scenario string
	}
	tests := []struct {
		name string
		args args
		want *corev1.Service
	}{
		// add test cases
		{
			name: "Normal service",
			args: args{
				ns:       "default",
				svcType:  corev1.ServiceTypeClusterIP,
				scenario: "test",
			},
			want: &corev1.Service{
				ObjectMeta: metav1.ObjectMeta{
					Name:      "locust-master-test-svc",
					Namespace: "default",
				},
				Spec: corev1.ServiceSpec{
					Type: corev1.ServiceTypeClusterIP,
					Selector: map[string]string{
						"app":      "locust-master",
						"scenario": "test",
					},
					Ports: []corev1.ServicePort{
						{
							Name: "tcp",
							Port: 5557,
							TargetPort: intstr.IntOrString{
								IntVal: 5557,
							},
						},
					},
				},
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := BuildMasterService4Locust(tt.args.ns, tt.args.svcType, tt.args.scenario); !reflect.DeepEqual(got, tt.want) {
				t.Errorf("BuildMasterService4Locust() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestBuildLocusterWorker4Locust(t *testing.T) {
	type args struct {
		ns         string
		img        string
		masterHost string
		masterPort string
		scenario   string
		workerId   string
	}
	tests := []struct {
		name string
		args args
		want *corev1.Pod
	}{
		{
			name: "Normal worker",
			args: args{
				ns:         "default",
				img:        "locustio/locust:1.2.3",
				masterHost: "locust-master",
				masterPort: "5557",
				scenario:   "test",
				workerId:   "1",
			},
			want: &corev1.Pod{
				ObjectMeta: metav1.ObjectMeta{
					Name:      "locust-worker-test-1",
					Namespace: "default",
					Labels: map[string]string{
						"module":   "performance-testing",
						"app":      "locust-worker",
						"scenario": "test",
					},
				},
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := BuildLocusterWorker4Locust(tt.args.ns, tt.args.img, tt.args.masterHost, tt.args.masterPort, tt.args.scenario, tt.args.workerId)
			if got.Name != tt.want.Name {
				t.Errorf("BuildLocusterWorker4Locust() = %v, want %v", got, tt.want.Name)
			}
			if got.Labels["scenario"] != tt.want.Labels["scenario"] {
				t.Errorf("BuildLocusterWorker4Locust() = %v, want %v", got, tt.want.Labels["scenario"])
			}
			if got.Labels["app"] != tt.want.Labels["app"] {
				t.Errorf("BuildLocusterWorker4Locust() = %v, want %v", got, tt.want.Labels["app"])
			}
			if got.Labels["module"] != tt.want.Labels["module"] {
				t.Errorf("BuildLocusterWorker4Locust() = %v, want %v", got, tt.want.Labels["module"])
			}
			// compare two array of string
			command := []string{"locust"}
			if !reflect.DeepEqual(got.Spec.Containers[0].Command, command) {
				t.Errorf("BuildLocusterWorker4Locust() = %v, want %v", got, command)
			}
			arg := []string{"--worker", "--master-host", "locust-master", "--master-port", "5557", "--loglevel", "DEBUG", "--exit-code-on-error", "0", "--logfile", "/tmp/worker.log"}
			if !reflect.DeepEqual(got.Spec.Containers[0].Args, arg) {
				t.Errorf("BuildLocusterWorker4Locust() = %v, want %v", got, arg)
			}
		})
	}
}
