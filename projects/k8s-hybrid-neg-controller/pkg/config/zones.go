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
	"errors"
	"fmt"
	"regexp"
	"slices"
	"strings"
	"time"

	compute "cloud.google.com/go/compute/apiv1"
	"cloud.google.com/go/compute/apiv1/computepb"
	"cloud.google.com/go/compute/metadata"
	"github.com/go-logr/logr"
	"github.com/gogo/protobuf/proto"
)

const (
	// TimeoutListRegionZones is the duration allocated when dynamically looking up the zones of a
	// Compute Engine region. This is only used when running on GKE, and only if the `neg-zones`
	// flag is not specified.
	TimeoutListRegionZones = 600 * time.Second

	defaultNEGZoneFlagName = "default-neg-zone"
	negZonesFlagName       = "neg-zones"
	zoneMappingFlagName    = "zone-mapping"
)

var (
	negZonesFlag       string
	defaultNEGZoneFlag string
	zoneMappingFlag    string

	computeEngineZoneRegexp = regexp.MustCompile("[a-z]{2,}-[a-z]{4,}[0-9]{1,2}-[a-z]")

	errAtLeastOneZoneRequired   = errors.New("at least one Compute Engine zone must be provided")
	errDefaultNEGZoneNotInZones = errors.New("default NEG zone not found in NEG zones list")
	errInvalidNEGZone           = errors.New("invalid NEG zone, ensure that the values of the '" + negZonesFlagName + "' flag match zones from 'gcloud compute zones list'")
	errInvalidNEGZoneInMapping  = errors.New("invalid NEG zone mapping, ensure that the target values of the '" + zoneMappingFlagName + "' flag match zones from the '" + negZonesFlagName + "' flag")
	errMissingNEGZones          = errors.New("missing NEG zones, add the '" + negZonesFlagName + "' flag with values from 'gcloud compute zones list'")
	errZoneMappingsRequired     = errors.New("zone mappings must be provided when not running on Google Cloud")
)

func init() {
	commandLine.StringVar(&negZonesFlag,
		negZonesFlagName,
		"",
		"Compute Engine zones used by this controller to create network Endpoint Groups (NEGs)."+
			" If omitted, the controller dynamically discovers zones by watching the Kubernetes cluster Nodes and mapping the values of the 'topology.kubernetes.io/zone' label to Compute Engine zones,"+
			" using the mappings defined by the '"+zoneMappingFlagName+"' flag.")
	commandLine.StringVar(&defaultNEGZoneFlag,
		defaultNEGZoneFlagName,
		"",
		"The default Compute Engine zone to use when creating network Endpoint Groups (NEGs) if no mapping exists for the zone of an endpoint."+
			" If undefined, the controller selects one of the zones provided to '"+negZonesFlagName+"' as the default.")
	commandLine.StringVar(&zoneMappingFlag,
		zoneMappingFlagName,
		"",
		"List of comma-separated 'key=value' pairs, where the key is a zone used by a node in the Kubernetes cluster,"+
			" and the value is the Compute Engine zone to use when creating a hybrid NEG for endpoints in that zone."+
			" To see the zones currently used by your k8s cluster Nodes, run 'kubectl get nodes --output=jsonpath=\"{.items[*].metadata.labels.topology\\.kubernetes\\.io/zone}\"'."+
			" To see a list of Compute Engine zones, run 'gcloud compute zones list'.")
}

// getNEGZones returns a sorted slice of Compute Engine zones.
// The zones are provided using the `-neg-zones` flag.
// If the `-neg-zones` flag is not specified, the target values of the `-zone-mapping` flag are used.
// If the `-zone-mapping` flag also is not specified, and if the controller manager is running on
// Google Cloud, then the zones are looked up from the Compute Engine or Google Kubernetes Engine
// metadata server.
func getNEGZones(ctx context.Context, logger logr.Logger, projectID string, regionZonesClient *compute.RegionZonesClient) ([]string, error) {
	var zones []string
	var err error
	switch {
	case len(negZonesFlag) > 0:
		// Use the values from the supplied `neg-zones` flag.
		zones = strings.Split(negZonesFlag, ",")
	case len(zoneMappingFlag) > 0:
		// Use the target values from the `zone-mapping` flag.
		zoneMapping := parseZoneMappingFlag()
		for _, negZone := range zoneMapping {
			zones = append(zones, negZone)
		}
	case metadata.OnGCE():
		// Look up zones from the Compute Engine or Google Kubernetes Engine metadata server, and
		// using the Compute Engine API.
		// 1. Look up the zone of the current Kubernetes Node from the metadata server.
		// 2. Determine the region of that zone.
		// 3. Use the Compute Engine API to list the zones of that region.
		logger.V(4).Info("No NEG zones provided, attempting to fetch zones from the metadata server")
		zones, err = lookupNEGZones(ctx, projectID, regionZonesClient)
		if err != nil {
			return nil, err
		}
	}
	if len(zones) == 0 {
		return nil, errAtLeastOneZoneRequired
	}
	slices.Sort(zones)
	for _, zone := range zones {
		if !isValidNEGZone(zone) {
			return nil, fmt.Errorf("%w zone=%s", errInvalidNEGZone, zone)
		}
	}
	return zones, nil
}

