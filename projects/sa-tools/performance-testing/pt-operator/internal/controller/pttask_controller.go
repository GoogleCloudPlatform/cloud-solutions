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

package controller

import (
	"bytes"
	"context"
	"errors"
	"io"
	"io/ioutil"
	"math"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/google/uuid"
	"sigs.k8s.io/yaml"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/labels"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/selection"
	"k8s.io/apimachinery/pkg/types"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/log"

	"cloud.google.com/go/storage"
	perftestv1 "com.google.cloud.solutions.satools/pt-operator/api/v1"
	"com.google.cloud.solutions.satools/pt-operator/internal/helper"
)

// PtTaskReconciler reconciles a PtTask object
type PtTaskReconciler struct {
	client.Client
	Scheme *runtime.Scheme
}

//+kubebuilder:rbac:groups=perftest.com.google.cloud.solutions.satools,resources=pttasks,verbs=get;list;watch;create;update;patch;delete
//+kubebuilder:rbac:groups=perftest.com.google.cloud.solutions.satools,resources=pttasks/status,verbs=get;update;patch
//+kubebuilder:rbac:groups=perftest.com.google.cloud.solutions.satools,resources=pttasks/finalizers,verbs=update
//+kubebuilder:rbac:groups="",resources=pods,verbs=get;list;watch;create;update;patch;delete
//+kubebuilder:rbac:groups="",resources=services,verbs=get;list;watch;create;update;patch;delete

// Reconcile is part of the main kubernetes reconciliation loop which aims to
// move the current state of the cluster closer to the desired state.

// For more details, check Reconcile and its Result here:
// - https://pkg.go.dev/sigs.k8s.io/controller-runtime@v0.14.1/pkg/reconcile
func (r *PtTaskReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	l := log.FromContext(ctx)

	// Process for PtTask
	var pTask perftestv1.PtTask
	if err := r.Get(ctx, req.NamespacedName, &pTask); err != nil {
		l.Info("unable to fetch PtTask")

	} else {
		// Set the Id for PtTask
		if pTask.Status.Id == "" {
			id := uuid.New().String()
			// If the executionId is set in the annotation, use it
			if eId, ok := pTask.Annotations["pttask/executionId"]; ok {
				id = eId
			}

			// Update status/id of PtTask
			pTask.Status.Id = id
			pTask.Status.PtStatus = perftestv1.PT_STATUS_INITIAL
			update2ptadmin(ctx, pTask.Annotations["pttask/callback"], pTask.Annotations["pttask/correlationId"], pTask.Status.PtStatus)
			l.Info("Update status of PtTask", "Id", pTask.Status.Id, "PtStatus", pTask.Status.PtStatus)

			if err = r.Client.Status().Update(context.Background(), &pTask); err != nil {
				l.Info("failed to update status of ptTask")
				return ctrl.Result{}, err
			}
		}

		// Process the execution
		for _, xe := range pTask.Spec.Execution {

			l.Info("Process ptTask in progress")
			switch xe.Executor {
			case "locust":
				l.Info("Provisioning for Locust")
				go func(sxe perftestv1.PtTaskExecution) {
					l.Info("Provisioning for Locust", "scenario", sxe.Scenario, "workers", sxe.Workers)
					trsConf, _ := yaml.Marshal(pTask.Spec)
					// l.Info("BO:")
					l.Info(string(trsConf))
					// l.Info("EO:")
					if !(pTask.Status.Phases != nil && pTask.Status.Phases[sxe.Scenario] == perftestv1.PT_STATUS_FINISHED) {
						if ph, err := do4Locust(ctx, r, req, &pTask, sxe.Scenario, sxe.Workers); err != nil {
							l.Error(err, "failed to provision/execute Locust", "phase", ph)
							updateStatus(ctx, r, sxe.Scenario, req.NamespacedName, ph, "")
						} else {
							updateStatus(ctx, r, sxe.Scenario, req.NamespacedName, ph, "")
						}
						l.Info("Provisioning for Locust is succeeded", "scenario", sxe.Scenario, "workers", sxe.Workers)
					}
				}(xe)

			case "jmeter":
				l.Info("Provisioning for JMeter")
			default:
				l.Info("The testing framework wasn't supported yet", "framework", pTask.Spec.Execution[0].Executor)
			}
		}
	}

	return ctrl.Result{}, nil
}

