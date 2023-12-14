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
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"net/http"
	"os"

	"sigs.k8s.io/controller-runtime/pkg/log"

	"golang.org/x/oauth2"
	"golang.org/x/oauth2/google"
	"google.golang.org/api/impersonate"
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
		log.Log.Error(err, "Failed to register auth plugin")
	}
	log.Log.Info("Registered AuthProviderPlugin")
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
	fmt.Println("addr:", addr, "config:", config, "persister:", persister)
	ts, err := google.DefaultTokenSource(context.TODO(), googleScopes...)
	if err != nil {
		return nil, fmt.Errorf("failed to create google token source: %+v", err)
	}
	return &googleAuthProvider{tokenSource: ts}, nil
}

// RetrieveGoogleTokenSource retrieves a impersonated CredentialsTokenSource,
// delegated service account must have the role - roles/iam.serviceAccountTokenCreator.
func RetrieveGoogleTokenSource(ctx context.Context, user string) (oauth2.TokenSource, error) {
	// https://pkg.go.dev/google.golang.org/api/impersonate#example-CredentialsTokenSource-ServiceAccount
	// Base credentials sourced from ADC or provided client options.
	l := log.FromContext(ctx).WithName("RetrieveGoogleTokenSource")
	target := os.Getenv("TARGET_PRINCIPAL")
	l.Info("Retrieving Google Token Source", "user", user, "target", target)
	ts, err := impersonate.CredentialsTokenSource(ctx, impersonate.CredentialsConfig{
		TargetPrincipal: target,
		Scopes:          []string{"https://www.googleapis.com/auth/cloud-platform"},
		// Subject:      user, // That's only for admin user to impersonate sa
	})
	if err != nil {
		return nil, fmt.Errorf("failed to create impersonated token source: %+v", err)
	}

	return ts, err
}

// ValidateTokenWithAPI validates the token with Google API and returns the subject of the token.
func ValidateTokenWithAPI(ctx context.Context, token string) (*map[string]string, error) {
	l := log.FromContext(ctx).WithName("ValidateTokenWithAPI")
	google_token_endpoint := "https://oauth2.googleapis.com/tokeninfo"

	req, err := http.NewRequest("GET", google_token_endpoint, nil)
	if err != nil {
		fmt.Println(err)
		return nil, nil
	}
	req.Header.Add("Content-Type", "application/json")
	req.Header.Add("Authorization", "Bearer "+token)

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("invalidate token: %w", err)
	}
	defer resp.Body.Close()
	var jwt map[string]string
	err = json.NewDecoder(resp.Body).Decode(&jwt)
	if err != nil {
		return nil, fmt.Errorf("invalidate token: %w", err)
	}
	l.Info("Validating token with Google API", "jwt", jwt)
	if _, ok := jwt["error"]; ok {
		return nil, fmt.Errorf("invalidate token: Invalid Value")
	}
	return &jwt, nil
}

func EncryptData(data string) string {
	h := sha256.New()
	h.Write([]byte(data))
	return fmt.Sprintf("%x", h.Sum(nil))
}
