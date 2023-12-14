// Copyright 2023 Google LLC
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

package helper

import (
	"context"
	"encoding/base64"

	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"k8s.io/cli-runtime/pkg/resource"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
	"k8s.io/client-go/restmapper"
	clientcmdapi "k8s.io/client-go/tools/clientcmd/api"
	"sigs.k8s.io/controller-runtime/pkg/log"
)

func Kube2Client(ctx context.Context, caText64 string, gkeEndpoint string) (*rest.Config, *kubernetes.Clientset, error) {
	l := log.FromContext(ctx)
	l.Info("decode caText64", "caText64", caText64)
	caText, err := base64.StdEncoding.DecodeString(caText64)
	if err != nil {
		l.Error(err, "failed to decode text")
		return nil, nil, err
	}
	config := &rest.Config{
		TLSClientConfig: rest.TLSClientConfig{
			CAData: caText,
		},
		Host: gkeEndpoint,
		AuthProvider: &clientcmdapi.AuthProviderConfig{
			Name: "google",
		},
	}
	clientset, err := kubernetes.NewForConfig(config)
	return config, clientset, err

}

func CreateObject(ctx context.Context, kubeClientset kubernetes.Interface, restConfig rest.Config, obj runtime.Object) (runtime.Object, error) {
	l := log.FromContext(ctx)
	// Create a REST mapper that tracks information about the available resources in the cluster.
	groupResources, err := restmapper.GetAPIGroupResources(kubeClientset.Discovery())
	if err != nil {
		return obj, err
	}
	rm := restmapper.NewDiscoveryRESTMapper(groupResources)

	// Get some metadata needed to make the REST request.
	gvk := obj.GetObjectKind().GroupVersionKind()
	gk := schema.GroupKind{Group: gvk.Group, Kind: gvk.Kind}
	mapping, err := rm.RESTMapping(gk, gvk.Version)
	if err != nil {
		return obj, err
	}

	name, err := meta.NewAccessor().Name(obj)
	if err != nil {
		return obj, err
	}
	l.Info("the name of object", "name", name)

	// Create a client specifically for creating the object.
	restClient, err := newRestClient(restConfig, mapping.GroupVersionKind.GroupVersion())
	if err != nil {
		return obj, err
	}

	// Use the REST helper to create the object in the "default" namespace.
	restHelper := resource.NewHelper(restClient, mapping)
	return restHelper.Create("default", false, obj)
}

func PhaseOfPod(ctx context.Context, kubeClientset kubernetes.Interface, podName string, podNamespace string) (corev1.PodPhase, error) {
	l := log.FromContext(ctx)
	// Get a pod status from kubeClientset
	pod, err := kubeClientset.CoreV1().Pods(podName).Get(ctx, podNamespace, metav1.GetOptions{})
	if err != nil {
		l.Error(err, "failed to get pod")
		return corev1.PodUnknown, err
	}
	l.Info("the phase of pod", "phase", pod.Status.Phase)

	return pod.Status.Phase, nil
}

func newRestClient(restConfig rest.Config, gv schema.GroupVersion) (rest.Interface, error) {
	restConfig.ContentConfig = resource.UnstructuredPlusDefaultContentConfig()
	restConfig.GroupVersion = &gv
	if len(gv.Group) == 0 {
		restConfig.APIPath = "/api"
	} else {
		restConfig.APIPath = "/apis"
	}

	return rest.RESTClientFor(&restConfig)
}
