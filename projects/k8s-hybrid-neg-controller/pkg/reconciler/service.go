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
	"crypto/md5" // #nosec Not using MD5 as a secure hash function
	"encoding/json"
	"errors"
	"fmt"
	"strconv"
	"time"

	"github.com/go-logr/logr"
	"golang.org/x/sync/errgroup"
	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/types"
	"k8s.io/client-go/tools/record"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/controller/controllerutil"
	"sigs.k8s.io/controller-runtime/pkg/log"
	"sigs.k8s.io/controller-runtime/pkg/reconcile"

	"github.com/googlecloudplatform/k8s-hybrid-neg-controller/pkg/annotation"
	"github.com/googlecloudplatform/k8s-hybrid-neg-controller/pkg/neg"
)

const (
	FinalizerName = "solutions.cloud.google.com/hybrid-neg"

	maxLengthNEGName = 63
)

// serviceReconciler implements `reconcile.Reconciler` for Kubernetes Service objects.
// See https://pkg.go.dev/sigs.k8s.io/controller-runtime@main/pkg/reconcile
type serviceReconciler struct {
	client.Client
	clusterID    string
	negClient    *neg.Client
	recorder     record.EventRecorder
	requeueAfter time.Duration
	zones        []string
}

var _ reconcile.Reconciler = &serviceReconciler{}

func NewServiceReconciler(k8sClient client.Client, recorder record.EventRecorder, negClient *neg.Client, clusterID string, zones []string, requeueAfter time.Duration) reconcile.Reconciler {
	return &serviceReconciler{
		Client:       k8sClient,
		clusterID:    clusterID,
		negClient:    negClient,
		recorder:     recorder,
		requeueAfter: requeueAfter,
		zones:        zones,
	}
}

// Reconcile performs a full reconciliation for the Kubernetes Service object referred to by
// the `reconcile.Request`. The controller will requeue the `reconcile.Request` to be processed
// again if an error is non-nil or `reconcile.Result.Requeue` is `true`, otherwise upon completion
// it will remove the work from the queue.
func (r *serviceReconciler) Reconcile(ctx context.Context, req reconcile.Request) (reconcile.Result, error) {
	logger := log.FromContext(ctx)
	err := r.reconcile(ctx, logger, req.NamespacedName)
	if err == nil || errors.Is(err, reconcile.TerminalError(nil)) {
		return reconcile.Result{}, err
	}
	logger.Error(err, "Requeueing")
	return reconcile.Result{
		Requeue:      true,
		RequeueAfter: r.requeueAfter,
	}, nil
}

// reconcile creates and deletes hybrid NEGs for the provided Service, based on the hybrid NEG
// config annotation on the Service.
func (r *serviceReconciler) reconcile(ctx context.Context, logger logr.Logger, serviceNamespacedName types.NamespacedName) error {
	service := &corev1.Service{}
	if err := r.Get(ctx, serviceNamespacedName, service); err != nil {
		// Ignore not-found errors, since they can't be fixed by an immediate requeue.
		return client.IgnoreNotFound(err)
	}

	if !service.ObjectMeta.DeletionTimestamp.IsZero() {
		if err := r.handleDelete(ctx, logger, service); err != nil {
			return err
		}
		// Stop reconciliation as the item is being deleted
		return nil
	}

	negConfig, negConfigAnnotationExists, err := getHybridNEGConfig(service.ObjectMeta.Annotations)
	if err != nil {
		r.recorder.Event(service, "Warning", "ConfigError", err.Error())
		return reconcile.TerminalError(err)
	}
	logger.V(4).Info("Hybrid NEG config annotation", "negConfig", negConfig)
	negStatus, negStatusAnnotationExists, err := getHybridNEGStatus(service.ObjectMeta.Annotations)
	if err != nil {
		r.recorder.Event(service, "Warning", "ConfigError", err.Error())
		logger.Error(err, "Problem reading the hybrid NEG status annotation, proceeding as if it does not exist")
	}
	logger.V(4).Info("Hybrid NEG status annotation", "negStatus", negStatus)
	if !negConfigAnnotationExists && !negStatusAnnotationExists {
		// No hybrid NEG annotations, do nothing.
		return nil
	}

	negsToCreate, negsToDelete := r.syncNEGs(ctx, logger, serviceNamespacedName, negConfig, negStatus)
	if err := r.updateService(ctx, logger, service, negStatus, negsToCreate, negsToDelete); err != nil {
		return err
	}
	return nil
}