// Update the status of PtTask, including phase, archive, and ptStatus
func updateStatus(ctx context.Context, r *PtTaskReconciler, scenario string, nn types.NamespacedName, ph string, arch string) error {
	l := log.FromContext(ctx)
	l.Info("Update status of PtTask", "scenario", scenario, "ph", ph, "arch", arch)
	var pTask perftestv1.PtTask
	if err := r.Get(ctx, nn, &pTask); err != nil {
		l.Error(err, "unable to fetch PtTask", "name", nn.Name, "namespace", nn.Namespace)
		return err
	}
	if pTask.Status.Phases == nil && ph != "" {
		pTask.Status.Phases = make(map[string]string)
	}
	if pTask.Status.Archives == nil && arch != "" {
		pTask.Status.Archives = make(map[string]string)
	}
	if ph != "" {
		pTask.Status.Phases[scenario] = ph
		if strings.HasPrefix(ph, "PROVISIONING_") {
			pTask.Status.PtStatus = perftestv1.PT_STATUS_PENDING
		} else {
			pTask.Status.PtStatus = ph
		}
		l.Info("Update phase of status", "scenario", scenario, "phase", ph)
	}
	if arch != "" {
		pTask.Status.Archives[scenario] = arch
		l.Info("Update archive of status", "scenario", scenario, "archive", arch)
	}

	update2ptadmin(ctx, pTask.Annotations["pttask/callback"], pTask.Annotations["pttask/correlationId"], pTask.Status.PtStatus)
	if err := r.Client.Status().Update(context.Background(), &pTask); err != nil {
		l.Error(err, "failed to update status of ptTask", "scenario", scenario)
		return err
	}
	return nil
}

