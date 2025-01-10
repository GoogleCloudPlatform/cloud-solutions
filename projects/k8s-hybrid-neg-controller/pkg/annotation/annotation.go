// Copyright 2024 Google LLC
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

package annotation

const (
	HybridNEGConfigKey = "solutions.cloud.google.com/hybrid-neg"
	HybridNEGStatusKey = "solutions.cloud.google.com/hybrid-neg-status"
)

// NEGAttributes contains the name used when creating zonal hybrid NEGs.
// The name is optional in the config annotation, a NEG name will be generated if not supplied.
type NEGAttributes struct {
	Name string `json:"name,omitempty"`
}

// ServicePortNEGMap is the mapping from service port number to hybrid NEG name.
type ServicePortNEGMap map[string]string

// NEGConfig is used to unmarshal the hybrid NEG config annotation. Its structure is based on the
// GKE NEG config annotation, see
// https://cloud.google.com/kubernetes-engine/docs/how-to/standalone-neg#naming_negs
type NEGConfig struct {
	// ExposedPorts specifies the service ports to be exposed as zonal hybrid NEGs,
	// and attributes of the NEGs (currently only the optional name).
	ExposedPorts map[int32]NEGAttributes `json:"exposed_ports,omitempty"`
	// Ingress is not used by this controller. It is included so that this struct matches the
	// `cloud.google.com/neg` annotation used by GKE's built-in NEG controller.
	Ingress bool `json:"ingress,omitempty"`
}

// NEGStatus is used to marshal and unmarshal the hybrid NEG status annotation created by this
// controller. Its structure is based on the GKE NEG status annotation, see
// https://cloud.google.com/kubernetes-engine/docs/how-to/standalone-neg#retrieve-neg-status
type NEGStatus struct {
	// NetworkEndpointGroups is the mapping from service port number to hybrid NEG name.
	NetworkEndpointGroups ServicePortNEGMap `json:"network_endpoint_groups,omitempty"`
	// Zones is a list of zones where the hybrid NEGs exist.
	Zones []string `json:"zones,omitempty"`
}
