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

package v1

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

// EDIT THIS FILE!  THIS IS SCAFFOLDING FOR YOU TO OWN!
// NOTE: json tags are required.  Any new fields you add must have json tags for the fields to be serialized.

// PtTaskSpec defines the desired state of PtTask
type PtTaskSpec struct {
	// Task type
	//+kubebuilder:default:=Local
	//+kubebuilder:validation:Enum:=Local;Distribution
	Type string `json:"type"`

	// Execution for different scenarios
	Execution []PtTaskExecution `json:"execution"`
	// (scenario name) -> (PtTaskScenario)
	Scenarios map[string]PtTaskScenario `json:"scenarios"`

	// Container images for the scenario: (scenario name) -> (PtTaskImages)
	Images map[string]PtTaskImages `json:"images"`

	// Traffics definition: (scenario name) -> (PtTaskTraffic)
	Traffics map[string][]PtTaskTraffic `json:"traffics,omitempty"`

	// Testing output
	TestingOutput PtTaskTestingOutput `json:"testingOutput"`
}

// PtTaskExecution defines the execution of a scenario
type PtTaskExecution struct {
	// Executor type: locust, jmeter, etc from https://gettaurus.org/docs/Executors/
	//+kubebuilder:default:=locust
	//+kubebuilder:validation:Enum:=locust;jmeter
	Executor string `json:"executor"`
	// The number of target concurrent virtual users
	Concurrency int `json:"concurrency"`
	// Time to hold target concurrency
	HoldFor string `json:"hold-for"`
	// Ramp-up time to reach target concurrency
	RampUp string `json:"ramp-up"`
	// Limit scenario iterations number
	Iterations int `json:"iterations,omitempty"`
	// The name of scenario that described in scenarios part
	Scenario string `json:"scenario"`
	// Is master or not
	//+kubebuilder:default:=true
	//+kubebuilder:validation:Enum:=true;false
	Master bool `json:"master,omitempty"`
	// Numbers of workers, calculated if not specified
	//+kubebuilder:validation:Minimum=1
	Workers int `json:"workers,omitempty"`
}

// PtTaskScenario defines the scenario
type PtTaskScenario struct {
	DefaultAddress string `json:"default-address"`
	Script         string `json:"script"`
}

// PtTaskImages defines the images for a scenario
type PtTaskImages struct {
	// The image for master node
	MasterImage string `json:"masterImage"`
	// The image for worker node
	WorkerImage string `json:"workerImage"`
}

// PtTaskTraffic defines the traffic for a scenario
type PtTaskTraffic struct {
	// Base64 key for service account
	SAKey64 string `json:"saKey64,omitempty"`
	// Base64 CA acertificate
	GKECA64 string `json:"gkeCA64,omitempty"`
	// External endpoint for GKE
	GKEEndpoint string `json:"gkeEndpoint,omitempty"`
	// The region where GKE cluster is provisioned
	Region string `json:"region"`
	// The percentage for traffic: currency * precent/100
	Percent int `json:"percent,omitempty"`
}

// PtTaskTestingOutput defines the testing output for a scenario
type PtTaskTestingOutput struct {
	// Where to store testing logs
	LogDir string `json:"logDir"`
	// Testing logs for Locust: locust-workers.ldjson
	Ldjson string `json:"ldjson,omitempty"`
	// Testing logs for JMeter: jmeter.jtl
	Jtl string `json:"jtl,omitempty"`
	// Archiving GCS bucket
	Bucket string `json:"bucket"`
}

var (
	PT_STATUS_UNKNOWN               = "UNKNOWN"
	PT_STATUS_INITIAL               = "INITIAL"
	PT_STATUS_PROVISIONING          = "PROVISIONING"
	PT_STATUS_PROVISIONING_MASTER   = "PROVISIONING_MASTER"
	PT_STATUS_PROVISIONING_WORKER   = "PROVISIONING_WORKER"
	PT_STATUS_PROVISIONING_FINISHED = "PROVISIONING_FINISHED"
	PT_STATUS_PROVISIONING_FAILED   = "PROVISIONING_FAILED"
	PT_STATUS_PENDING               = "PENDING"
	PT_STATUS_TESTING               = "TESTING"
	PT_STATUS_FINISHED              = "FINISHED"
	PT_STATUS_CANCELLED             = "CANCELLED"
	PT_STATUS_CANCELLING            = "CANCELLING"
	PT_STATUS_FAILED                = "FAILED"
)

// PtTaskStatus defines the observed state of PtTask
type PtTaskStatus struct {

	// Phases included status per testing scenario: (scenario name) -> (PT_STATUS_*)
	Phases map[string]string `json:"phase,omitempty"`
	// Archive for each scenario: (scenario name) -> (archived timestamp)
	Archives map[string]string `json:"archives,omitempty"`
	// Each PtTask has an unique Id
	Id string `json:"id"`

	// The status of the pttask:: PT_STATUS_*
	PtStatus string `json:"ptStatus"`
}

//+kubebuilder:object:root=true
//+kubebuilder:subresource:status

// PtTask is the Schema for the pttasks API
type PtTask struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   PtTaskSpec   `json:"spec,omitempty"`
	Status PtTaskStatus `json:"status,omitempty"`
}

//+kubebuilder:object:root=true

// PtTaskList contains a list of PtTask
type PtTaskList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []PtTask `json:"items"`
}

func init() {
	SchemeBuilder.Register(&PtTask{}, &PtTaskList{})
}
