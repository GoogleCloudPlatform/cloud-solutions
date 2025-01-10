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

	"github.com/go-logr/logr"
	"github.com/google/uuid"
	v1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/types"
	"sigs.k8s.io/controller-runtime/pkg/client"
)

const (
	clusterIDFlagName = "cluster-id"

	// Kubernetes cluster IDs will be trimmed to this length.
	maxLengthClusterID = 8
)

var clusterIDFlag string

func init() {
	commandLine.StringVar(&clusterIDFlag, clusterIDFlagName, "", "The Kubernetes cluster ID to use when dynamically creating names for network endpoint groups (NEGs)."+
		" If unspecified, the controller manager will look up a value from the environment.")
}

// getClusterID returns a string of max length 8 characters.
func getClusterID(ctx context.Context, logger logr.Logger, k8sClient client.Client) string {
	clusterID := lookupClusterID(ctx, logger, k8sClient)
	if len(clusterID) > maxLengthClusterID {
		clusterID = clusterID[:maxLengthClusterID]
	}
	return clusterID
}

// lookupClusterID is used if the `cluster-id` flag is not supplied.
func lookupClusterID(ctx context.Context, logger logr.Logger, k8sClient client.Client) string {
	// First, see if a flag value was set:
	if clusterIDFlag != "" {
		return clusterIDFlag
	}
	// Second, try to get the ingress uid of a GKE cluster:
	configMap := &v1.ConfigMap{}
	if err := k8sClient.Get(ctx, types.NamespacedName{
		Namespace: "kube-system",
		Name:      "ingress-uid",
	}, configMap); err != nil {
		logger.V(4).Info("Could not get the ingress-uid ConfigMap from the kube-system namespace."+
			" This is expected to fail on non-Google Kubernetes Engine clusters", "error", err.Error())
	}
	if configMap.Data != nil && len(configMap.Data["uid"]) > 0 {
		logger.V(4).Info("Found cluster ID from kube-system/ingress-uid ConfigMap")
		return configMap.Data["uid"]
	}
	// Third, try to get the UID of the kubernetes Service in the default namespace:
	service := v1.Service{}
	if err := k8sClient.Get(ctx, types.NamespacedName{
		Namespace: "default",
		Name:      "kubernetes",
	}, &service); err != nil {
		logger.Error(err, "Could not get the default/kubernetes Service.")
	}
	clusterID := string(service.GetUID())
	if len(clusterID) > 0 {
		logger.V(4).Info("Found cluster ID from the default/kubernetes Service", "clusterID", clusterID)
		return clusterID
	}
	// Finally, if all else fails, generate a value:
	logger.V(1).Info("No cluster ID available, using generated value")
	return fmt.Sprintf("%0x", uuid.New())[:8]
}
