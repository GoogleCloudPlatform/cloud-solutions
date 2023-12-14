// Copyright 2023 Google LLC
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

package helper

import (
	"context"
	"fmt"
	"log"
	"net/http"

	"golang.org/x/oauth2"
	"golang.org/x/oauth2/google"
	"k8s.io/client-go/rest"
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

func init() {
	if err := rest.RegisterAuthProviderPlugin(googleAuthPlugin, newGoogleAuthProvider); err != nil {
		log.Fatalf("Failed to register %s auth plugin: %v", googleAuthPlugin, err)
	}
	log.Println("Registered AuthProviderPlugin")
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

func newGoogleAuthProvider(addr string, config map[string]string, persister rest.AuthProviderConfigPersister) (rest.AuthProvider, error) {
	fmt.Println("addr", addr, "config:", config, "persister:", persister)
	ts, err := google.DefaultTokenSource(context.TODO(), googleScopes...)
	if err != nil {
		return nil, fmt.Errorf("failed to create google token source: %+v", err)
	}
	return &googleAuthProvider{tokenSource: ts}, nil
}
