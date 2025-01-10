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

package manager

import (
	"fmt"

	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/client-go/kubernetes/scheme"
	controllerruntime "sigs.k8s.io/controller-runtime"
	clientconfig "sigs.k8s.io/controller-runtime/pkg/client/config"
	"sigs.k8s.io/controller-runtime/pkg/healthz"
	"sigs.k8s.io/controller-runtime/pkg/manager"
	"sigs.k8s.io/controller-runtime/pkg/metrics/server"

	"github.com/googlecloudplatform/k8s-hybrid-neg-controller/pkg/config"
	"github.com/googlecloudplatform/k8s-hybrid-neg-controller/pkg/version"
)

const (
	LeaderElectionID = "hybrid-neg-controller-manager"
)

// NewManager creates a controller manager.
func NewManager(cfg *config.ManagerConfig) (manager.Manager, error) {
	k8sClientConfig, err := clientconfig.GetConfigWithContext(cfg.Kubecontext)
	if err != nil {
		return nil, fmt.Errorf("could not initialize Kubernetes client config: %w", err)
	}
	k8sClientConfig.UserAgent = version.UserAgent()
	k8sClientScheme := runtime.NewScheme()
	if err := scheme.AddToScheme(k8sClientScheme); err != nil {
		return nil, fmt.Errorf("could not add Kubernetes types to new pluggable scheme: %w", err)
	}
	mgr, err := controllerruntime.NewManager(k8sClientConfig, manager.Options{
		HealthProbeBindAddress:  cfg.ProbeAddr,
		LeaderElection:          true,
		LeaderElectionID:        LeaderElectionID,
		LeaderElectionNamespace: cfg.LeaderElectionNamespace,
		Metrics: server.Options{
			BindAddress: cfg.MetricsAddr,
		},
		Scheme: k8sClientScheme,
	})
	if err != nil {
		return nil, fmt.Errorf("could not create controller manager: %w", err)
	}
	if err := mgr.AddHealthzCheck("healthz", healthz.Ping); err != nil {
		return nil, fmt.Errorf("unable to set up health check: %w", err)
	}
	if err := mgr.AddReadyzCheck("readyz", healthz.Ping); err != nil {
		return nil, fmt.Errorf("unable to set up readiness check: %w", err)
	}
	return mgr, nil
}
