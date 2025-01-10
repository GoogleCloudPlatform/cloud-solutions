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
	"errors"
	"time"

	"github.com/go-logr/logr"
)

const (
	DefaultNEGOperationTimeoutSeconds = 300

	timeoutCreateZonalNEGSecondsFlagName = "timeout-create-zonal-neg-seconds"
	timeoutDeleteZonalNEGSecondsFlagName = "timeout-delete-zonal-neg-seconds"
	timeoutSyncZonalNEGSecondsFlagName   = "timeout-sync-zonal-neg-seconds"

	timeoutSyncServiceEndpointsSecondsFlagName = "timeout-sync-service-endpoints-seconds"
)

var (
	timeoutCreateZonalNEGSecondsFlag int64
	timeoutDeleteZonalNEGSecondsFlag int64
	timeoutSyncZonalNEGSecondsFlag   int64

	timeoutSyncServiceEndpointsSecondsFlag int64

	errInvalidTimeout = errors.New("invalid timeout, must be greater than zero")
)

type Timeouts struct {
	CreateZonalNEG time.Duration
	DeleteZonalNEG time.Duration
	SyncZonalNEG   time.Duration

	SyncServiceEndpoints time.Duration
}

func init() {
	commandLine.Int64Var(&timeoutCreateZonalNEGSecondsFlag,
		timeoutCreateZonalNEGSecondsFlagName,
		DefaultNEGOperationTimeoutSeconds,
		"Timeout in seconds for creating a zonal network endpoint group (NEG).")
	commandLine.Int64Var(&timeoutDeleteZonalNEGSecondsFlag,
		timeoutDeleteZonalNEGSecondsFlagName,
		DefaultNEGOperationTimeoutSeconds,
		"Timeout in seconds for deleting a zonal network endpoint group (NEG).")
	commandLine.Int64Var(&timeoutSyncZonalNEGSecondsFlag,
		timeoutSyncZonalNEGSecondsFlagName,
		DefaultNEGOperationTimeoutSeconds,
		"Timeout in seconds for syncing endpoints of a zonal network endpoint group (NEG).")

	commandLine.Int64Var(&timeoutSyncServiceEndpointsSecondsFlag,
		timeoutSyncServiceEndpointsSecondsFlagName,
		DefaultNEGOperationTimeoutSeconds,
		"Timeout in seconds for synchronizing endpoints of a Kubernetes Service with all of its zonal network endpoint groups (NEGs).")
}

func getTimeouts(logger logr.Logger) Timeouts {
	if timeoutCreateZonalNEGSecondsFlag <= 0 {
		logger.Error(errInvalidTimeout, "Using default value for -"+timeoutCreateZonalNEGSecondsFlagName, "timeout", DefaultNEGOperationTimeoutSeconds)
		timeoutCreateZonalNEGSecondsFlag = DefaultNEGOperationTimeoutSeconds
	}
	if timeoutDeleteZonalNEGSecondsFlag <= 0 {
		logger.Error(errInvalidTimeout, "Using default value for -"+timeoutDeleteZonalNEGSecondsFlagName, "timeout", DefaultNEGOperationTimeoutSeconds)
		timeoutDeleteZonalNEGSecondsFlag = DefaultNEGOperationTimeoutSeconds
	}
	if timeoutSyncZonalNEGSecondsFlag <= 0 {
		logger.Error(errInvalidTimeout, "Using default value for -"+timeoutSyncZonalNEGSecondsFlagName, "timeout", DefaultNEGOperationTimeoutSeconds)
		timeoutSyncZonalNEGSecondsFlag = DefaultNEGOperationTimeoutSeconds
	}

	if timeoutSyncServiceEndpointsSecondsFlag <= 0 {
		logger.Error(errInvalidTimeout, "Using default value for -"+timeoutSyncServiceEndpointsSecondsFlagName, "timeout", DefaultNEGOperationTimeoutSeconds)
		timeoutSyncServiceEndpointsSecondsFlag = DefaultNEGOperationTimeoutSeconds
	}

	return Timeouts{
		CreateZonalNEG:       time.Duration(timeoutCreateZonalNEGSecondsFlag) * time.Second,
		DeleteZonalNEG:       time.Duration(timeoutDeleteZonalNEGSecondsFlag) * time.Second,
		SyncZonalNEG:         time.Duration(timeoutSyncZonalNEGSecondsFlag) * time.Second,
		SyncServiceEndpoints: time.Duration(timeoutSyncServiceEndpointsSecondsFlag) * time.Second,
	}
}
