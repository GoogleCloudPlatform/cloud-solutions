// Copyright 2024 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//	http://www.apache.org/licenses/LICENSE-2.0
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
	"sync"
	"time"

	compute "cloud.google.com/go/compute/apiv1"
	"cloud.google.com/go/compute/apiv1/computepb"
	"github.com/go-logr/logr"
	"github.com/gogo/protobuf/proto"
	"github.com/google/uuid"
	"golang.org/x/sync/errgroup"
	"golang.org/x/sync/semaphore"
	"google.golang.org/api/googleapi"
	"k8s.io/apimachinery/pkg/types"
)

const (
	// MaxSizeNetworkEndpointsAttachDetach is the max number of network endpoints that can
	// be attached or detached from a NEG in a single API call.
	// It is also the max number of network endpoints returned per page in API calls to list
	// existing endpoints of NEGs.
	MaxSizeNetworkEndpointsAttachDetach = 500
)

var (
	// zonalNEGLocks tracks locks that prevent multiple goroutines simultaneously updating a zonal NEG.
	zonalNEGLocks sync.Map

	errUnexpectedLockType = errors.New("unexpected type of lock")
)

// SyncEndpoints determines the diff between current network endpoints in zonal NEGs, and the new set of
// endpoints supplied. The function then attaches and detaches network endpoints so that the list
// of network endpoints for each zone matches the supplied set of endpoints.
func (c *Client) SyncEndpoints(ctx context.Context, logger logr.Logger, name string, endpointsByZone ZonalEndpoints, service types.NamespacedName) error {
	logger = logger.WithValues("GoogleCloudProjectID", c.projectID, "NetworkEndpointGroup", name)
	logger.Info("Syncing NEGs", "type", negTypeHybrid, "zones", c.zones)
	g, groupCtx := errgroup.WithContext(ctx)
	for _, zone := range c.zones {
		g.Go(func() error {
			return c.syncZonalNEG(groupCtx, logger, name, zone, endpointsByZone[zone], service)
		})
	}
	if err := g.Wait(); err != nil {
		return fmt.Errorf("problem syncing NEG name=%s for Kubernetes Service=%s: %w", name, service.String(), err)
	}
	logger.Info("Synced NEGs", "type", negTypeHybrid, "zones", c.zones)
	return nil
}

func (c *Client) syncZonalNEG(ctx context.Context, logger logr.Logger, name string, zone string, newEndpoints EndpointSet, service types.NamespacedName) error {
	logger = logger.WithValues("zone", zone)

	// Using semaphores instead of mutex because Acquire() takes a context argument, enabling deadlines on obtaining locks.
	// sync.Mutex could be used instead, but the code gets more complicated.
	lockName := fmt.Sprintf("%s/%s", name, zone)
	logger = logger.WithValues("lock", lockName)
	l, _ := zonalNEGLocks.LoadOrStore(lockName, semaphore.NewWeighted(1))
	sem, ok := l.(*semaphore.Weighted)
	if !ok {
		return fmt.Errorf("%w: expected *semaphore.Weighted, got %T for zonal NEG name=%s zone=%s", errUnexpectedLockType, l, name, zone)
	}
	lockAcquireCtx, cancelLockAquire := context.WithDeadline(ctx, time.Now().Add(c.timeouts.SyncZonalNEG))
	defer cancelLockAquire()
	if err := sem.Acquire(lockAcquireCtx, 1); err != nil {
		return fmt.Errorf("could not obtain lock for updating NEG name=%s zone=%s: %w", name, zone, err)
	}
	defer func() {
		sem.Release(1)
		logger.V(4).Info("Released lock for modifying zonal NEG")
	}()
	logger.V(4).Info("Obtained lock for modifying zonal NEG")

	syncCtx, cancelSync := context.WithDeadline(ctx, time.Now().Add(c.timeouts.SyncZonalNEG))
	defer cancelSync()
	logger.V(6).Info("Listing endpoints")
	existingEndpoints, err := c.getEndpoints(syncCtx, name, zone)
	if err != nil && !isNotFound(err) {
		return fmt.Errorf("problem listing network endpoints of NEG with projectID=%s name=%s zone=%s: %w", c.projectID, name, zone, err)
	}
	if isNotFound(err) {
		logger.Error(err, "Zonal NEG not found, the initial creation may have failed, trying to create again.")
		neg := newNetworkEndpointGroup(name, c.projectID, c.network, service)
		if createErr := c.createZonalNEG(syncCtx, logger, zone, neg); createErr != nil {
			return fmt.Errorf("problem creating zonal NEG during endpoint sync name=%s zone=%s: %w", name, zone, createErr)
		}
	}
	attach, detach := diffEndpoints(existingEndpoints, newEndpoints)
	logger.V(4).Info("Network endpoint diff sizes", "attachSize", len(attach), "detachSize", len(detach))
	return c.attachDetachEndpoints(syncCtx, logger, name, zone, attach, detach)
}

