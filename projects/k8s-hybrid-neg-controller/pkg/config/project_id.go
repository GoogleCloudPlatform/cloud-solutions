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
	"context"
	"fmt"

	"cloud.google.com/go/compute/metadata"
	"github.com/go-logr/logr"
)

const (
	projectIDFlagName = "project-id"
)

var projectIDFlag string

func init() {
	commandLine.StringVar(&projectIDFlag,
		projectIDFlagName,
		"",
		"The project ID of the Google Cloud project where the controller should create network Endpoint Groups (NEGs)."+
			" If unset, the controller looks up the project ID from the Compute Engine/Google Kubernetes Engine metadata server.")
}

// getProjectID first looks up the Google Cloud project ID from the provided `project-id` flag.
// If the project ID flag is not provided, this function queries the Compute Engine or
// Google Kubernetes Engine metadata server.
func getProjectID(ctx context.Context, logger logr.Logger) (string, error) {
	if projectIDFlag != "" {
		return projectIDFlag, nil
	}
	logger.V(4).Info("No Google Cloud project ID provided, attempting to look it up from the metadata server")
	projectID, err := metadata.ProjectIDWithContext(ctx)
	if err != nil {
		return "", fmt.Errorf("could not find the Google Cloud project ID from the Compute Engine or Google Kubernetes Engine metadata server: %w", err)
	}
	return projectID, nil
}