func do4Locust(ctx context.Context, ptr *PtTaskReconciler, req ctrl.Request, pTask *perftestv1.PtTask, scenario string, workerNum int) (string, error) {
	l := log.FromContext(ctx)
	// masterImage := "asia-docker.pkg.dev/play-api-service/test-images/taurus-base"
	// workerImage := "asia-docker.pkg.dev/play-api-service/test-images/locust-worker"

	// 1. Create Locust master Pod
	phase := perftestv1.PT_STATUS_PROVISIONING_MASTER
	trsConf, _ := yaml.Marshal(pTask.Spec)
	mp := helper.BuildMasterPod4Locust(req.Namespace, pTask.Spec.Images[scenario].MasterImage, pTask.Status.Id, scenario, string(trsConf))
	mpNN := types.NamespacedName{
		Name:      mp.Name,
		Namespace: mp.Namespace,
	}
	var xMp = corev1.Pod{}
	if err := ptr.Get(ctx, mpNN, &xMp); err != nil {
		l.Info("master pod wasn't existed", "name", mp.Name, "namespace", mp.Namespace)
		l.Info("Create master pod", "name", mp.Name, "namespace", mp.Namespace)
		if err := ctrl.SetControllerReference(pTask, mp, ptr.Scheme); err != nil {
			l.Error(err, "unable to set OwnerReferences to master pod", "name", mp.Name, "namespace", mp.Namespace)
			return phase, err
		}
		if err := ptr.Create(ctx, mp); err != nil {
			l.Error(err, "failed to create Pod for master node of Locust")
			return phase, err
		}

	} else {
		l.Info("master node was existed", "name", mp.Name, "namespace", mp.Namespace)

	}

	// 2. Create Locust master service for Pod
	ms := helper.BuildMasterService4Locust(req.Namespace, corev1.ServiceTypeClusterIP, scenario)
	if pTask.Spec.Type == "Distribution" {
		ms.Spec.Type = corev1.ServiceTypeLoadBalancer
	}
	msNN := types.NamespacedName{
		Name:      ms.Name,
		Namespace: ms.Namespace,
	}
	var xMs = corev1.Service{}
	if err := ptr.Get(ctx, msNN, &xMs); err != nil {
		l.Info("master svc wasn't existed", "name", ms.Name, "namespace", ms.Namespace)
		l.Info("Create master svc", "name", ms.Name, "namespace", ms.Namespace)
		if err := ctrl.SetControllerReference(pTask, ms, ptr.Scheme); err != nil {
			l.Error(err, "unable to set OwnerReferences to master service", "name", ms.Name, "namespace", ms.Namespace)
			updateStatus(ctx, ptr, scenario, req.NamespacedName, perftestv1.PT_STATUS_FAILED, "")
			return phase, err
		}
		if err := ptr.Create(ctx, ms); err != nil {
			l.Error(err, "failed to create Service for master node of Locust")
			updateStatus(ctx, ptr, scenario, req.NamespacedName, perftestv1.PT_STATUS_FAILED, "")
			return phase, err
		}
	} else {
		l.Info("master svc was existed", "name", xMs.Name, "namespace", xMs.Namespace)
	}

	// 4. Create Locust worker Pods as demand if locust master is ready
	svcHost := ""
	svcPort := ""
	isReady := false
	// Check if the master service is ready: max 100 times, 5 seconds per time
	for int := 0; int < 100; int++ {
		isReady, svcHost, svcPort = checkLocustMaster(ctx, ptr, req, mpNN, msNN)
		if !isReady {
			time.Sleep(5 * time.Second)
		} else {
			break
		}
	}
	if !isReady {
		l.Error(errors.New("master service for Locust is not ready"), "failed to create master service")
		return phase, errors.New("master service for Locust is not ready")
	}
	l.Info("master service for Locust is ready", "host", svcHost, "port", svcPort)
	go MonitorLocustMaster(scenario, ptr, mpNN)

	phase = perftestv1.PT_STATUS_PROVISIONING_WORKER
	// Creat multiple workers
	l.Info("Provision workers", "type", pTask.Spec.Type)
	if pTask.Spec.Type == "Local" {
		// Local
		for i := 1; i < workerNum+1; i++ {
			worker := helper.BuildLocusterWorker4Locust(req.Namespace, pTask.Spec.Images[scenario].WorkerImage, svcHost, svcPort, scenario, strconv.Itoa(i))
			workerNN := types.NamespacedName{
				Name:      worker.Name,
				Namespace: worker.Namespace,
			}
			if err := ptr.Get(ctx, workerNN, &corev1.Pod{}); err != nil {
				l.Info("Provision workers in the same cluster")
				l.Info("worker pod wasn't existed", "name", worker.Name, "namespace", worker.Namespace)
				l.Info("Create worker pod", "name", worker.Name, "namespace", worker.Namespace)
				if err := ctrl.SetControllerReference(pTask, worker, ptr.Scheme); err != nil {
					l.Error(err, "unable to set OwnerReferences to worker pod", "name", worker.Name, "namespace", worker.Namespace)
					updateStatus(ctx, ptr, scenario, req.NamespacedName, perftestv1.PT_STATUS_FAILED, "")
					return phase, err
				}
				if err := ptr.Create(ctx, worker); err != nil {
					l.Error(err, "failed to create Pod for worker node of Locust", "worker", worker.ObjectMeta.Name)
					updateStatus(ctx, ptr, scenario, req.NamespacedName, perftestv1.PT_STATUS_FAILED, "")
					return phase, err
				}
			} else {
				l.Info("worker node was existed", "name", worker.Name, "namespace", worker.Namespace)
			}
		}
		// Monitor the status of the worker locally
		go MonitorLocustLocalWorker(scenario, ptr, req.Namespace)

	} else if pTask.Spec.Type == "Distribution" {
		// Distribution
		l.Info("Provision workers in the different clusters")
		for _, e := range pTask.Spec.Execution {
			if e.Scenario == scenario {
				//provision workers in different clusters
				if ts, ok := pTask.Spec.Traffics[scenario]; ok {
					for _, t := range ts {
						n := int(math.Floor((float64(e.Workers * int(t.Percent) / 100)) + 0.5))

						l.Info("Provison worker in different region", "region", t.Region)
						_, k2c, err := helper.Kube2Client(ctx, t.GKECA64, t.GKEEndpoint)
						if err != nil {
							l.Error(err, "unable to connect with GKE cluster", "region", t.Region, "endpoint", t.GKEEndpoint)
							updateStatus(ctx, ptr, scenario, req.NamespacedName, perftestv1.PT_STATUS_FAILED, "")
							return phase, err
						}
						for i := 1; i < n+1; i++ {

							worker := helper.BuildLocusterWorker4Locust("default", pTask.Spec.Images[scenario].WorkerImage, svcHost, svcPort, scenario, strconv.Itoa(i))
							if _, err := k2c.CoreV1().Pods("default").Get(ctx, worker.Name, metav1.GetOptions{}); err != nil {
								l.Info("Provision workers in the different cluster")
								l.Info("worker pod wasn't existed", "name", worker.Name, "namespace", "default")
								l.Info("Create worker pod", "name", worker.Name, "namespace", "default")
								if _, err := k2c.CoreV1().Pods("default").Create(ctx, worker, metav1.CreateOptions{}); err != nil {
									l.Error(err, "unable to create worker in GKE cluster", "region", t.Region, "endpoint", t.GKEEndpoint)
									updateStatus(ctx, ptr, scenario, req.NamespacedName, perftestv1.PT_STATUS_FAILED, "")
									return phase, err
								}
							}

							// Monitor the worker in the target clutser
							go MonitorLocustDistributionWorker(scenario, strconv.Itoa(i), t.GKECA64, t.GKEEndpoint)

						}
						l.Info("The worker has been provisoned in target region", "region", t.Region, "endpoint", t.GKEEndpoint)
					}
				}
			}
		}
	}

	// 5. Kick off monitoring and keep update along the way
	// 5.1 Checking out testing kicked off
	// 5.2 Starting to aggreagete metrics
	phase = perftestv1.PT_STATUS_TESTING
	updateStatus(ctx, ptr, scenario, types.NamespacedName{Name: pTask.Name, Namespace: pTask.Namespace}, phase, "")
	if pTask.Spec.TestingOutput.Ldjson != "" {
		l.Info("local debug mode", "ldjson", pTask.Spec.TestingOutput.Ldjson)
		go MonitorLocustTesting(scenario, pTask.Spec.TestingOutput.Ldjson)
	} else {
		ldjson := "/taurus-logs/" + pTask.Status.Id + "/" + scenario + "/locust-workers.ldjson"
		l.Info("monitoring testing logs", "ldjson", ldjson)
		go MonitorLocustTesting(scenario, ldjson)
	}

	// TODO: 6. House keeping after testing
	// 6.1 waiting to finish
	// 6.2 Achieving logs/reports
	// 6.3 Mark PtTask was done
	// 6.4 Singal to clean up all related resources except metadata store & GCS
	go checkMasterStatus(ptr, pTask)

	return phase, nil
}

