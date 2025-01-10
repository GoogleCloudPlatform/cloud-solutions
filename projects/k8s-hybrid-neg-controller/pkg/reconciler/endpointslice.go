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

package reconciler

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strconv"
	"time"

	"cloud.google.com/go/compute/apiv1/computepb"
	"github.com/go-logr/logr"
	"golang.org/x/sync/errgroup"
	"google.golang.org/protobuf/proto"
	corev1 "k8s.io/api/core/v1"
	discoveryv1 "k8s.io/api/discovery/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/labels"
	"k8s.io/apimachinery/pkg/types"
	"k8s.io/client-go/tools/record"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/log"
	"sigs.k8s.io/controller-runtime/pkg/reconcile"

	"github.com/googlecloudplatform/k8s-hybrid-neg-controller/pkg/annotation"
	"github.com/googlecloudplatform/k8s-hybrid-neg-controller/pkg/neg"
)

const (
	// DurationObtainServiceLock determines how long the controller waits to obtain the lock for
	// updating endpoints of NEGs that belong to a Kubernetes Service.
	DurationObtainServiceLock = 5 * time.Minute
)

var (
	errEmptyNEGNameInStatus = errors.New("empty NEG name in hybrid NEG status annotation")
	errNoServiceNameLabel   = errors.New("no Service name label on EndpointSlice")
	errNoStatusAnnotation   = errors.New("hybrid NEG config annotation present, but not the status annotation")
)

// endpointSliceReconciler implements `reconcile.Reconciler` for Kubernetes EndpointSlice objects.
// See https://pkg.go.dev/sigs.k8s.io/controller-runtime@main/pkg/reconcile
type endpointSliceReconciler struct {
	client.Client
	defaultNEGZone         string
	negClient              *neg.Client
	recorder               record.EventRecorder
	requeueAfter           time.Duration
	timeoutSyncServiceNEGs time.Duration
	zoneMapping            map[string]string
	zones                  []string
}

var _ reconcile.Reconciler = &endpointSliceReconciler{}

func NewEndpointSliceReconciler(k8sClient client.Client, recorder record.EventRecorder, negClient *neg.Client, zones []string, zoneMapping map[string]string, defaultNEGZone string, requeueAfter time.Duration, timeoutSyncServiceNEGs time.Duration) reconcile.Reconciler {
	return &endpointSliceReconciler{
		Client:                 k8sClient,
		recorder:               recorder,
		negClient:              negClient,
		zones:                  zones,
		zoneMapping:            zoneMapping,
		defaultNEGZone:         defaultNEGZone,
		requeueAfter:           requeueAfter,
		timeoutSyncServiceNEGs: timeoutSyncServiceNEGs,
	}
}

// Reconcile performs a full reconciliation for the Kubernetes EndpointSlice object referred to by
// the `reconcile.Request`. The controller will requeue the `reconcile.Request` to be processed
// again if an error is non-nil or `reconcile.Result.Requeue` is `true`, otherwise upon completion
// it will remove the work from the queue.
func (r *endpointSliceReconciler) Reconcile(ctx context.Context, req reconcile.Request) (reconcile.Result, error) {
	logger := log.FromContext(ctx)
	logger.V(2).Info("Reconciling EndpointSlice")
	err := r.reconcile(ctx, logger, req.Namespace, req.Name)
	if err == nil || errors.Is(err, reconcile.TerminalError(nil)) {
		return reconcile.Result{}, err
	}
	logger.Error(err, "Requeueing")
	return reconcile.Result{
		Requeue:      true,
		RequeueAfter: r.requeueAfter,
	}, nil
}

// reconcile looks up the Service for the provided EndpointSlice name and namespace, and then
// performs a reconciliation for all NEGs of that Service.
func (r *endpointSliceReconciler) reconcile(ctx context.Context, logger logr.Logger, namespace string, endpointSliceName string) error {
	service, err := r.getService(ctx, namespace, endpointSliceName)
	if err != nil {
		logger.Error(err, "Could not find Service for EndpointSlice")
		return client.IgnoreNotFound(err)
	}
	logger = logger.WithValues("service", service.GetName())
	return r.reconcileEndpointsForService(ctx, logger, service)
}

