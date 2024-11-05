// Copyright 2023 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package kubeapi

import (
	"context"
	"encoding/base64"
	"fmt"
	"log"
	"net/http"

	"cloud.google.com/go/container/apiv1/containerpb"
	"golang.org/x/oauth2"
	"golang.org/x/oauth2/google"
	"k8s.io/client-go/rest"
	"k8s.io/client-go/tools/clientcmd"
	"k8s.io/client-go/tools/clientcmd/api"
)

var (
	googleScopes = []string{
		"https://www.googleapis.com/auth/cloud-platform",
		"https://www.googleapis.com/auth/userinfo.email",
	}
)

const (
	googleAuthPlugin = "google" // so that this is different than "gcp" that's already in client-go tree.
)

type K8sAuthConfigs struct {
	config *api.Config
}

func init() {
	if err := rest.RegisterAuthProviderPlugin(googleAuthPlugin, newGoogleAuthProvider); err != nil {
		log.Fatalf("Failed to register %s auth plugin: %v", googleAuthPlugin, err)
	}
}

var _ rest.AuthProvider = &googleAuthProvider{}

type googleAuthProvider struct {
	tokenSource oauth2.TokenSource
}

func (g *googleAuthProvider) WrapTransport(rt http.RoundTripper) http.RoundTripper {
	return &oauth2.Transport{
		Base:   rt,
		Source: g.tokenSource,
	}
}
func (g *googleAuthProvider) Login() error { return nil }

func newGoogleAuthProvider(_ string, _ map[string]string, _ rest.AuthProviderConfigPersister) (rest.AuthProvider, error) {
	ts, err := google.DefaultTokenSource(context.TODO(), googleScopes...)
	if err != nil {
		return nil, fmt.Errorf("failed to create google token source: %+v", err)
	}
	return &googleAuthProvider{tokenSource: ts}, nil
}

// GetK8sConfig returns k8s config can be used to initialize client-go
func (c *K8sAuthConfigs) GetK8sConfig(clusterName string) (*rest.Config, error) {
	cfg, err := clientcmd.NewNonInteractiveClientConfig(*c.config, clusterName, &clientcmd.ConfigOverrides{
		CurrentContext: clusterName,
	}, nil).ClientConfig()
	if err != nil {
		return nil, fmt.Errorf("failed to create Kubernetes configuration cluster=%s: %w", clusterName, err)
	}
	return cfg, nil
}

// GenerateK8sClustersConfig generates configs for K8s authentication from clusters data fetched from Google Cloud
func GenerateK8sClustersConfig(pbClusters []*containerpb.Cluster, projectID string) (*K8sAuthConfigs, error) {
	config := &api.Config{
		APIVersion: "v1",
		Kind:       "Config",
		Clusters:   map[string]*api.Cluster{},  // Clusters is a map of referencable names to cluster configs
		AuthInfos:  map[string]*api.AuthInfo{}, // AuthInfos is a map of referencable names to user configs
		Contexts:   map[string]*api.Context{},  // Contexts is a map of referencable names to context configs
	}

	for _, pbCluster := range pbClusters {
		name := fmt.Sprintf("gke_%s_%s_%s", projectID, pbCluster.Location, pbCluster.Name)
		cert, err := base64.StdEncoding.DecodeString(pbCluster.MasterAuth.ClusterCaCertificate)
		if err != nil {
			return nil, fmt.Errorf("invalid certificate cluster=%s cert=%s: %w", name, pbCluster.MasterAuth.ClusterCaCertificate, err)
		}
		config.Clusters[name] = &api.Cluster{
			CertificateAuthorityData: cert,
			Server:                   "https://" + pbCluster.Endpoint,
		}
		config.Contexts[name] = &api.Context{
			Cluster:  name,
			AuthInfo: name,
		}
		config.AuthInfos[name] = &api.AuthInfo{
			AuthProvider: &api.AuthProviderConfig{
				Name: googleAuthPlugin,
			},
		}
	}
	return &K8sAuthConfigs{config: config}, nil
}