func checkMasterStatus(ptr *PtTaskReconciler, pTask *perftestv1.PtTask) {
	ctx := context.Background()
	l := log.Log.WithName("checkMasterStatus")
	for {
		var pods corev1.PodList
		rl, _ := labels.NewRequirement("app", selection.Equals, []string{"locust-master"})
		if err := ptr.List(ctx, &pods, &client.ListOptions{Namespace: pTask.Namespace, LabelSelector: labels.NewSelector().Add(*rl)}); err != nil {
			l.Error(err, "unable to list pods in namespace", "namespace", pTask.Namespace)
		} else {
			isAllDone := len(pods.Items)
			l.Info("check the number of locust master", "count", isAllDone)
			for _, p := range pods.Items {
				for _, st := range p.Status.ContainerStatuses {
					if strings.Contains(st.Name, "locust-master") {
						scenario := strings.Replace(st.Name, "locust-master-", "", 1)
						if st.State.Terminated != nil {
							if st.State.Terminated.Reason == "Completed" {
								l.Info("locust master is completed", "name", p.Name, "namespace", p.Namespace)
								//TODO: Archive the logs into GCS
								ptr.Get(ctx, types.NamespacedName{Name: pTask.Name, Namespace: pTask.Namespace}, pTask)
								if pTask.Status.Archives != nil && pTask.Status.Archives[scenario] != "" {
									l.Info("the logs are already archived into GCS", "scenario", scenario)
									isAllDone--
									continue
								}
								l.Info("archive logs into GCS", "scenario", scenario)
								src := "/taurus-logs/" + pTask.Status.Id + "/" + scenario
								dst := pTask.Status.Id + "/" + scenario
								if pTask.Spec.TestingOutput.LogDir != "/taurus-logs" {
									src = pTask.Spec.TestingOutput.LogDir
								}
								if err := copyFileToGCS(ctx, src, pTask.Spec.TestingOutput.Bucket, dst); err != nil {
									l.Error(err, "unable to copy logs into GCS", "scenario", scenario)
								} else {
									l.Info("logs are archived into GCS", "scenario", scenario)
								}

								//TODO: Mark the PtTask as done
								l.Info("the scenario is succeeded in PtTask", "scenario", scenario)
								updateStatus(ctx, ptr, scenario, types.NamespacedName{Name: pTask.Name, Namespace: pTask.Namespace}, perftestv1.PT_STATUS_FINISHED, time.Now().String())
								isAllDone--
							}
						}
					}
				}
			}
			if isAllDone == 0 {
				//TODO: Singal to clean up all related resources except metadata store & GCS
				l.Info("singal to clean up all related resources")
				break
			}
		}
		time.Sleep(20 * time.Second)
	}

}