func (r *endpointSliceReconciler) reconcileEndpointsForService(ctx context.Context, logger logr.Logger, service *corev1.Service) error {
	negStatus, err := getNEGStatus(logger, service)
	if err != nil {
		logger.Error(err, "Could not get Service NEG status")
		return err
	}
	if negStatus == nil {
		logger.V(6).Info("No Service NEG status, skipping")
		return nil
	}
	logger.V(4).Info("Found Service NEG status", "negStatus", negStatus)

	logger.V(2).Info("Reconciling endpoints")
	servicePortNameToNEGNameMap, err := getServicePortNameToNEGNameMap(*negStatus, service.Spec.Ports)
	if err != nil {
		logger.Error(err, "Skipping reconcile due to invalid NEG config, could not get service port to NEG name map.")
		return reconcile.TerminalError(err)
	}

	endpointSliceList, err := r.getEndpointSlicesForService(ctx, service)
	if err != nil {
		logger.Error(err, "Could not get EndpointSlices for Service")
		return err
	}
	logger.V(4).Info("Number of EndpointSlices for Service", "endpointSliceListSize", len(endpointSliceList.Items))
	servicePortNameToEndpointsByZoneMap := r.mapServicePortsToEndpointsByZone(logger, service.Spec.Ports, negStatus.Zones, endpointSliceList)

	return r.syncEndpoints(ctx, logger, servicePortNameToEndpointsByZoneMap, servicePortNameToNEGNameMap, types.NamespacedName{
		Namespace: service.GetNamespace(),
		Name:      service.GetName(),
	})
}

// getNEGStatus returns the hybrid NEG status annotation value for the provided Service.
func getNEGStatus(logger logr.Logger, service *corev1.Service) (*annotation.NEGStatus, error) {
	hybridNEGConfigAnnotationValue, serviceHasHybridNEGConfigAnnotation := service.Annotations[annotation.HybridNEGConfigKey]
	hybridNEGStatusAnnotationValue, serviceHasHybridNEGStatusAnnotation := service.Annotations[annotation.HybridNEGStatusKey]
	if !serviceHasHybridNEGConfigAnnotation && !serviceHasHybridNEGStatusAnnotation {
		logger.V(4).Info("Service does not have the hybrid NEG config or status annotations, skipping reconcile")
		return nil, nil
	}
	negConfig := &annotation.NEGConfig{}
	if serviceHasHybridNEGConfigAnnotation {
		if err := json.Unmarshal([]byte(hybridNEGConfigAnnotationValue), negConfig); err != nil {
			return nil, reconcile.TerminalError(fmt.Errorf("could not unmarshall NEG config annotation value [%s]:%w", hybridNEGConfigAnnotationValue, err))
		}
	}
	if serviceHasHybridNEGConfigAnnotation && len(negConfig.ExposedPorts) > 0 && !serviceHasHybridNEGStatusAnnotation {
		// The status annotation may not have been created yet, requeue to try again.
		return nil, fmt.Errorf("%w, requeueing", errNoStatusAnnotation)
	}
	negStatus := &annotation.NEGStatus{}
	if err := json.Unmarshal([]byte(hybridNEGStatusAnnotationValue), negStatus); err != nil {
		return nil, reconcile.TerminalError(fmt.Errorf("could not unmarshall NEG status annotation value [%s]:%w", hybridNEGStatusAnnotationValue, err))
	}
	return negStatus, nil
}

// getEndpointSlicesForService returns all the EndpointSlices for a Service.
func (r *endpointSliceReconciler) getEndpointSlicesForService(ctx context.Context, service *corev1.Service) (discoveryv1.EndpointSliceList, error) {
	labelSelector, err := labels.Parse(fmt.Sprintf("%s=%s", discoveryv1.LabelServiceName, service.GetName()))
	if err != nil {
		return discoveryv1.EndpointSliceList{}, reconcile.TerminalError(fmt.Errorf("could not create label selector: %w", err))
	}
	endpointSliceList := discoveryv1.EndpointSliceList{}
	if err := r.List(ctx, &endpointSliceList, &client.ListOptions{
		LabelSelector: labelSelector,
		Namespace:     service.GetNamespace(),
	}); err != nil {
		return discoveryv1.EndpointSliceList{}, fmt.Errorf("could not list EndpointSlices of service=%s/%s, requeueing: %w", service.GetNamespace(), service.GetName(), err)
	}
	return endpointSliceList, nil
}

