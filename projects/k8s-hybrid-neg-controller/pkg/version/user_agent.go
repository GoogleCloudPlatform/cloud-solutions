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

package version

import (
	"fmt"
)

const (
	// userAgentFormatString is used with both the k8s and Compute Engine clients.
	// Formats to cloud-solutions/k8s-hybrid-neg-controller-v999.
	userAgentFormatString = "cloud-solutions/k8s-hybrid-neg-controller-%s"
)

// UserAgent returns the value of the `User-Agent` header for Google API requests.
func UserAgent() string {
	return fmt.Sprintf(userAgentFormatString, Version)
}
