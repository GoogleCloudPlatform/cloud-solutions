// Copyright 2024 Google LLC
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

package auth

import (
	"context"
	"fmt"
	"net/http"
	"strings"

	"github.com/go-logr/logr"
	"golang.org/x/oauth2"
	"golang.org/x/oauth2/google"
	"k8s.io/client-go/rest"
)

var defaultGoogleScopes = []string{
	"https://www.googleapis.com/auth/cloud-platform",
	"https://www.googleapis.com/auth/userinfo.email",
}

const (
	googleAuthPluginName = "google"
	googleScopesKey      = "scopes"
)

func RegisterGoogle(ctx context.Context, logger logr.Logger) {
	logger.Info("Registering Kubernetes client auth provider", "authProvider", googleAuthPluginName)
	if err := rest.RegisterAuthProviderPlugin(googleAuthPluginName, func(_ string, config map[string]string, _ rest.AuthProviderConfigPersister) (rest.AuthProvider, error) {
		scopes := parseScopes(config)
		ts, err := google.DefaultTokenSource(ctx, scopes...)
		if err != nil {
			return nil, fmt.Errorf("failed to create Google token source: %w", err)
		}
		return &googleAuthProvider{tokenSource: ts}, nil
	}); err != nil {
		logger.Error(err, "Could not register Kubernetes client auth provider")
	}
}

func parseScopes(config map[string]string) []string {
	scopes, exist := config[googleScopesKey]
	if !exist {
		return defaultGoogleScopes
	}
	if scopes == "" {
		return []string{}
	}
	return strings.Split(scopes, ",")
}

var _ rest.AuthProvider = &googleAuthProvider{}

type googleAuthProvider struct {
	tokenSource oauth2.TokenSource
}

// WrapTransport returns a modified RoundTripper that attaches Authorization headers to requests.
// The auth provider's token source is used to provide tokens for the Authorization header.
func (g *googleAuthProvider) WrapTransport(rt http.RoundTripper) http.RoundTripper {
	return &oauth2.Transport{
		Base:   rt,
		Source: g.tokenSource,
	}
}

func (g *googleAuthProvider) Login() error { return nil }