// getEndpoints returns the current endpoints of the NEG identified by the provided name and zone.
// Pagination logic based on example from https://github.com/GoogleCloudPlatform/golang-samples/blob/main/compute/list_all_instances.go
func (c *Client) getEndpoints(ctx context.Context, name string, zone string) (EndpointSet, error) {
	endpoints := EndpointSet{}
	request := &computepb.ListNetworkEndpointsNetworkEndpointGroupsRequest{
		NetworkEndpointGroup: name,
		NetworkEndpointGroupsListEndpointsRequestResource: &computepb.NetworkEndpointGroupsListEndpointsRequest{
			HealthStatus: proto.String(computepb.NetworkEndpointGroupsListEndpointsRequest_SKIP.String()),
		},
		Project:              c.projectID,
		ReturnPartialSuccess: proto.Bool(true),
		Zone:                 zone,
	}
	for endpoint, err := range c.client.ListNetworkEndpoints(ctx, request).All() {
		if err != nil {
			return nil, fmt.Errorf("problem iterating over network endpoints of NEG name=%s zone=%s: %w", name, zone, err)
		}
		if endpoint == nil {
			continue
		}
		// Instance is a pointer to an empty string in the response to ListNetworkEndpoints,
		// but must be nil in attach/detach requests for hybrid NEGs. So explicitly set it to `nil` here.
		// And set Fqdn to `nil` too, just in case.
		endpoint.NetworkEndpoint.Instance = nil
		endpoint.NetworkEndpoint.Fqdn = nil
		endpoints.Put(endpoint.NetworkEndpoint)
	}
	return endpoints, nil
}

// diffEndpoints returns a set of endpoints to be attached, and a set of endpoints to be
// detached from a NEG. The diff is determined by comparing the current state and the desired
// target state.
func diffEndpoints(previous EndpointSet, current EndpointSet) ([]*computepb.NetworkEndpoint, []*computepb.NetworkEndpoint) {
	var added []*computepb.NetworkEndpoint
	var removed []*computepb.NetworkEndpoint
	for endpointKey, endpoint := range previous {
		if _, exists := current[endpointKey]; !exists {
			removed = append(removed, endpoint)
		}
	}
	for endpointKey, endpoint := range current {
		if _, exists := previous[endpointKey]; !exists {
			added = append(added, endpoint)
		}
	}
	return added, removed
}

// attachDetachEndpoints syncs the endpoints of the zonal NEG and blocks until all operations
// return. The method returns an error if one or more of the attach/detach API requests fail.
// The reason for blocking until done is to ensure that the next EndpointSlice reconciliation
// request observes a consistent view of the endpoints in the NEGs.
func (c *Client) attachDetachEndpoints(syncCtx context.Context, logger logr.Logger, name string, zone string, attach []*computepb.NetworkEndpoint, detach []*computepb.NetworkEndpoint) error {
	logger.V(8).Info("Network endpoint diff endpoints", "attach", attach, "detach", detach)
	attachOps, err := c.attachEndpoints(syncCtx, logger, name, zone, attach)
	if err != nil {
		return fmt.Errorf("problem attaching endpoints to NEG of type=%s for projectID=%s name=%s zone=%s attach=%+v: %w", negTypeHybrid, c.projectID, name, zone, attach, err)
	}
	detachOps, err := c.detachEndpoints(syncCtx, logger, name, zone, detach)
	if err != nil {
		return fmt.Errorf("problem detaching endpoints from NEG of type=%s for projectID=%s name=%s zone=%s detach=%+v: %w", negTypeHybrid, c.projectID, name, zone, detach, err)
	}
	g, groupCtx := errgroup.WithContext(syncCtx)
	for _, op := range append(attachOps, detachOps...) {
		g.Go(func() error {
			return op.Wait(groupCtx)
		})
	}
	if err := g.Wait(); err != nil {
		return fmt.Errorf("problem while waiting for async attaching and detaching of endpoints for NEG name=%s zone=%s: %w", name, zone, err)
	}
	return nil
}