// getService looks up and returns the Service for the provided EndpointSlice name and namespace.
func (r *endpointSliceReconciler) getService(ctx context.Context, namespace string, endpointSliceName string) (*corev1.Service, error) {
	endpointSlice := &metav1.PartialObjectMetadata{
		TypeMeta: metav1.TypeMeta{
			APIVersion: "discovery.k8s.io/v1",
			Kind:       "EndpointSlice",
		},
	}
	if err := r.Get(ctx, types.NamespacedName{
		Namespace: namespace,
		Name:      endpointSliceName,
	}, endpointSlice); err != nil {
		return nil, err
	}
	serviceName, exists := endpointSlice.ObjectMeta.Labels[discoveryv1.LabelServiceName]
	if !exists {
		return nil, errNoServiceNameLabel
	}
	service := &corev1.Service{}
	if err := r.Get(ctx, types.NamespacedName{
		Namespace: namespace,
		Name:      serviceName,
	}, service); err != nil {
		return nil, err
	}
	return service, nil
}

// syncEndpoints syncs the endpoints of all NEGs of the provided Service.
func (r *endpointSliceReconciler) syncEndpoints(ctx context.Context, logger logr.Logger, servicePortNameToEndpointsByZoneMap neg.ServiceEndpoints, servicePortNameToNEGNameMap map[string]string, service types.NamespacedName) error {
	logger.V(4).Info("Syncing endpoints", "servicePortNameToNEGNameMap", servicePortNameToNEGNameMap)
	logger.V(4).Info("Syncing endpoints", "len(servicePortNameToEndpointsByZoneMap)", len(servicePortNameToEndpointsByZoneMap))
	for servicePortName, endpointsByZoneMap := range servicePortNameToEndpointsByZoneMap {
		logger.V(4).Info("Syncing endpoints", "servicePortName", servicePortName, "len(endpointsByZoneMap)", len(endpointsByZoneMap))
		for zone, endpoints := range endpointsByZoneMap {
			logger.V(4).Info("Syncing endpoints", "servicePortName", servicePortName, "zone", zone, "len(endpoints)", len(endpoints))
		}
	}
	g, ctx := errgroup.WithContext(ctx)
	for portName, zoneToEndpointMap := range servicePortNameToEndpointsByZoneMap {
		g.Go(func() error {
			negName, exists := servicePortNameToNEGNameMap[portName]
			if !exists {
				logger.V(2).Info("NEG name mapping not found, skipping", "portName", portName)
				return nil
			}
			logger.V(4).Info("Syncing endpoints for NEG", "negName", negName)
			if err := r.negClient.SyncEndpoints(ctx, logger, negName, zoneToEndpointMap, service); err != nil {
				return fmt.Errorf("problem syncing NEG name=%s: %w", negName, err)
			}
			logger.V(4).Info("Successfully synced endpoints for NEG", "negName", negName)
			return nil
		})
	}
	if err := g.Wait(); err != nil {
		return reconcile.TerminalError(fmt.Errorf("problem syncing one or more NEGs: %w", err))
	}
	logger.V(4).Info("Successfully synced endpoints", "servicePortNameToNEGNameMap", servicePortNameToNEGNameMap)
	return nil
}