// syncNEGs creates and deletes NEGs for the provided Service, based on the provided hybrid NEG
// config annotation. It also updates the Service's hybrid NEG status annotation to reflect the
// names and Compute Engine zones of the Service's hybrid NEGs.
// This method intentionally does not propagate errors, and instead just logs them. The reason is
// to prevent infinite reconciliation retries in case of unrecoverable errors, such as IAM
// permission issues.
func (r *serviceReconciler) syncNEGs(ctx context.Context, logger logr.Logger, service types.NamespacedName, negConfig annotation.NEGConfig, negStatus annotation.NEGStatus) (map[string]string, map[string]string) {
	negsToCreate := getNEGsToCreate(logger, negConfig, negStatus, r.clusterID, service)
	if err := r.createNEGs(ctx, logger, negsToCreate, service); err != nil {
		logger.Error(err, "Problem creating hybrid NEGs")
	}
	negsToDelete := getNEGsToDelete(logger, negConfig, negStatus)
	if err := r.deleteNEGs(ctx, logger, negsToDelete, service); err != nil {
		logger.Error(err, "Problem deleting hybrid NEGs that were removed from the hybrid NEG config annotation")
	}
	return negsToCreate, negsToDelete
}

// getHybridNEGConfig returns the config annotation added by this controller, similar to
// the `cloud.google.com/neg` annotation, see
// https://cloud.google.com/kubernetes-engine/docs/how-to/standalone-neg#naming_negs
func getHybridNEGConfig(annotations map[string]string) (annotation.NEGConfig, bool, error) {
	annotationValue, exists := annotations[annotation.HybridNEGConfigKey]
	if !exists {
		return annotation.NEGConfig{
			ExposedPorts: map[int32]annotation.NEGAttributes{},
		}, false, nil
	}
	negConfig := annotation.NEGConfig{}
	if err := json.Unmarshal([]byte(annotationValue), &negConfig); err != nil {
		return annotation.NEGConfig{}, false, fmt.Errorf("could not unmarshal value of annotation [%s: %s]: %w", annotation.HybridNEGConfigKey, annotationValue, err)
	}
	if negConfig.ExposedPorts == nil {
		negConfig.ExposedPorts = map[int32]annotation.NEGAttributes{}
	}
	return negConfig, true, nil
}

// getHybridNEGStatus returns the hybrid NEG status annotation added by this controller.
// The format of the hybrid NEG status annotation matches the format of the
// `cloud.google.com/neg-status` annotation that the GKE NEG controller adds for standalone NEGs,
// see https://cloud.google.com/kubernetes-engine/docs/how-to/standalone-neg#retrieve-neg-status
func getHybridNEGStatus(annotations map[string]string) (annotation.NEGStatus, bool, error) {
	annotationValue, exists := annotations[annotation.HybridNEGStatusKey]
	if !exists {
		return annotation.NEGStatus{
			NetworkEndpointGroups: map[string]string{},
		}, false, nil
	}
	negStatus := annotation.NEGStatus{}
	if err := json.Unmarshal([]byte(annotationValue), &negStatus); err != nil {
		return annotation.NEGStatus{}, false, fmt.Errorf("could not unmarshal value of annotation [%s: %s]: %w", annotation.HybridNEGStatusKey, annotationValue, err)
	}
	if negStatus.NetworkEndpointGroups == nil {
		negStatus.NetworkEndpointGroups = map[string]string{}
	}
	return negStatus, true, nil
}

// getNEGsToCreate returns entries from the `exposed_ports` map in the hybrid NEG config
// annotation that do _not_ have corresponding entries in the `network_endpoint_groups` map in the
// hybrid NEG status annotation, matching by the key (Service port number).
// It also generates NEG names if not specified in the `exposed_ports` map in the hybrid NEG config
// annotation.
func getNEGsToCreate(logger logr.Logger, negConfig annotation.NEGConfig, negStatus annotation.NEGStatus, clusterID string, service types.NamespacedName) map[string]string {
	negsToCreate := map[string]string{}
	for exposedPortNumber, negNameFromConfig := range negConfig.ExposedPorts {
		servicePortNumber := strconv.FormatInt(int64(exposedPortNumber), 10)
		negNameFromStatus, existsInStatus := negStatus.NetworkEndpointGroups[servicePortNumber]
		if existsInStatus {
			if negNameFromConfig.Name != "" && negNameFromConfig.Name != negNameFromStatus {
				logger.Info("Mismatched NEG names in config and status annotations, NEG names will not be updated", "negConfig", negConfig, "negStatus", negStatus)
			}
			// Don't recreate NEG, since it should already exist if it's in the status annotation.
			continue
		}
		if negNameFromConfig.Name == "" {
			// #nosec Not using MD5 as a secure hash function
			suffix := fmt.Sprintf("-%0x", md5.Sum([]byte(clusterID+service.Namespace+service.Name+servicePortNumber)))[:9]
			prefix := fmt.Sprintf("k8s1-%s-%s-%s-%s", clusterID, service.Namespace, service.Name, servicePortNumber)
			if len(prefix+suffix) > maxLengthNEGName {
				prefix = prefix[:maxLengthNEGName-len(suffix)]
			}
			negNameFromConfig = annotation.NEGAttributes{
				Name: prefix + suffix,
			}
		}
		negsToCreate[servicePortNumber] = negNameFromConfig.Name
	}
	return negsToCreate
}

