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
	"github.com/go-logr/logr"
)

const (
	defaultNetworkName = "default"
	networkFlagName    = "network"
)

var networkFlag string

func init() {
	commandLine.StringVar(&networkFlag,
		networkFlagName,
		defaultNetworkName,
		"The global Compute Engine VPC network to use when creating network Endpoint Groups (NEGs).")
}

func getNetwork(logger logr.Logger) string {
	if len(networkFlag) == 0 {
		logger.V(2).Info("Empty Compute Engine VPC network name provided, using default value", "network", defaultNetworkName)
		return defaultNetworkName
	}
	return networkFlag
}
