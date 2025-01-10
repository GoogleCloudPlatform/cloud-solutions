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

package util

import (
	"os"
)

const (
	defaultNamespace = "hybrid-neg-system"
)

// GetNamespace returns the Kubernetes Namespace of the current Kubernetes Pod.
func GetNamespace() string {
	namespace, exists := os.LookupEnv("POD_NAMESPACE")
	if exists {
		return namespace
	}
	namespaceBytes, err := os.ReadFile("/var/run/secrets/kubernetes.io/serviceaccount/namespace")
	if err == nil && len(namespaceBytes) > 0 {
		return string(namespaceBytes)
	}
	return defaultNamespace
}
