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
	DefaultReconcileRequeueDelaySeconds = 10

	reconcileRequeueDelaySecondsFlagName = "reconcile-requeue-delay-seconds"
)

var (
	reconcileRequeueDelaySecondsFlag int64

	errInvalidReconcileRequeueDelay = errors.New("invalid reconcile requeue delay, must be >= 0")
)

func init() {
	commandLine.Int64Var(&reconcileRequeueDelaySecondsFlag, reconcileRequeueDelaySecondsFlagName, DefaultReconcileRequeueDelaySeconds, "The requeue delay for the controllers' reconcile loop on non-terminal errors.")
}

func getRequeueAfter(logger logr.Logger) time.Duration {
	if reconcileRequeueDelaySecondsFlag < 0 {
		logger.Error(errInvalidReconcileRequeueDelay, "Using default value", "reconcileRequeueDelaySeconds", DefaultReconcileRequeueDelaySeconds)
		reconcileRequeueDelaySecondsFlag = DefaultReconcileRequeueDelaySeconds
	}
	return time.Duration(reconcileRequeueDelaySecondsFlag) * time.Second
}
