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

package config

import (
	"context"
	"fmt"
	"time"

	compute "cloud.google.com/go/compute/apiv1"
	"github.com/go-logr/logr"
	"google.golang.org/api/option"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/client-go/kubernetes/scheme"
	"sigs.k8s.io/controller-runtime/pkg/client"
	clientconfig "sigs.k8s.io/controller-runtime/pkg/client/config"

	"github.com/googlecloudplatform/k8s-hybrid-neg-controller/pkg/util"
	"github.com/googlecloudplatform/k8s-hybrid-neg-controller/pkg/version"
)

// ManagerConfig holds configuration values for the controller manager.
type ManagerConfig struct {
	Kubecontext             string
	LeaderElectionNamespace string
	MetricsAddr             string
	ProbeAddr               string
}

// ReconcilerConfig holds configuration values for the reconcilers.
type ReconcilerConfig struct {
	ClusterID               string
	DefaultNEGZone          string
	ExcludeSystemNamespaces bool
	Network                 string
	ProjectID               string
	RequeueAfter            time.Duration
	Timeouts                Timeouts
	ZoneMapping             map[string]string
	Zones                   []string
}

// Client looks up parameters to configure the controller.
type Client struct {
	K8sClient         client.Client
	RegionZonesClient *compute.RegionZonesClient
}

// NewClient returns a client for looking up parameters to configure the controller.
func NewClient(ctx context.Context) (*Client, error) {
	regionZonesClient, err := compute.NewRegionZonesRESTClient(ctx, option.WithUserAgent(version.UserAgent()))
	if err != nil {
		return nil, fmt.Errorf("problem creating Compute Engine API client: %w", err)
	}
	k8sClient, err := createK8sClient(kubecontext)
	if err != nil {
		return nil, fmt.Errorf("problem creating Kubernetes client: %w", err)
	}
	return &Client{
		K8sClient:         k8sClient,
		RegionZonesClient: regionZonesClient,
	}, nil
}

// GetManagerConfig returns configuration values for the controller manager.
func (c *Client) GetManagerConfig() *ManagerConfig {
	return &ManagerConfig{
		MetricsAddr:             metricsAddrFlag,
		LeaderElectionNamespace: util.GetNamespace(),
		ProbeAddr:               probeAddrFlag,
	}
}

// GetReconcilerConfig returns configuration values for the reconcilers.
func (c *Client) GetReconcilerConfig(ctx context.Context, logger logr.Logger) (*ReconcilerConfig, error) {
	projectID, err := getProjectID(ctx, logger)
	if err != nil {
		return nil, err
	}
	negZones, err := getNEGZones(ctx, logger, projectID, c.RegionZonesClient)
	if err != nil {
		return nil, err
	}
	defaultNEGZone, err := getDefaultNEGZone(logger, negZones)
	if err != nil {
		return nil, err
	}
	zoneMapping, err := getZoneMapping(logger, negZones)
	if err != nil {
		return nil, err
	}
	clusterID := getClusterID(ctx, logger, c.K8sClient)
	network := getNetwork(logger)
	requeueAfter := getRequeueAfter(logger)
	timeouts := getTimeouts(logger)
	return &ReconcilerConfig{
		ClusterID:               clusterID,
		DefaultNEGZone:          defaultNEGZone,
		ExcludeSystemNamespaces: excludeSystemNamespaces,
		Network:                 network,
		ProjectID:               projectID,
		RequeueAfter:            requeueAfter,
		Timeouts:                timeouts,
		ZoneMapping:             zoneMapping,
		Zones:                   negZones,
	}, nil
}

// createK8sClient returns a Kubernetes client that the controller uses for looking up the cluster ID.
func createK8sClient(kubecontext string) (client.Client, error) {
	k8sClientConfig, err := clientconfig.GetConfigWithContext(kubecontext)
	if err != nil {
		return nil, err
	}
	k8sClientConfig.UserAgent = version.UserAgent()
	k8sClientScheme := runtime.NewScheme()
	if err := scheme.AddToScheme(k8sClientScheme); err != nil {
		return nil, fmt.Errorf("could not add Kubernetes types to new pluggable scheme: %w", err)
	}
	return client.New(k8sClientConfig, client.Options{
		Scheme: k8sClientScheme,
	})
}
