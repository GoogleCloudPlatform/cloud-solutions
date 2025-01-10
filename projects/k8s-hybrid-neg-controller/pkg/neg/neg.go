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

package neg

import (
	"context"
	"fmt"

	compute "cloud.google.com/go/compute/apiv1"
	"cloud.google.com/go/compute/apiv1/computepb"
	"google.golang.org/api/option"

	"github.com/googlecloudplatform/k8s-hybrid-neg-controller/pkg/config"
	"github.com/googlecloudplatform/k8s-hybrid-neg-controller/pkg/version"
)

const (
	// negTypeHybrid is the enum value for the type hybrid connectivity NEGs.
	negTypeHybrid = "NON_GCP_PRIVATE_IP_PORT"
)

type Client struct {
	client    *compute.NetworkEndpointGroupsClient
	network   string
	projectID string
	timeouts  config.Timeouts
	zones     []string
}

// EndpointSet represents a set of network endpoints.
// The map key is a string representation of the network endpoint in the format `[IP address]:[port]`.
type EndpointSet map[string]*computepb.NetworkEndpoint

func (e EndpointSet) Contains(ep *computepb.NetworkEndpoint) bool {
	if ep == nil {
		return false
	}
	_, exists := e[endpointToString(ep)]
	return exists
}

func (e EndpointSet) Put(ep *computepb.NetworkEndpoint) {
	e[endpointToString(ep)] = ep
}

// ZonalEndpoints groups network endpoints, keyed by their zone.
type ZonalEndpoints map[string]EndpointSet

// ServiceEndpoints is the set of network endpoints for a Service, keyed by the Service port name.
// It includes endpoints of all Service ports referenced in the hybrid NEG annotations.
type ServiceEndpoints map[string]ZonalEndpoints

func NewClient(ctx context.Context, network string, projectID string, timeouts config.Timeouts, zones []string) (*Client, error) {
	computeNEGClient, err := compute.NewNetworkEndpointGroupsRESTClient(ctx, option.WithUserAgent(version.UserAgent()))
	if err != nil {
		return nil, fmt.Errorf("problem creating Compute Engine NEG API client: %w", err)
	}
	return &Client{
		client:    computeNEGClient,
		network:   network,
		projectID: projectID,
		timeouts:  timeouts,
		zones:     zones,
	}, nil
}