// mapServicePortsToEndpointsByZone returns a map of servicePortName -> zone -> endpoint,
// where endpoint is an (IP address, port number) tuple.
//
// The method iterates over the list of EndpointSlices. Each EndpointSlice may contain multiple
// ports. These are identified by the name of the Service port.
//
// For headful Services, the target port may be a name or a port number. If it is a name, the
// actual endpoint port may differ from one Pod to another, based on the Pod spec.
// Also, endpoints in an EndpointSlice may come from different zones.
func (r *endpointSliceReconciler) mapServicePortsToEndpointsByZone(logger logr.Logger, servicePorts []corev1.ServicePort, zones []string, endpointSliceList discoveryv1.EndpointSliceList) neg.ServiceEndpoints {
	servicePortsToEndpointsByZone := initializeServicePortNameToEndpointsByZoneMap(servicePorts, zones)
	for _, endpointSlice := range endpointSliceList.Items {
		// The endpoint port may be different to the service port for headful Services.
		for _, endpointSlicePort := range endpointSlice.Ports {
			if endpointSlicePort.Port == nil || *endpointSlicePort.Port == 0 {
				logger.V(2).Info("Skipping EndpointSlice port without Port value", "endpointSlice", endpointSlice)
				continue
			}
			var servicePortName string // empty string is a valid port name if there's only one service port
			if endpointSlicePort.Name != nil {
				servicePortName = *endpointSlicePort.Name
			}
			logger.V(4).Info("Number of endpoints for port", "endpointsSize", len(endpointSlice.Endpoints), "port", *endpointSlicePort.Port, "portName", servicePortName)
			for _, endpoint := range endpointSlice.Endpoints {
				if endpoint.Conditions.Ready == nil || !*endpoint.Conditions.Ready {
					continue
				}
				zone := r.mapZone(logger, endpoint)
				for _, address := range endpoint.Addresses {
					servicePortsToEndpointsByZone[servicePortName][zone].Put(&computepb.NetworkEndpoint{
						IpAddress: proto.String(address),
						Port:      endpointSlicePort.Port,
					})
				}
			}
		}
	}
	return servicePortsToEndpointsByZone
}

func initializeServicePortNameToEndpointsByZoneMap(servicePorts []corev1.ServicePort, zones []string) neg.ServiceEndpoints {
	servicePortsToEndpointsByZone := neg.ServiceEndpoints{}
	for _, servicePort := range servicePorts {
		servicePortsToEndpointsByZone[servicePort.Name] = neg.ZonalEndpoints{}
		for _, zone := range zones {
			servicePortsToEndpointsByZone[servicePort.Name][zone] = neg.EndpointSet{}
		}
	}
	return servicePortsToEndpointsByZone
}

// getServicePortNameToNEGNameMap translates the service ports from the network_endpoint_groups map in
// the hybrid NEG status annotation to service port names.
func getServicePortNameToNEGNameMap(negStatus annotation.NEGStatus, servicePorts []corev1.ServicePort) (map[string]string, error) {
	servicePortNameToNEGNameMap := make(map[string]string, len(negStatus.NetworkEndpointGroups))
	for servicePortNumber, negName := range negStatus.NetworkEndpointGroups {
		if len(negName) == 0 {
			return nil, fmt.Errorf("%w for service port number %s: %+v", errEmptyNEGNameInStatus, servicePortNumber, negStatus.NetworkEndpointGroups)
		}
		for _, servicePort := range servicePorts {
			if strconv.FormatInt(int64(servicePort.Port), 10) == servicePortNumber {
				servicePortNameToNEGNameMap[servicePort.Name] = negName
			}
		}
	}
	return servicePortNameToNEGNameMap, nil
}

// mapZone returns the Compute Engine zone for the provided endpoint, based on the endpoint's
// zone, and the controller's zone mapping. If the endpoint's zone is nil, or if there is no
// match for the endpoint's zone in the controller's zone mapping configuration, this method
// returns the controller's default Compute Engine zone.
func (r *endpointSliceReconciler) mapZone(logger logr.Logger, endpoint discoveryv1.Endpoint) string {
	if endpoint.Zone == nil {
		logger.Info("Nil zone for endpoint in EndpointSlice, using default NEG zone", "endpoint", endpoint, "defaultNEGZone", r.defaultNEGZone)
		return r.defaultNEGZone
	}
	zone, ok := r.zoneMapping[*endpoint.Zone]
	if !ok {
		logger.Info("No mapping for endpoint zone, using default NEG zone", "endpointZone", *endpoint.Zone, "defaultNEGZone", r.defaultNEGZone)
		return r.defaultNEGZone
	}
	return zone
}