// attachEndpoints adds the provided endpoints to the NEG identified by the provided name and zone.
// The method returns a slice of handles to the async attach API requests.
func (c *Client) attachEndpoints(ctx context.Context, logger logr.Logger, name string, zone string, attach []*computepb.NetworkEndpoint) ([]*compute.Operation, error) {
	var ops []*compute.Operation
	// Requests to attach/detach network endpoints can have at most 500 endpoints.
	for i := 0; i < len(attach); i += MaxSizeNetworkEndpointsAttachDetach {
		var chunk []*computepb.NetworkEndpoint
		if i > len(attach)-MaxSizeNetworkEndpointsAttachDetach {
			chunk = attach[i:]
		} else {
			chunk = attach[i : i+MaxSizeNetworkEndpointsAttachDetach]
		}
		requestID := uuid.New().String()
		logger = logger.WithValues("chunkSize", len(chunk), "requestID", requestID)
		logger.V(6).Info("Sending API request to attach endpoints to zonal NEG")
		operation, err := c.client.AttachNetworkEndpoints(ctx, &computepb.AttachNetworkEndpointsNetworkEndpointGroupRequest{
			NetworkEndpointGroup: name,
			NetworkEndpointGroupsAttachEndpointsRequestResource: &computepb.NetworkEndpointGroupsAttachEndpointsRequest{
				NetworkEndpoints: chunk,
			},
			Project:   c.projectID,
			RequestId: proto.String(requestID),
			Zone:      zone,
		})
		if err != nil && !googleapi.IsNotModified(err) {
			return nil, err
		}
		ops = append(ops, operation)
	}
	return ops, nil
}

// detachEndpoints removes the provided endpoints from the NEG identified by the provided name and
// zone. The method returns a slice of handles to the async attach API requests.
func (c *Client) detachEndpoints(ctx context.Context, logger logr.Logger, name string, zone string, detach []*computepb.NetworkEndpoint) ([]*compute.Operation, error) {
	var ops []*compute.Operation
	// Requests to attach/detach network endpoints can have at most 500 endpoints.
	for i := 0; i < len(detach); i += MaxSizeNetworkEndpointsAttachDetach {
		var chunk []*computepb.NetworkEndpoint
		if i > len(detach)-MaxSizeNetworkEndpointsAttachDetach {
			chunk = detach[i:]
		} else {
			chunk = detach[i : i+MaxSizeNetworkEndpointsAttachDetach]
		}
		requestID := uuid.New().String()
		logger = logger.WithValues("chunkSize", len(chunk), "requestID", requestID)
		logger.V(6).Info("Sending API request to detach endpoints from zonal NEG")
		operation, err := c.client.DetachNetworkEndpoints(ctx, &computepb.DetachNetworkEndpointsNetworkEndpointGroupRequest{
			NetworkEndpointGroup: name,
			NetworkEndpointGroupsDetachEndpointsRequestResource: &computepb.NetworkEndpointGroupsDetachEndpointsRequest{
				NetworkEndpoints: chunk,
			},
			Project:   c.projectID,
			RequestId: proto.String(requestID),
			Zone:      zone,
		})
		if err != nil && !googleapi.IsNotModified(err) {
			return nil, err
		}
		ops = append(ops, operation)
	}
	return ops, nil
}

// isNotFound returns true if the provided error is a `googleapi.Error` with status code
// 404 Not Found.
func isNotFound(err error) bool {
	if err == nil {
		return false
	}
	var ae *googleapi.Error
	ok := errors.As(err, &ae)
	return ok && ae.Code == http.StatusNotFound
}

// endpointToString returns a string representation of the IPv4 address and port number of the
// provided NetworkEndpoint.
// Hybrid NEGs currently use only the IPv4 address and port number to identify endpoints;
// instance name is not used, and IPv6 addresses are not currently supported.
func endpointToString(endpoint *computepb.NetworkEndpoint) string {
	if endpoint == nil {
		return "nil"
	}
	return fmt.Sprintf("%s/%d", endpoint.GetIpAddress(), endpoint.GetPort())
}