// lookupNEGZones is used when the `neg-zones` flag is not supplied.
func lookupNEGZones(ctx context.Context, projectID string, regionZonesClient *compute.RegionZonesClient) ([]string, error) {
	zone, err := metadata.ZoneWithContext(ctx)
	if err != nil {
		return nil, fmt.Errorf("%s: unable to retrieve Compute Engine zone from metadata server: %w", errMissingNEGZones.Error(), err)
	}
	region, err := regionFromZone(zone)
	if err != nil {
		return nil, fmt.Errorf("unable to determine region from zone=%s: %w", zone, err)
	}
	var zones []string
	ctxWithDeadline, cancel := context.WithDeadline(ctx, time.Now().Add(TimeoutListRegionZones))
	defer cancel()
	for zone, err := range regionZonesClient.List(ctxWithDeadline, &computepb.ListRegionZonesRequest{
		Project:              projectID,
		Region:               region,
		ReturnPartialSuccess: proto.Bool(true),
	}).All() {
		if err != nil {
			return nil, fmt.Errorf("%s: unable to retrieve Compute Engine zones for projectID=%s regionFromZone=%s: %w", errMissingNEGZones.Error(), projectID, region, err)
		}
		zones = append(zones, *zone.Name)
	}
	return zones, nil
}

// getZoneMapping returns a map from Kubernetes cluster Node zones to Compute Engine zones.
// If no zone mappings are provided, and the controller manager is running on Google Cloud,
// the function returns a map of the provided zones where key=value (a "no-op map"),
// otherwise the function returns an error.
func getZoneMapping(logger logr.Logger, zones []string) (map[string]string, error) {
	if len(zoneMappingFlag) > 0 {
		zoneMapping := parseZoneMappingFlag()
		return validateZoneMapping(zoneMapping, zones)
	}
	if !metadata.OnGCE() {
		return nil, errZoneMappingsRequired
	}
	logger.V(2).Info("No zone mappings provided, using the zones reported by endpoints in EndpointSlices")
	noopMap := make(map[string]string, len(zones))
	for _, zone := range zones {
		noopMap[zone] = zone
	}
	return noopMap, nil
}

// getDefaultNEGZone returns the Compute Engine zone that should be used when attaching or detaching
// a network endpoint from a NEG if no zone mapping exists for the Kubernetes cluster Node zone
// in the EndpointSlice.
func getDefaultNEGZone(logger logr.Logger, zones []string) (string, error) {
	if len(defaultNEGZoneFlag) == 0 {
		zone := zones[0]
		logger.V(2).Info("No default NEG zone provided,"+
			" using one of the provided NEG zones as the default",
			"defaultNEGZone", zone)
		return zone, nil
	}
	for _, zone := range zones {
		if defaultNEGZoneFlag == zone {
			return defaultNEGZoneFlag, nil
		}
	}
	return "", fmt.Errorf("%w zone=%s zones=%+v", errDefaultNEGZoneNotInZones, defaultNEGZoneFlag, zones)
}

// regionFromZone returns the Compute Engine region of the supplied Compute Engine zone.
func regionFromZone(zone string) (string, error) {
	if !isValidNEGZone(zone) {
		return "", fmt.Errorf("%w zone=%s", errInvalidNEGZone, zone)
	}
	zoneSplit := strings.Split(zone, "-")
	return fmt.Sprintf("%s-%s", zoneSplit[0], zoneSplit[1]), nil
}

func validateZoneMapping(zoneMappings map[string]string, zones []string) (map[string]string, error) {
	negZones := make(map[string]bool, len(zones))
	for _, zone := range zones {
		negZones[zone] = true
	}
	for _, negZone := range zoneMappings {
		_, exists := negZones[negZone]
		if !exists {
			return nil, fmt.Errorf("%w %s", errInvalidNEGZoneInMapping, zoneMappingFlag)
		}
	}
	return zoneMappings, nil
}

func parseZoneMappingFlag() map[string]string {
	zoneMappingFlagSplit := strings.Split(zoneMappingFlag, ",")
	zoneMappings := make(map[string]string, len(zoneMappingFlagSplit))
	for _, mapping := range zoneMappingFlagSplit {
		kv := strings.Split(mapping, "=")
		zoneMappings[kv[0]] = kv[1]
	}
	return zoneMappings
}

// isValidNEGZone checks that the provided NEG zone look like a valid Compute Engine zones.
func isValidNEGZone(zone string) bool {
	return computeEngineZoneRegexp.MatchString(zone)
}
