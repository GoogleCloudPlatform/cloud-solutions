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
	"fmt"
	"strings"

	corev1 "k8s.io/api/core/v1"
	discoveryv1 "k8s.io/api/discovery/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/labels"
	"k8s.io/apimachinery/pkg/types"
	"k8s.io/client-go/tools/record"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/controller/controllerutil"
	"sigs.k8s.io/controller-runtime/pkg/handler"
	"sigs.k8s.io/controller-runtime/pkg/log"
	"sigs.k8s.io/controller-runtime/pkg/manager"
	"sigs.k8s.io/controller-runtime/pkg/predicate"
	"sigs.k8s.io/controller-runtime/pkg/reconcile"

	"github.com/googlecloudplatform/k8s-hybrid-neg-controller/pkg/annotation"
	"github.com/googlecloudplatform/k8s-hybrid-neg-controller/pkg/config"
	"github.com/googlecloudplatform/k8s-hybrid-neg-controller/pkg/neg"
)

// CreateReconcilers creates reconcilers for Kubernetes Services and EndpointSlices.
func CreateReconcilers(ctx context.Context, mgr manager.Manager, eventRecorder record.EventRecorder, cfg *config.ReconcilerConfig) error {
	negClient, err := neg.NewClient(ctx, cfg.Network, cfg.ProjectID, cfg.Timeouts, cfg.Zones)
	if err != nil {
		return fmt.Errorf("problem creating NEG sync client: %w", err)
	}

	endpointSliceReconciler := NewEndpointSliceReconciler(mgr.GetClient(), eventRecorder, negClient, cfg.Zones, cfg.ZoneMapping, cfg.DefaultNEGZone, cfg.RequeueAfter, cfg.Timeouts.SyncServiceEndpoints)
	if err := ctrl.NewControllerManagedBy(mgr).
		For(&discoveryv1.EndpointSlice{}).
		Watches(&corev1.Service{}, handler.EnqueueRequestsFromMapFunc(serviceToEndpointSliceMapFunc(mgr.GetClient()))).
		WithEventFilter(predicate.ResourceVersionChangedPredicate{}).
		WithEventFilter(endpointSliceIsIPv4()).
		WithEventFilter(noSystemNamespaces(cfg.ExcludeSystemNamespaces)).
		Complete(endpointSliceReconciler); err != nil {
		return fmt.Errorf("could not create controller for Kubernetes EndpointSlices: %w", err)
	}

	serviceReconciler := NewServiceReconciler(mgr.GetClient(), eventRecorder, negClient, cfg.ClusterID, cfg.Zones, cfg.RequeueAfter)
	if err := ctrl.NewControllerManagedBy(mgr).
		For(&corev1.Service{}).
		WithEventFilter(predicate.ResourceVersionChangedPredicate{}).
		WithEventFilter(noSystemNamespaces(cfg.ExcludeSystemNamespaces)).
		WithEventFilter(hasHybridNEGAnnotationOrFinalizer()).
		WithEventFilter(hasPorts()).
		Complete(serviceReconciler); err != nil {
		return fmt.Errorf("could not create controller for Kubernetes Services: %w", err)
	}
	return nil
}