// Checking status of master whether it should launch worker nodes
func checkLocustMaster(ctx context.Context, ptr *PtTaskReconciler, req ctrl.Request, masterNN types.NamespacedName, masterSNN types.NamespacedName) (bool, string, string) {
	l := log.FromContext(ctx)

	var masterPod corev1.Pod
	var masterSvc corev1.Service
	if err := ptr.Get(ctx, masterNN, &masterPod); err != nil {
		l.Error(err, "unable to fetch Pod for master node", "name", masterNN.Name, "namespace", masterNN.Namespace)
	} else {
		for _, cs := range masterPod.Status.ContainerStatuses {
			if *cs.Started && cs.Ready {
				if err := ptr.Get(ctx, masterSNN, &masterSvc); err != nil {
					l.Error(err, "unable to fetch Service for master node", "name", masterSNN.Name, "namespace", masterSNN.Namespace)
				} else {
					if masterSvc.Spec.Type == corev1.ServiceTypeClusterIP {
						return true, masterSvc.Spec.ClusterIP, strconv.Itoa(int(masterSvc.Spec.Ports[0].Port))
					} else if masterSvc.Spec.Type == corev1.ServiceTypeLoadBalancer {
						if masterSvc.Status.LoadBalancer.Ingress != nil {
							return true, masterSvc.Status.LoadBalancer.Ingress[0].IP, strconv.Itoa(int(masterSvc.Spec.Ports[0].Port))
						}
					}
				}
			}
		}
	}
	return false, "", ""

}

// Achive all testing logs to GCS
func copyFileToGCS(ctx context.Context, src string, bucket string, dst string) error {
	l := log.FromContext(ctx)
	l.Info("copying files to GCS", "src", src, "bucket", bucket, "dst", dst)
	// Using Cloud Storage API
	client, err := storage.NewClient(ctx)
	if err != nil {
		l.Error(err, "unable to create GCS client")
		return err
	}
	defer client.Close()

	// copy all files in the folder to GCS
	files, err := ioutil.ReadDir(src)
	if err != nil {
		l.Error(err, "unable to read local folder", "folder", src)
		return err
	}
	for _, f := range files {
		if f.IsDir() {
			continue
		}
		srcFile := src + "/" + f.Name()
		dstFile := dst + "/" + f.Name()
		l.Info("copying file to GCS", "src", srcFile, "dst", dstFile)
		fh, err := os.Open(srcFile)
		if err != nil {
			l.Error(err, "unable to open local file", "file", srcFile)
			return err
		}
		wc := client.Bucket(bucket).Object(dstFile).NewWriter(ctx)
		if _, err = io.Copy(wc, fh); err != nil {
			l.Error(err, "unable to copy file to GCS", "src", srcFile, "dst", dstFile)
			return err
		}
		if err := wc.Close(); err != nil {
			l.Error(err, "unable to close GCS writer", "src", srcFile, "dst", dstFile)
			return err
		}
	}
	return nil
}

// SetupWithManager sets up the controller with the Manager.
func (r *PtTaskReconciler) SetupWithManager(mgr ctrl.Manager) error {

	return ctrl.NewControllerManagedBy(mgr).
		For(&perftestv1.PtTask{}).
		Complete(r)
}

func update2ptadmin(ctx context.Context, url string, correlationId string, status string) {
	l := log.FromContext(ctx)
	l.Info("callback to send status to ptadmin")
	if url != "" && correlationId != "" && status != "" {
		l.Info("sending status to ptadmin", "url", url, "correlationId", correlationId, "status", status)
		client := &http.Client{}
		req, err := http.NewRequest("PATCH", url+"/v1/update/pttask/"+correlationId, bytes.NewBuffer([]byte(status)))
		if err != nil {
			l.Error(err, "unable to create request to ptadmin")
			return
		}
		req.Header.Set("Content-Type", "text/plain")

		resp, err := client.Do(req)
		if err != nil {
			l.Error(err, "unable to send request to ptadmin")
			return
		}
		defer resp.Body.Close()
		l.Info("response from ptadmin", "status", resp.Status)
	}
}
