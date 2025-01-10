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
	"time"

	"cloud.google.com/go/compute/apiv1/computepb"
	"github.com/go-logr/logr"
	"golang.org/x/sync/errgroup"
	"k8s.io/apimachinery/pkg/types"
)

// DeleteNEGs removes endpoints from existing zonal NEGs, and then attempts to delete the NEGs.
// Deleting NEGs will fail if one or more BackendServices reference a zonal NEG.
func (c *Client) DeleteNEGs(ctx context.Context, logger logr.Logger, name string, service types.NamespacedName) error {
	logger = logger.WithValues("NetworkEndpointGroup", name)
	emptyEndpointsByZoneMap := make(ZonalEndpoints, len(c.zones))
	for _, zone := range c.zones {
		emptyEndpointsByZoneMap[zone] = EndpointSet{}
	}
	logger.Info("Deleting network endpoints from NEGs")
	if err := c.SyncEndpoints(ctx, logger, name, emptyEndpointsByZoneMap, service); err != nil {
		return fmt.Errorf("problem removing endpoints from zonal NEG: %w", err)
	}
	g, groupCtx := errgroup.WithContext(ctx)
	for _, zone := range c.zones {
		g.Go(func() error {
			logger.Info("Deleting NEG async", "projectID", c.projectID, "zone", zone)
			ctxWithDeadline, cancel := context.WithDeadline(groupCtx, time.Now().Add(c.timeouts.DeleteZonalNEG))
			defer cancel()
			_, err := c.client.Delete(ctxWithDeadline, &computepb.DeleteNetworkEndpointGroupRequest{
				NetworkEndpointGroup: name,
				Project:              c.projectID,
				Zone:                 zone,
			})
			return err
		})
	}
	return g.Wait()
}
