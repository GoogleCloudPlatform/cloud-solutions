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

package api

// PtTaskSpec defines the desired state of PtTask
type PtTaskSpec struct {
	// Task type
	//+kubebuilder:default:=Local
	//+kubebuilder:validation:Enum:=Local;Distribution
	Type string `yaml:"type"`

	// Execution for different scenarios
	Execution []PtTaskExecution `yaml:"execution"`
	// (scenario name) -> (PtTaskScenario)
	Scenarios map[string]PtTaskScenario `yaml:"scenarios"`

	// Container images for the scenario: (scenario name) -> (PtTaskImages)
	Images map[string]PtTaskImages `yaml:"images"`

	// Traffics definition: (scenario name) -> (PtTaskTraffic)
	Traffics map[string][]PtTaskTraffic `yaml:"traffics,omitempty"`

	// Testing output
	TestingOutput PtTaskTestingOutput `yaml:"testingOutput"`
}

// PtTaskExecution defines the execution of a scenario
type PtTaskExecution struct {
	// Executor type: locust, jmeter, etc from https://gettaurus.org/docs/Executors/
	//+kubebuilder:default:=locust
	//+kubebuilder:validation:Enum:=locust;jmeter
	Executor string `yaml:"executor"`
	// The number of target concurrent virtual users
	Concurrency int `yaml:"concurrency"`
	// Time to hold target concurrency
	HoldFor string `yaml:"hold-for"`
	// Ramp-up time to reach target concurrency
	RampUp string `yaml:"ramp-up"`
	// Limit scenario iterations number
	Iterations int `yaml:"iterations,omitempty"`
	// The name of scenario that described in scenarios part
	Scenario string `yaml:"scenario"`
	// Is master or not
	//+kubebuilder:default:=true
	//+kubebuilder:validation:Enum:=true;false
	Master bool `yaml:"master,omitempty"`
	// Numbers of workers, calculated if not specified
	//+kubebuilder:validation:Minimum=1
	Workers int `yaml:"workers,omitempty"`
}

// PtTaskScenario defines the scenario
type PtTaskScenario struct {
	DefaultAddress string `yaml:"default-address"`
	Script         string `yaml:"script"`
}

// PtTaskImages defines the images for a scenario
type PtTaskImages struct {
	// The image for master node
	MasterImage string `yaml:"masterImage"`
	// The image for worker node
	WorkerImage string `yaml:"workerImage"`
}

// PtTaskTraffic defines the traffic for a scenario
type PtTaskTraffic struct {
	// Base64 key for service account
	SAKey64 string `yaml:"saKey64,omitempty"`
	// Base64 CA acertificate
	GKECA64 string `yaml:"gkeCA64,omitempty"`
	// External endpoint for GKE
	GKEEndpoint string `yaml:"gkeEndpoint,omitempty"`
	// The region where GKE cluster is provisioned
	Region string `yaml:"region"`
	// The percentage for traffic: currency * precent/100
	Percent int `yaml:"percent"`
}

// PtTaskTestingOutput defines the testing output for a scenario
type PtTaskTestingOutput struct {
	// Where to store testing logs
	LogDir string `yaml:"logDir,omitempty"`
	// Testing logs for Locust: locust-workers.ldjson
	Ldjson string `yaml:"ldjson,omitempty"`
	// Testing logs for JMeter: jmeter.jtl
	Jtl string `yaml:"jtl,omitempty"`
	// Archiving GCS bucket
	Bucket string `yaml:"bucket"`
}

// PtTaskStatus defines the observed state of PtTask
type PtTaskStatus struct {

	// Phases included following status per testing scenario: (scenario name) -> (phase)
	// - "PrivisionMaster",
	// - "ProvisionWorker",
	// - "Testing",
	// - "Done"
	Phases map[string]string `yaml:"phase,omitempty"`
	// Archive for each scenario: (scenario name) -> (archived timestamp)
	Archives map[string]string `yaml:"archives,omitempty"`
	// Each PtTask has an unique Id
	ID string `yaml:"id"`
}

// PtTask is the Schema for the pttasks API
type PtTask struct {
	Kind       string       `yaml:"kind,omitempty"`
	APIVersion string       `yaml:"apiVersion,omitempty"`
	Metadata   MyObjectMeta `yaml:"metadata,omitempty"`
	Spec       PtTaskSpec   `yaml:"spec,omitempty"`
	Status     PtTaskStatus `yaml:"status,omitempty"`
}

type MyObjectMeta struct {
	Name        string            `yaml:"name,omitempty"`
	Namespace   string            `yaml:"namespace,omitempty"`
	Labels      map[string]string `yaml:"labels,omitempty"`
	Annotations map[string]string `yaml:"annotations,omitempty"`
}
