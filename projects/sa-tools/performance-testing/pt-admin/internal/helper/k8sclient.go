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
	"bytes"
	"context"
	"encoding/base64"
	"io/ioutil"

	appv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/runtime/serializer/yaml"
	yamlutil "k8s.io/apimachinery/pkg/util/yaml"
	"k8s.io/client-go/dynamic"
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
		l.Error(err, "failed to decode text", "caText64", caText64)
		return nil, nil, err
	}
	config := &rest.Config{
		TLSClientConfig: rest.TLSClientConfig{
			CAData: caText,
		},
		Host: gkeEndpoint, // such as: "https://34.81.126.228"
		AuthProvider: &clientcmdapi.AuthProviderConfig{
			Name: "google",
		},
	}
	clientset, err := kubernetes.NewForConfig(config)
	return config, clientset, err

}

func StatusOfPVC(ctx context.Context, caText64 string, gkeEndpoint string, ns string, name string) (*corev1.PersistentVolumeClaim, error) {
	l := log.FromContext(ctx)
	_, clientSet, err := Kube2Client(ctx, caText64, gkeEndpoint)
	if err != nil {
		l.Error(err, "failed to get clientset")
		return &corev1.PersistentVolumeClaim{}, err
	}
	pvc, err := clientSet.CoreV1().PersistentVolumeClaims(ns).Get(ctx, name, metav1.GetOptions{})
	if err != nil {
		l.Error(err, "failed to get PersistentVolumeClaims", "ns", ns, "name", name)
		return &corev1.PersistentVolumeClaim{}, err
	}

	return pvc, nil
}

func StatusOfDeployment(ctx context.Context, caText64 string, gkeEndpoint string, ns string, name string) (*appv1.Deployment, error) {
	l := log.FromContext(ctx)
	_, clientSet, err := Kube2Client(ctx, caText64, gkeEndpoint)
	if err != nil {
		l.Error(err, "failed to get clientset")
		return &appv1.Deployment{}, err
	}
	dep, err := clientSet.AppsV1().Deployments(ns).Get(ctx, name, metav1.GetOptions{})
	if err != nil {
		l.Error(err, "failed to get Deployment", "ns", ns, "name", name)
		return &appv1.Deployment{}, err
	}
	return dep, nil
}
func CreateBytes2K8s(ctx context.Context, caText64 string, gkeEndpoint string, filebytes []byte) error {
	l := log.FromContext(ctx)
	l.Info("apply bytes to k8s")
	restConfig, clientSet, err := Kube2Client(ctx, caText64, gkeEndpoint)
	if err != nil {
		l.Error(err, "failed to get clientset")
		return err
	}
	dd, err := dynamic.NewForConfig(restConfig)
	if err != nil {
		l.Error(err, "failed to get dynamic client")
		return err
	}
	decoder := yamlutil.NewYAMLOrJSONDecoder(bytes.NewReader(filebytes), 100)
	for {
		var rawObj runtime.RawExtension
		if err = decoder.Decode(&rawObj); err != nil {
			break
		}

		obj, gvk, err := yaml.NewDecodingSerializer(unstructured.UnstructuredJSONScheme).Decode(rawObj.Raw, nil, nil)
		if err != nil {
			l.Error(err, "failed to decode")
			return err
		}

		// For debug
		// y := printers.YAMLPrinter{}
		// y.PrintObj(obj, os.Stdout)
		//
		unstructuredMap, err := runtime.DefaultUnstructuredConverter.ToUnstructured(obj)
		if err != nil {
			l.Error(err, "failed to convert to unstructured")
			return err
		}

		unstructuredObj := &unstructured.Unstructured{Object: unstructuredMap}

		gr, err := restmapper.GetAPIGroupResources(clientSet.Discovery())
		if err != nil {
			l.Error(err, "failed to get api group resources")
			return err
		}

		mapper := restmapper.NewDiscoveryRESTMapper(gr)
		mapping, err := mapper.RESTMapping(gvk.GroupKind(), gvk.Version)
		if err != nil {
			l.Error(err, "failed to get rest mapping")
			return err
		}

		var dri dynamic.ResourceInterface
		if mapping.Scope.Name() == meta.RESTScopeNameNamespace {
			if unstructuredObj.GetNamespace() == "" {
				unstructuredObj.SetNamespace("default")
			}
			dri = dd.Resource(mapping.Resource).Namespace(unstructuredObj.GetNamespace())
		} else {
			dri = dd.Resource(mapping.Resource)
		}

		obj2, err := dri.Apply(context.Background(), unstructuredObj.GetName(), unstructuredObj, metav1.ApplyOptions{
			FieldManager: "pt-admin",
		})
		if err != nil {
			l.Error(err, "failed to apply object")
			return err
		}
		l.Info("applied object", "kind", obj2.GetKind(), "name", obj2.GetName())
	}
	return nil
}

func CreateYaml2K8s(ctx context.Context, caText64 string, gkeEndpoint string, file string) error {
	l := log.FromContext(ctx)
	l.Info("apply yaml to k8s", "file", file)

	filebytes, err := ioutil.ReadFile(file)
	if err != nil {
		l.Error(err, "failed to read file")
		return err
	}

	return CreateBytes2K8s(ctx, caText64, gkeEndpoint, filebytes)
}

func DeletePtTask(ctx context.Context, caText64 string, gkeEndpoint string, name string, ns string) error {
	l := log.FromContext(ctx).WithName("DeletePtTask")

	_, clientSet, err := Kube2Client(ctx, caText64, gkeEndpoint)
	if err != nil {
		l.Error(err, "failed to get clientset")
		return err
	}
	return clientSet.AppsV1().Deployments(ns).Delete(ctx, name, metav1.DeleteOptions{})
}
