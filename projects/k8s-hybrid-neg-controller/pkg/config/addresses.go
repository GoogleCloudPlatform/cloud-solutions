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

const (
	metricsAddrFlagName = "metrics-bind-address"
	probeAddrFlagName   = "health-probe-bind-address"
)

var (
	metricsAddrFlag string
	probeAddrFlag   string
)

func init() {
	commandLine.StringVar(&metricsAddrFlag, metricsAddrFlagName, ":8080", "The address that the metric endpoint binds to.")
	commandLine.StringVar(&probeAddrFlag, probeAddrFlagName, ":8081", "The address that the probe endpoint binds to.")
}