// getNEGsToDelete returns entries from the `network_endpoint_groups` map in the hybrid NEG status
// annotation that do _not_ have corresponding entries in the `exposed_ports` map in the hybrid NEG
// config annotation, matching by the key (Service port number).
func getNEGsToDelete(logger logr.Logger, negConfig annotation.NEGConfig, negStatus annotation.NEGStatus) map[string]string {
	negsToDelete := map[string]string{}
	for servicePortNumber, negName := range negStatus.NetworkEndpointGroups {
		exposedPortNumber, err := strconv.ParseInt(servicePortNumber, 10, 32)
		if err != nil {
			logger.Error(err, "invalid service port number in hybrid NEG status annotation, skipping entry", "servicePortNumber", servicePortNumber)
			continue
		}
		_, existsInConfig := negConfig.ExposedPorts[int32(exposedPortNumber)]
		if !existsInConfig {
			logger.V(2).Info("NEG from status annotation missing from config annotation, deleting", "port", servicePortNumber, "networkEndpointGroup", negName)
			negsToDelete[servicePortNumber] = negName
		}
	}
	return negsToDelete
}

// createNEGs creates hybrid NEGs for all of the provided Service port numbers, across all
// zones configured on the controller.
func (r *serviceReconciler) createNEGs(ctx context.Context, logger logr.Logger, servicePortNumberToNEGName map[string]string, service types.NamespacedName) error {
	g, groupCtx := errgroup.WithContext(ctx)
	for servicePortNumber, negName := range servicePortNumberToNEGName {
		g.Go(func() error {
			logger.Info("Creating NEGs", "servicePortNumber", servicePortNumber, "name", negName)
			if err := r.negClient.CreateNEGs(groupCtx, logger, negName, service); err != nil {
				return fmt.Errorf("problem creating NEG with port=%s name=%s: %w", servicePortNumber, negName, err)
			}
			return nil
		})
	}
	if err := g.Wait(); err != nil {
		return fmt.Errorf("problem creating one or more NEGs: %w", err)
	}
	return nil
}

// deleteNEGs deletes hybrid NEGs for all of the provided Service port numbers, across all
// zones configured on the controller.
func (r *serviceReconciler) deleteNEGs(ctx context.Context, logger logr.Logger, servicePortNumberToNEGName map[string]string, service types.NamespacedName) error {
	g, groupCtx := errgroup.WithContext(ctx)
	for servicePortNumber, negName := range servicePortNumberToNEGName {
		g.Go(func() error {
			logger.Info("Deleting NEGs", "servicePortNumber", servicePortNumber, "name", negName)
			if err := r.negClient.DeleteNEGs(groupCtx, logger, negName, service); err != nil {
				return fmt.Errorf("problem deleting NEG with port=%s name=%s: %w", servicePortNumber, negName, err)
			}
			return nil
		})
	}
	if err := g.Wait(); err != nil {
		return fmt.Errorf("problem deleting one or more NEGs: %w", err)
	}
	return nil
}

