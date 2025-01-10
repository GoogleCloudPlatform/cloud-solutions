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
	"errors"
	"fmt"
	"net/http"
	"time"

	"cloud.google.com/go/compute/apiv1/computepb"
	"github.com/go-logr/logr"
	"github.com/gogo/protobuf/proto"
	"golang.org/x/sync/errgroup"
	"google.golang.org/api/googleapi"
	"k8s.io/apimachinery/pkg/types"
)

// CreateNEGs creates zonal hybrid connectivity Network Endpoint Groups with the supplied name
// in each of the zones configured on the `NEGClient`.
func (c *Client) CreateNEGs(ctx context.Context, logger logr.Logger, name string, service types.NamespacedName) error {
	logger = logger.WithValues("GoogleCloudProjectID", c.projectID, "type", negTypeHybrid, "NetworkEndpointGroup", name)
	neg := newNetworkEndpointGroup(name, c.projectID, c.network, service)
	g, groupCtx := errgroup.WithContext(ctx)
	for _, zone := range c.zones {
		g.Go(func() error {
			return c.createZonalNEG(groupCtx, logger, zone, neg)
		})
	}
	if err := g.Wait(); err != nil {
		return fmt.Errorf("problem creating NEGs name=%s in zones=%+v: %w", name, c.zones, err)
	}
	return nil
}

// createZonalNEG does not use locking to prevent multiple goroutines from creating the same NEG
// at the same time. Instead, the method checks for `isNotModified` and `isAlreadyExists` errors.
func (c *Client) createZonalNEG(ctx context.Context, logger logr.Logger, zone string, neg *computepb.NetworkEndpointGroup) error {
	logger.Info("Creating zonal NEG async", "zone", zone)
	ctxWithDeadline, cancel := context.WithDeadline(ctx, time.Now().Add(c.timeouts.CreateZonalNEG))
	defer cancel()
	_, err := c.client.Insert(ctxWithDeadline, &computepb.InsertNetworkEndpointGroupRequest{
		NetworkEndpointGroupResource: neg,
		Project:                      c.projectID,
		Zone:                         zone,
	})
	if err != nil && !googleapi.IsNotModified(err) && !isAlreadyExists(err) {
		return fmt.Errorf("problem creating NEG of type=%s for projectID=%s zone=%s: %w", negTypeHybrid, c.projectID, zone, err)
	}
	logger.Info("Created zonal NEG", "zone", zone)
	return nil
}

// newNetworkEndpointGroup creates a `compute.NetworkEndpointGroup` resource to use in a request to
// insert a new NEG.
func newNetworkEndpointGroup(name string, projectID string, network string, service types.NamespacedName) *computepb.NetworkEndpointGroup {
	return &computepb.NetworkEndpointGroup{
		Annotations: map[string]string{
			"created-by":  "k8s-hybrid-neg-controller",
			"k8s-service": service.String(),
		},
		Description:         proto.String("Kubernetes Service"),
		Name:                proto.String(name),
		Network:             proto.String(fmt.Sprintf("https://www.googleapis.com/compute/v1/projects/%s/global/networks/%s", projectID, network)),
		NetworkEndpointType: proto.String(negTypeHybrid),
	}
}

// isAlreadyExists reports whether err is the result of the
// server replying with http.StatusConflict because the
// resource being created already exists.
func isAlreadyExists(err error) bool {
	if err == nil {
		return false
	}
	var apiErr *googleapi.Error
	ok := errors.As(err, &apiErr)
	return ok && apiErr.Code == http.StatusConflict && apiErr.Errors[0].Reason == "alreadyExists"
}