// serviceToEndpointSliceMapFunc triggers a reconciliation of a Service's EndpointSlices when
// there a Service reconciliation event. This ensures that endpoints are added immediately after
// NEG creation, without having to wait for an EndpointSlice reconciliation event.
func serviceToEndpointSliceMapFunc(k8sClient client.Client) handler.MapFunc {
	return func(ctx context.Context, o client.Object) []reconcile.Request {
		logger := log.FromContext(ctx).WithValues("namespace", o.GetNamespace(), "service", o.GetName())
		if o.GetDeletionTimestamp() != nil {
			logger.V(4).Info("Not triggering EndpointSlice reconciliation for Service, as Service is being deleted")
			return nil
		}
		if _, exists := o.GetAnnotations()[annotation.HybridNEGConfigKey]; !exists {
			logger.V(4).Info("Not triggering EndpointSlice reconciliation for Service," +
				" as Service does not have the hybrid NEG config annotation")
			return nil
		}
		labelSelector, err := labels.Parse(fmt.Sprintf("%s=%s", discoveryv1.LabelServiceName, o.GetName()))
		if err != nil {
			logger.Error(err, "Could not create label selector, must wait for next EndpointSlice event to reconcile NEG endpoints")
			return nil
		}

		// Query for metadata only to save memory.
		endpointSliceList := &metav1.PartialObjectMetadataList{
			TypeMeta: metav1.TypeMeta{
				APIVersion: "discovery.k8s.io/v1",
				Kind:       "EndpointSliceList",
			},
		}
		if err := k8sClient.List(ctx, endpointSliceList, &client.ListOptions{
			Namespace:     o.GetNamespace(),
			LabelSelector: labelSelector,
		}); err != nil {
			logger.Error(err, "Could not list EndpointSlices, must wait for next EndpointSlice event to reconcile NEG endpoints")
			return nil
		}
		if len(endpointSliceList.Items) == 0 || endpointSliceList.Items[0].GetName() == "" {
			logger.V(4).Info("Not triggering EndpointSlice reconciliation for Service, as no EndpointSlices found")
			return nil
		}
		logger.V(2).Info("Enqueueing EndpointSlice reconciliation for Service")

		// The EndpointSlice reconciler looks up all EndpointSlices for the Service, so we only
		// need to enqueue a reconcile request for one of the EndpointSlices.
		return []reconcile.Request{
			{
				NamespacedName: types.NamespacedName{
					Namespace: o.GetNamespace(),
					Name:      endpointSliceList.Items[0].GetName(),
				},
			},
		}
	}
}

// endpointSliceIsIPv4 predicate to only reconcile EndpointSlices with `addressType` of IPv4.
//
// References:
//   - [Kubernetes: Dual-stack networking]
//   - [Google Cloud: IPv6 for Application Load Balancers and proxy Network Load Balancers]
//
// [Kubernetes: Dual-stack networking]: https://kubernetes.io/docs/concepts/services-networking/dual-stack/
// [Google Cloud: IPv6 for Application Load Balancers and proxy Network Load Balancers]: https://cloud.google.com/load-balancing/docs/ipv6
func endpointSliceIsIPv4() predicate.Funcs {
	return predicate.NewPredicateFuncs(func(object client.Object) bool {
		if object == nil {
			return false
		}
		endpointSlice, ok := object.(*discoveryv1.EndpointSlice)
		if !ok {
			// Not an EndpointSlice, probably a Service, don't filter.
			return true
		}
		return endpointSlice.AddressType == discoveryv1.AddressTypeIPv4
	})
}

// noSystemNamespaces is used to filter out (i.e., not reconcile) objects in Kubernetes Namespaces
// with names ending with `-system`, but only if the `excludeSystemNamespaces` argument is `true`.
func noSystemNamespaces(excludeSystemNamespaces bool) predicate.Funcs {
	return predicate.NewPredicateFuncs(func(object client.Object) bool {
		if object == nil {
			return false
		}
		if !excludeSystemNamespaces {
			return true
		}
		return !strings.HasSuffix(object.GetNamespace(), "-system")
	})
}

// hasHybridNEGAnnotationOrFinalizer is used to filter out Kubernetes Services that have
// neither the hybrid NEG config annotations, nor the hybrid NEG finalizer.
func hasHybridNEGAnnotationOrFinalizer() predicate.Funcs {
	return predicate.NewPredicateFuncs(func(object client.Object) bool {
		if object == nil {
			return false
		}
		service, ok := object.(*corev1.Service)
		if !ok {
			// Not a Service, don't filter.
			return true
		}
		_, configExists := service.GetAnnotations()[annotation.HybridNEGConfigKey]
		if configExists {
			return true
		}
		_, statusExists := service.GetAnnotations()[annotation.HybridNEGStatusKey]
		if statusExists {
			return true
		}
		return controllerutil.ContainsFinalizer(service, FinalizerName)
	})
}

// hasPorts is used to filter out Kubernetes Services that don't expose ports,
// such as Services of type ExternalName.
func hasPorts() predicate.Funcs {
	return predicate.NewPredicateFuncs(func(object client.Object) bool {
		if object == nil {
			return false
		}
		service, ok := object.(*corev1.Service)
		if !ok {
			// Not a Service, don't filter.
			return true
		}
		return len(service.Spec.Ports) > 0
	})
}