// updateService connects to the Kubernetes cluster API server to update the Service definition if
// the reconciler made any of the following changes to the Service:
//
// - added or removed the `solutions.cloud.google.com/hybrid-neg` finalizer.
// - created or removed hybrid NEGs.
func (r *serviceReconciler) updateService(ctx context.Context, logger logr.Logger, service *corev1.Service, negStatus annotation.NEGStatus, negsToCreate map[string]string, negsToDelete map[string]string) error {
	if err := updateNEGStatusIfRequired(logger, negStatus, negsToCreate, negsToDelete, r.zones, service); err != nil {
		return err
	}
	var updatedFinalizer bool
	if len(negStatus.NetworkEndpointGroups) > 0 {
		updatedFinalizer = controllerutil.AddFinalizer(service, FinalizerName)
	} else {
		updatedFinalizer = controllerutil.RemoveFinalizer(service, FinalizerName)
	}
	if updatedFinalizer || len(negsToCreate) > 0 || len(negsToDelete) > 0 {
		// The Service has been modified, update it.
		return r.Update(ctx, service)
	}
	return nil
}

// updateNEGStatusIfRequired updates the hybrid NEG status annotation value on the Service
// if the reconciler added or removed hybrid NEGs.
func updateNEGStatusIfRequired(logger logr.Logger, negStatus annotation.NEGStatus, negsToCreate map[string]string, negsToDelete map[string]string, zones []string, service *corev1.Service) error {
	if len(negsToCreate) == 0 && len(negsToDelete) == 0 {
		return nil
	}
	for servicePortNumber, negName := range negsToCreate {
		negStatus.NetworkEndpointGroups[servicePortNumber] = negName
	}
	for servicePortNumber := range negsToDelete {
		delete(negStatus.NetworkEndpointGroups, servicePortNumber)
	}
	if len(negStatus.NetworkEndpointGroups) == 0 {
		logger.V(2).Info("Removing hybrid NEG status annotation")
		delete(service.Annotations, annotation.HybridNEGStatusKey)
		return nil
	}
	negStatus.Zones = zones
	logger.V(2).Info("Updating hybrid NEG status annotation")
	negStatusBytes, err := json.Marshal(negStatus)
	if err != nil {
		return reconcile.TerminalError(fmt.Errorf("could not marshal new NEG status annotation value: %w", err))
	}
	service.Annotations[annotation.HybridNEGStatusKey] = string(negStatusBytes)
	return nil
}

// handleDelete attempts to delete the hybrid NEGs of the Service that is being deleted if the
// Service has the `solutions.cloud.google.com/hybrid-neg` finalizer.
//
// If any of the NEGs are referenced by backend services, deletion will fail. NEGs must be removed
// from backend services before they can be deleted. Removing NEGs from backend services is
// typically done using the same mechanism used to add NEG references to backend services, e.g.,
// using infrastructure-as-code tools.
//
// If deletion of any NEG fails, this method logs the error _but does not return the error_.
//
// After attempting to delete the NEGs, this method removes the
// `solutions.cloud.google.com/hybrid-neg` finalizer from the Service. The method returns an error
// that requeues the reconcile request if removal of the finalizer fails.
//
// [Backend services overview]: https://cloud.google.com/load-balancing/docs/backend-service
func (r *serviceReconciler) handleDelete(ctx context.Context, logger logr.Logger, service *corev1.Service) error {
	if controllerutil.ContainsFinalizer(service, FinalizerName) {
		// Our finalizer is present, so let's clean up the external resources.
		if err := r.finalize(ctx, logger, service); err != nil {
			logger.Error(err, "Problem deleting external resources, these will need to be manually cleaned up")
		}
		// Remove our finalizer from the Service.
		controllerutil.RemoveFinalizer(service, FinalizerName)
		if err := r.Update(ctx, service); err != nil {
			logger.Error(err, "Problem removing finalizer, requeueing")
			return err
		}
	}
	return nil
}

// finalize parses the hybrid NEG status annotation on the Service and uses the NEG names and
// zones in the annoation value to request deletion of the hybrid NEGs associated to the Service.
//
// This method returns an error if either of the following happens:
// - There is a problem parsing the hybrid NEG status annotation value.
// - There is problem deleting one or more of the hybrid NEGs.
func (r *serviceReconciler) finalize(ctx context.Context, logger logr.Logger, service *corev1.Service) error {
	negStatus, exists, err := getHybridNEGStatus(service.Annotations)
	if err != nil {
		return fmt.Errorf("problem reading the hybrid NEG status annotation: %w", err)
	}
	if !exists {
		return nil
	}
	g, groupCtx := errgroup.WithContext(ctx)
	for _, negName := range negStatus.NetworkEndpointGroups {
		g.Go(func() error {
			return r.negClient.DeleteNEGs(groupCtx, logger, negName, types.NamespacedName{
				Namespace: service.GetNamespace(),
				Name:      service.GetName(),
			})
		})
	}
	return g.Wait()
}
