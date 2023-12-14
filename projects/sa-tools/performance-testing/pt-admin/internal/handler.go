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

package internal

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/ioutil"
	"math"
	"math/rand"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	cloudbuild "cloud.google.com/go/cloudbuild/apiv1/v2"
	cloudbuildpb "cloud.google.com/go/cloudbuild/apiv1/v2/cloudbuildpb"
	"cloud.google.com/go/container/apiv1/containerpb"
	"cloud.google.com/go/pubsub"
	run "cloud.google.com/go/run/apiv2"
	runpb "cloud.google.com/go/run/apiv2/runpb"
	"google.golang.org/protobuf/types/known/timestamppb"

	// dashboard "cloud.google.com/go/monitoring/dashboard/apiv1"
	// dashboardpb "cloud.google.com/go/monitoring/dashboard/apiv1/dashboardpb"
	"cloud.google.com/go/storage"
	wfexecpb "cloud.google.com/go/workflows/executions/apiv1/executionspb"

	"com.google.cloud.solutions.satools/pt-admin/api"
	"com.google.cloud.solutions.satools/pt-admin/internal/helper"
	"github.com/gin-gonic/gin"

	"github.com/google/uuid"
	"gopkg.in/yaml.v3"
	"sigs.k8s.io/controller-runtime/pkg/log"
)

/////////////////////
// Operations for provison infrastructure
// 0. Build container images for the following testing task
// 1. Create a VPC network if not exist* - do it when install Pt-Admin
// 2. Create a Service Account for the GKE Autopilot cluster*  - do it when install Pt-Admin

// 3. Create a GKE Autopilot cluster
// 4. Retrieve the GKE Autopilot cluster's CA certificate & IP address
// 5. Configure Storage Class in the GKE Autopilot cluster
// 6. Configure PV in the GKE Autopilot cluster
// 7. Binding service sccount with GSA (Workload Identity)
// 8. Deploy pt-operator to the GKE Autopilot cluster

//7. Apply PtTask to the GKE Autopilot cluster
/////////////////////

func CreateVPC(ctx context.Context, c *gin.Context) (*helper.VPC, error) {
	l := log.FromContext(ctx).WithName("CreateVPC")
	ti := &helper.TInfra{}
	var input helper.VPC
	buf, err := io.ReadAll(c.Request.Body)
	if err != nil {
		return &helper.VPC{}, err
	}
	err = json.Unmarshal(buf, &input)
	if err != nil {
		return &helper.VPC{}, err
	}
	l.Info("Unmarshal buf", "buf", input)
	err = ti.CreateVPCNetwork(ctx, input.ProjectID, input.Network, input.Mtu)
	if err != nil {
		return &helper.VPC{}, err
	}
	return &input, nil
}

func CreateServiceAccount(ctx context.Context, c *gin.Context) (*helper.ServiceAccount, error) {
	ti := &helper.TInfra{}
	var input helper.ServiceAccount
	buf, err := io.ReadAll(c.Request.Body)
	if err != nil {
		return &helper.ServiceAccount{}, err
	}
	err = json.Unmarshal(buf, &input)
	if err != nil {
		return &helper.ServiceAccount{}, err
	}
	// Create Service Account
	_, err = ti.CreateServiceAccount(ctx, input.ProjectID, input.AccountID)
	if err != nil {
		return &helper.ServiceAccount{}, err
	}
	// Grant roles to Service Account
	err = ti.SetIamPolicies2SA(ctx, input.ProjectID, input.AccountID)
	if err != nil {
		return &helper.ServiceAccount{}, err
	}

	return &input, nil
}

func CreateServiceAccountKey(ctx context.Context, c *gin.Context) (*helper.ServiceAccount, error) {
	ti := &helper.TInfra{}
	var input helper.ServiceAccount
	buf, err := io.ReadAll(c.Request.Body)
	if err != nil {
		return &input, err
	}
	err = json.Unmarshal(buf, &input)
	if err != nil {
		return &input, err
	}
	key, err := ti.CreateServiceAccountKey(ctx, input.ProjectID, input.AccountID)
	if err != nil {
		return &input, err
	}
	input.Key = string(key.PrivateKeyData)
	return &input, nil
}

func CreateGKEAutopilotCluster(ctx context.Context, c *gin.Context) ([]helper.GKE, error) {
	ti := &helper.TInfra{}
	var input []helper.GKE
	buf, err := io.ReadAll(c.Request.Body)
	if err != nil {
		return []helper.GKE{}, err
	}
	err = json.Unmarshal(buf, &input)
	if err != nil {
		return []helper.GKE{}, err
	}
	// Return array of GKE with operationId, if operationId is empty, it means the cluster is existed
	var observed []helper.GKE
	for _, gke := range input {
		op, err := ti.CreateAutopilotCluster(ctx, gke.ProjectID, gke.Cluster, gke.Location, gke.Network, gke.Subnetwork, gke.AccountID)
		if err != nil {
			return []helper.GKE{}, err
		}
		if op.Name != "" {
			gke.OperationID = op.Name
			observed = append(observed, gke)
		} else {
			gke.Status = "DONE"
			observed = append(observed, gke)
		}
	}
	return observed, nil

}

func CheckClusterStatus(ctx context.Context, c *gin.Context) ([]helper.GKE, error) {
	l := log.FromContext(ctx).WithName("CheckClusterStatus")
	ti := &helper.TInfra{}
	var input []helper.GKE
	buf, err := io.ReadAll(c.Request.Body)
	if err != nil {
		return input, err
	}
	err = json.Unmarshal(buf, &input)
	if err != nil {
		l.Error(err, "json.Unmarshal", "buf", string(buf))
		return input, err
	}
	var observed []helper.GKE
	for _, gke := range input {
		if gke.Status != "DONE" {
			op, err := ti.AutopilotClusterStatus(ctx, gke.ProjectID, gke.Location, gke.OperationID)
			if err != nil {
				l.Error(err, "AutopilotClusterStatus")
				return input, err
			}

			if op.Status == containerpb.Operation_DONE {
				gke.Status = "DONE"
			} else {
				gke.Status = "IN_PROGRESS"
			}
			observed = append(observed, gke)
		}
	}

	// Check if all cluster is ready
	isAll := true
	for _, gke := range observed {
		if gke.Status != "DONE" {
			isAll = false
			break
		}
	}
	if isAll {
		return []helper.GKE{}, nil
	}
	return observed, nil

}

func RetrieveClusterInfo(ctx context.Context, c *gin.Context) ([]helper.GKE, error) {
	ti := &helper.TInfra{}
	var input []helper.GKE
	buf, err := io.ReadAll(c.Request.Body)
	if err != nil {
		return input, err
	}
	err = json.Unmarshal(buf, &input)
	if err != nil {
		return input, err
	}
	var observed []helper.GKE
	for _, gke := range input {
		ca, err := ti.GetClusterCaCertificate(ctx, gke.ProjectID, gke.Cluster, gke.Location)
		if err != nil {
			return input, err
		}
		gke.Certificate = ca
		ip, err := ti.GetClusterEndpoint(ctx, gke.ProjectID, gke.Cluster, gke.Location)
		if err != nil {
			return input, err
		}
		gke.Endpoint = ip
		observed = append(observed, gke)
	}
	return observed, nil
}

func ApplyManifest(ctx context.Context, c *gin.Context) error {
	l := log.FromContext(ctx).WithName("ApplyManifest")
	var gke helper.GKE
	file := c.Param("file")
	region := os.Getenv("LOCATION")

	buf, err := io.ReadAll(c.Request.Body)
	if err != nil {
		l.Error(err, "io.ReadAll")
		return err
	}
	err = json.Unmarshal(buf, &gke)
	if err != nil {
		l.Error(err, "json.Unmarshal", "buf", string(buf))
		return err
	}

	if file == "pt-operator.yaml" || file == "sc.yaml" {
		nfile, err := replaceEnvs(ctx, file, gke.AccountID, gke.ProjectID, region, gke.Network, "")
		if err != nil {
			l.Error(err, "replaceEnvs", "file", file)
			return err
		}
		file = nfile
	} else {
		file = "/manifests/" + file
	}
	err = helper.CreateYaml2K8s(ctx, gke.Certificate, gke.Endpoint, file)
	if err != nil {
		l.Error(err, "ApplyYaml2K8s", "file", file)
		return err
	}

	return nil
}

func BindingWorkloadIdentity(ctx context.Context, c *gin.Context) error {
	ti := &helper.TInfra{}
	var sa helper.ServiceAccount
	buf, err := io.ReadAll(c.Request.Body)
	if err != nil {
		return err
	}
	err = json.Unmarshal(buf, &sa)
	if err != nil {
		return err
	}

	return ti.SetIamPolicies2KSA(ctx, sa.ProjectID, "pt-system", "pt-operator-controller-manager")

}

func replaceEnvs(ctx context.Context, file, sa, projectID, region, network, ptName string) (string, error) {
	l := log.FromContext(ctx).WithName("replaceEnvs")
	buf, err := ioutil.ReadFile("/manifests/" + file)
	if err != nil {
		l.Error(err, "ReadFile")
		return "", err
	}
	newContents := string(buf)
	if sa != "" {
		newContents = strings.Replace(newContents, "${SA_NAME}", sa, -1)
	}
	if projectID != "" {
		newContents = strings.Replace(newContents, "${PROJECT_ID}", projectID, -1)
	}
	if region != "" {
		newContents = strings.Replace(newContents, "${REGION}", region, -1)
	}
	if network != "" {
		newContents = strings.Replace(newContents, "${NETWORK}", network, -1)
	}
	if ptName != "" {
		newContents = strings.Replace(newContents, "${PT_TASK_NAME}", ptName, -1)
	}

	// TODO: It's a specific path "/var/tmp/" for Cloud Run
	out := "/var/tmp/" + file + "-" + strconv.FormatInt(time.Now().UnixNano(), 10) + ".yaml"
	err = ioutil.WriteFile(out, []byte(newContents), 0)
	if err != nil {
		l.Error(err, "WriteFile")
		return "", err
	}

	return out, nil
}

func GetPVCStatus(ctx context.Context, c *gin.Context) (map[string]string, error) {
	l := log.FromContext(ctx).WithName("GetPVCStatus")
	var gke helper.GKE
	buf, err := io.ReadAll(c.Request.Body)
	if err != nil {
		l.Error(err, "io.ReadAll")
		return map[string]string{}, err
	}
	err = json.Unmarshal(buf, &gke)
	if err != nil {
		l.Error(err, "json.Unmarshal", "buf", string(buf))
		return map[string]string{}, err
	}

	pvc, err := helper.StatusOfPVC(ctx, gke.Certificate, gke.Endpoint, "pt-system", "bzt-filestore-pvc")
	if err != nil {
		l.Error(err, "StatusOfPVC")
		return map[string]string{}, err
	}
	if pvc.Status.Phase == "Bound" {
		return map[string]string{"status": "DONE"}, nil
	}
	return map[string]string{"status": "IN_PROGRESS"}, nil

}

func GetPtOperatorStatus(ctx context.Context, c *gin.Context) (map[string]string, error) {
	l := log.FromContext(ctx).WithName("GetPtOperatorStatus")
	var gke helper.GKE
	buf, err := io.ReadAll(c.Request.Body)
	if err != nil {
		l.Error(err, "io.ReadAll")
		return map[string]string{}, err
	}
	err = json.Unmarshal(buf, &gke)
	if err != nil {
		l.Error(err, "json.Unmarshal", "buf", string(buf))
		return map[string]string{}, err
	}

	dep, err := helper.StatusOfDeployment(ctx, gke.Certificate, gke.Endpoint, "pt-system", "pt-operator-controller-manager")
	if err != nil {
		l.Error(err, "StatusOfPod")
		return map[string]string{}, err
	}
	if dep.Status.Replicas == 1 {
		return map[string]string{"status": "DONE"}, nil
	}
	return map[string]string{"status": "IN_PROGRESS"}, nil

}

// Record the execution of a workflow
func RecordWorkflow(ctx context.Context, c *gin.Context) error {
	l := log.FromContext(ctx).WithName("RecordWorkflow")
	var pwf helper.ProvisionWf
	// The name of the workflow to be executed
	wf := c.Param("wf")
	eID := c.Param("executionId")
	buf, err := io.ReadAll(c.Request.Body)
	if err != nil {
		l.Error(err, "io.ReadAll")
		return err
	}
	err = json.Unmarshal(buf, &pwf)
	if err != nil {
		l.Error(err, "json.Unmarshal", "buf", string(buf))
		return err
	}

	// Save executionId to Firestore
	_, err = helper.Insert(ctx, pwf.ProjectID, "pt-transactions", helper.PtTransaction{
		CorrelationID:      pwf.CorrelationID,
		Created:            pwf.OriginLaunchedTask.Created,
		LastUpdated:        pwf.OriginLaunchedTask.LastUpdated,
		ExecutionID:        eID,
		WorkflowName:       wf,
		Input:              pwf,
		WorkflowStatus:     api.WorkflowStatus_PROVISIONING.String(),
		OriginTaskRequest:  pwf.OriginTaskRequest,
		OriginLaunchedTask: pwf.OriginLaunchedTask,
		CreatorEmail:       pwf.CreatorEmail,
	})
	if err != nil {
		l.Error(err, "failed to insert PtTransaction to Firestore")
		return err
	}
	return nil

}

// Execute the workflow to provision all related resources and apply PtTask to run a Performance Test
func ExecWorkflow(ctx context.Context, c *gin.Context) error {
	l := log.FromContext(ctx).WithName("ExecWorkflow")
	ti := &helper.TInfra{}
	var pwf helper.ProvisionWf
	// The name of the workflow to be executed
	wf := c.Param("wf")
	buf, err := io.ReadAll(c.Request.Body)
	if err != nil {
		l.Error(err, "io.ReadAll")
		return err
	}
	err = json.Unmarshal(buf, &pwf)
	if err != nil {
		l.Error(err, "json.Unmarshal", "buf", string(buf))
		return err
	}
	err = ti.ExecWorkflow(ctx, pwf.ProjectID, wf, buf)
	if err != nil {
		l.Error(err, "ti.ExecWorkflow")
		return err
	}

	return nil

}

func StatusWorkflow(ctx context.Context, c *gin.Context) (map[string]string, error) {
	l := log.FromContext(ctx).WithName("StatusWorkflow")
	ti := &helper.TInfra{}
	ex, err := ti.StatusWorkflow(ctx, c.Param("projectId"), c.Param("region"), c.Param("workflow"), c.Param("executionId"))
	if err != nil {
		l.Error(err, "ti.StatusWorkflow")
		return map[string]string{}, err
	}
	l.Info("StatusWorkflow", "startTime", ex.StartTime.String())
	return map[string]string{"status": wfexecpb.Execution_State_name[int32(ex.State.Number())]}, nil

}

func CreateDashboard(ctx context.Context, c *gin.Context) (string, error) {
	l := log.FromContext(ctx).WithName("CreateDashboard")
	dID := ""
	projectID := c.Param("projectId")
	correlationID := c.Param("correlationId")
	// var token *oauth2.Token
	url := fmt.Sprintf("https://monitoring.googleapis.com/v1/projects/%s/dashboards", projectID)

	// Get access token
	// curl "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token" \
	// --header "Metadata-Flavor: Google"
	aReq, err := http.NewRequest("GET", "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token", nil)
	if err != nil {
		l.Error(err, "http.NewRequest")
		return dID, err
	}
	aReq.Header.Add("Metadata-Flavor", "Google")
	aClient := &http.Client{}
	aResp, err := aClient.Do(aReq)
	if err != nil {
		l.Error(err, "aClient.Do")
		return dID, err
	}
	defer aResp.Body.Close()
	aBody, err := ioutil.ReadAll(aResp.Body)
	if err != nil {
		l.Error(err, "ioutil.ReadAll")
		return dID, err
	}
	var aRespBody map[string]interface{}
	err = json.Unmarshal(aBody, &aRespBody)
	if err != nil {
		l.Error(err, "json.Unmarshal")
		return dID, err
	}
	// curl -d @my-dashboard.json
	// -H "Authorization: Bearer $(gcloud auth print-access-token)"
	// -H 'Content-Type: application/json'
	// -X POST https://monitoring.googleapis.com/v1/projects/${PROJECT_ID}/dashboards
	// net/http post
	dFile, err := replaceEnvs(ctx, "dashboard.json", "", "", "", "", correlationID)
	if err != nil {
		l.Error(err, "replaceEnvs")
		return dID, err
	}
	dash, err := ioutil.ReadFile(dFile)
	if err != nil {
		l.Error(err, "ioutil.ReadFile")
		return dID, err
	}
	req, err := http.NewRequest("POST", url, bytes.NewBuffer(dash))
	if err != nil {
		l.Error(err, "http.NewRequest")
		return dID, err
	}
	req.Header.Set("Authorization", "Bearer "+fmt.Sprintf("%v", aRespBody["access_token"]))
	req.Header.Set("Content-Type", "application/json")
	client := &http.Client{}
	resp, err := client.Do(req)
	//eg: https://console.cloud.google.com/monitoring/dashboards/builder/db50a4bf-ae14-441f-812d-b01ea471ab42?project=play-api-service
	if err != nil {
		l.Error(err, "client.Do")
		return dID, err
	}
	defer resp.Body.Close()
	l.Info("response Status:", "status", resp.Status)
	buf, err := io.ReadAll(resp.Body)
	if err != nil {
		l.Error(err, "io.ReadAll")
		return dID, err
	}
	// json, cloud be map style
	var mp map[string]interface{}
	err = json.Unmarshal(buf, &mp)
	if err != nil {
		l.Error(err, "json.Unmarshal", "buf", string(buf))
		return dID, err
	}
	// "name": "projects/374299782509/dashboards/fd877f39-6505-4788-86b8-89b49bf43d4a"
	if mp["name"] != nil {
		dName := strings.Split(fmt.Sprintf("%v", mp["name"]), "/")
		dID = dName[len(dName)-1]
		l.Info("Dashboard created", "id", dID)

	}
	// Dashboard URL
	dURL := "https://console.cloud.google.com/monitoring/dashboards/builder/" + dID + "?project=" + projectID
	logURL := "https://console.cloud.google.com/logs/query;query=resource.type%3D%22k8s_cluster%22%0Aresource.labels.cluster_name%3D%22pt-cluster-9uej2d%22?project=" + projectID

	// Save dashboard URL to Firestore
	_, err = helper.UpdateDashboardURL(ctx, projectID, "pt-transactions", correlationID, dURL, logURL)
	if err != nil {
		l.Error(err, "failed to update dashboardUrl to Firestore")
	}
	return dURL, nil
}

func PreparenApplyPtTask(ctx context.Context, c *gin.Context) (*api.PtTask, error) {
	l := log.FromContext(ctx).WithName("PreparePtTask")
	executionID := c.Param("executionId")
	var pwf helper.ProvisionWf
	buf, err := io.ReadAll(c.Request.Body)
	if err != nil {
		l.Error(err, "io.ReadAll")
		return &api.PtTask{}, err
	}
	err = json.Unmarshal(buf, &pwf)
	if err != nil {
		l.Error(err, "json.Unmarshal", "buf", string(buf))
		return &api.PtTask{}, err
	}
	tr := pwf.TaskRequest

	// Calcaulate the number of pods
	var pt *api.PtTask
	name := "pt-task-" + executionID
	scenario := "scenario-" + executionID
	taurusImage := fmt.Sprintf("asia-docker.pkg.dev/%s/%s-pt-images/taurus-base", tr.ProjectID, tr.ProjectID)
	locustImage := fmt.Sprintf("asia-docker.pkg.dev/%s/%s-pt-images/locust-worker", tr.ProjectID, tr.ProjectID)
	workers := tr.NumOfUsers/1000 + 1
	if tr.WorkerNumber > 0 {
		workers = tr.WorkerNumber
	}

	// gzPath, _ := save2gcs(ctx, tr.ProjectId, tr.Script4Task)
	if tr.Executor == "locust" {
		l.Info("Locust PtTask")
		pt = &api.PtTask{
			Kind:       "PtTask",
			APIVersion: "perftest.com.google.cloud.solutions.satools/v1",
			Metadata: api.MyObjectMeta{
				Name:      name,
				Namespace: "pt-system",
				Annotations: map[string]string{
					"pttask/executionId":   executionID,
					"pttask/correlationId": pwf.CorrelationID,
					"pttask/callback":      pwf.URL,
				},
			},
			Spec: api.PtTaskSpec{
				// Type: "Local",
				Execution: []api.PtTaskExecution{
					{
						Executor:    tr.Executor,
						Concurrency: tr.NumOfUsers,
						HoldFor:     strconv.Itoa(tr.Duration) + "m",
						RampUp:      strconv.Itoa(tr.RampUp) + "s",
						Scenario:    scenario,
						Master:      true,
						Workers:     workers,
					},
				},
				Scenarios: map[string]api.PtTaskScenario{
					scenario: {
						Script:         "locustfile.py",
						DefaultAddress: tr.TargetURL,
					},
				},
				Images: map[string]api.PtTaskImages{
					scenario: {
						MasterImage: taurusImage,
						WorkerImage: locustImage,
					},
				},
				TestingOutput: api.PtTaskTestingOutput{
					LogDir: "/taurus-logs",
					Bucket: tr.ArchiveBucket,
				},
			},
		}
		if tr.IsLocal {
			l.Info("Locust PtTask is local...")
			pt.Spec.Type = "Local"
		} else {
			l.Info("Locust PtTask is distributed...")
			pt.Spec.Type = "Distribution"
			for _, gke := range pwf.GKEs {
				if gke.IsMater == "false" {
					ti := &helper.TInfra{}
					ca, err := ti.GetClusterCaCertificate(ctx, gke.ProjectID, gke.Cluster, gke.Location)
					if err != nil {
						return pt, err
					}

					ip, err := ti.GetClusterEndpoint(ctx, gke.ProjectID, gke.Cluster, gke.Location)
					if err != nil {
						return pt, err
					}
					gke.Endpoint = ip

					pt.Spec.Traffics = map[string][]api.PtTaskTraffic{
						scenario: {
							{
								GKECA64:     ca,
								GKEEndpoint: ip,
								Region:      gke.Location,
								Percent:     gke.Percent,
							},
						},
					}
				}
			}

		}
	} else if tr.Executor == "jmeter" {
		l.Info("Jmeter PtTask, still under development")
	}

	for _, gke := range pwf.GKEs {
		if gke.IsMater == "true" {

			// Get GKE credential
			ti := &helper.TInfra{}
			ca, err := ti.GetClusterCaCertificate(ctx, gke.ProjectID, gke.Cluster, gke.Location)
			if err != nil {
				return pt, err
			}
			gke.Certificate = ca
			ip, err := ti.GetClusterEndpoint(ctx, gke.ProjectID, gke.Cluster, gke.Location)
			if err != nil {
				return pt, err
			}
			gke.Endpoint = ip

			// Write yaml file
			buf, err := yaml.Marshal(pt)
			if err != nil {
				l.Error(err, "json.Marshal", "pt", pt)
				return pt, err
			}
			file := fmt.Sprintf("/var/tmp/pt-task-%s.yaml", executionID)
			err = ioutil.WriteFile(file, buf, 0644)
			if err != nil {
				l.Error(err, "ioutil.WriteFile", "file", file)
				return pt, err
			}
			l.Info("WriteFile", "file", file, "buf", string(buf))
			err = helper.CreateYaml2K8s(ctx, gke.Certificate, gke.Endpoint, file)
			if err != nil {
				l.Error(err, "CreateYaml2K8s")
				return pt, err
			}
		}
	}

	// Save PtTask to Firestore
	_, err = helper.UpdatePtTask(ctx, tr.ProjectID, "pt-transactions", pwf.CorrelationID, *pt)
	if err != nil {
		l.Error(err, "failed to update PtTask to Firestore")
	}
	return pt, nil
}

// Build images from content of script and base image, and go through the following processes:
//  1. extract script files from tgz
//  2. add docker file
//  3. tar the files to tgz
//  4. save the tgz to gcs
//  5. submit a cloudbuild job to build the image
func BuildImage(ctx context.Context, c *gin.Context) error {
	l := log.FromContext(ctx)
	var tr helper.TaskRequest
	buf, err := io.ReadAll(c.Request.Body)
	if err != nil {
		l.Error(err, "io.ReadAll")
		return err
	}
	err = json.Unmarshal(buf, &tr)
	if err != nil {
		l.Error(err, "json.Unmarshal", "buf", string(buf))
		return err
	}

	taurusImage := fmt.Sprintf("asia-docker.pkg.dev/%s/%s-pt-images/taurus-base", tr.ProjectID, tr.ProjectID)
	locustImage := fmt.Sprintf("asia-docker.pkg.dev/%s/%s-pt-images/locust-worker", tr.ProjectID, tr.ProjectID)
	tgzFile := fmt.Sprintf("/var/tmp/pt-scripts-%d.tgz", time.Now().UnixNano())
	destDir := fmt.Sprintf("/var/tmp/%d", time.Now().UnixNano())
	tgz2Gcs := fmt.Sprintf("/var/tmp/pt-scripts-to-gcs-%d.tgz", time.Now().UnixNano())

	l.Info("download the script file from bucket", "src", tr.Script4Task)

	bucket := strings.Split(tr.Script4Task, "/")[2]
	object := strings.Replace(tr.Script4Task, fmt.Sprintf("gs://%s/", bucket), "", 1)
	tgzBuf, err := downloadFromGcs(ctx, bucket, object)
	if err != nil {
		l.Error(err, "downloadFromGcs", "src", tr.Script4Task)
		return err
	}
	l.Info("extract script files from tgz")
	err = ioutil.WriteFile(tgzFile, tgzBuf, 0644)
	if err != nil {
		l.Error(err, "ioutil.WriteFile")
		return err
	}
	err = untarzFile(ctx, tgzFile, destDir+"/scripts")
	if err != nil {
		l.Error(err, "untarzFile", "tgzFile", tgzFile)
		return err
	}

	///////////////////////////////
	// Build Locust image
	l.Info("add docker file for Locust")
	err = copyFile(ctx, "/manifests/Dockerfile.locust", destDir+"/Dockerfile")
	if err != nil {
		return err
	}

	l.Info("tar the files to tgz")
	err = tarzFile(ctx, destDir, tgz2Gcs)
	if err != nil {
		l.Error(err, "tarzFile", "tgz2Gcs", tgz2Gcs)
		return err
	}

	l.Info("save the tgz to gcs", "src", tgz2Gcs)
	obj, err := save2gcs(ctx, tr.ProjectID, tgz2Gcs)
	if err != nil {
		l.Error(err, "save2gcs", "tgz2Gcs", tgz2Gcs)
		return err
	}
	l.Info("save2gcs was done", "obj", obj)

	l.Info("submit a cloudbuild job to build the image for Locust")
	err = submitCloudBuildJob(ctx, tr.ProjectID, obj, locustImage)
	if err != nil {
		l.Error(err, "submitCloudBuildJob", "image", locustImage)
		return err
	}

	///////////////////////////////
	// Build Taurus image
	l.Info("add docker file for Taurus")
	err = copyFile(ctx, "/manifests/Dockerfile.taurus", destDir+"/Dockerfile")
	if err != nil {
		return err
	}

	l.Info("tar the files to tgz")
	err = tarzFile(ctx, destDir, tgz2Gcs)
	if err != nil {
		l.Error(err, "tarzFile", "tgz2Gcs", tgz2Gcs)
		return err
	}

	l.Info("save the tgz to gcs")
	obj, err = save2gcs(ctx, tr.ProjectID, tgz2Gcs)
	if err != nil {
		l.Error(err, "save2gcs", "tgz2Gcs", tgz2Gcs)
		return err
	}

	l.Info("submit a cloudbuild job to build the image for Taurus")
	err = submitCloudBuildJob(ctx, tr.ProjectID, obj, taurusImage)
	if err != nil {
		l.Error(err, "submitCloudBuildJob", "image", taurusImage)
		return err
	}
	/////////////////////
	return nil
}

func copyFile(ctx context.Context, src string, dst string) error {
	l := log.FromContext(ctx)
	input, err := ioutil.ReadFile(src)
	if err != nil {
		l.Error(err, "ioutil.ReadFile", "dockerFile", src)
		return err
	}

	err = os.MkdirAll(filepath.Dir(dst), 0755)
	if err != nil {
		l.Error(err, "os.MkdirAll", "dockerFile", dst)
		return err
	}
	err = ioutil.WriteFile(dst, input, 0644)
	if err != nil {
		l.Error(err, "ioutil.WriteFile", "dockerFile", dst)
		return err
	}
	return nil
}

func tarzFile(ctx context.Context, srcDir string, tgzFile string) error {
	l := log.FromContext(ctx)
	var buf bytes.Buffer
	err := os.Chdir(srcDir)
	if err != nil {
		l.Error(err, "os.Chdir", "srcDir", srcDir)
		return err
	}

	// tar > gzip > buf
	zr := gzip.NewWriter(&buf)
	tw := tar.NewWriter(zr)

	// walk through every file in the folder
	filepath.Walk("./", func(file string, fi os.FileInfo, err error) error {
		// generate tar header
		header, err := tar.FileInfoHeader(fi, file)
		if err != nil {
			return err
		}

		// must provide real name
		// (see https://golang.org/src/archive/tar/common.go?#L626)
		header.Name = filepath.ToSlash(file)
		fmt.Println(header.Name)

		// write header
		if err := tw.WriteHeader(header); err != nil {
			return err
		}
		// if not a dir, write file content
		if !fi.IsDir() {
			data, err := os.Open(file)
			if err != nil {
				return err
			}
			if _, err := io.Copy(tw, data); err != nil {
				return err
			}
		}
		return nil
	})

	// produce tar
	if err := tw.Close(); err != nil {
		return err
	}
	// produce gzip
	if err := zr.Close(); err != nil {
		return err
	}
	//
	fileToWrite, err := os.OpenFile(tgzFile, os.O_CREATE|os.O_TRUNC|os.O_RDWR, os.FileMode(0644))
	if err != nil {
		l.Error(err, "os.OpenFile", "file", tgzFile)
		return nil
	}
	if _, err := io.Copy(fileToWrite, &buf); err != nil {
		l.Error(err, "io.Copy")
		return err
	}
	return nil
}

func untarzFile(ctx context.Context, srcFile string, destDir string) error {
	l := log.FromContext(ctx)
	err := os.MkdirAll(destDir, 0755)
	if err != nil {
		l.Error(err, "os.MkdirAll", "destDir", destDir)
		return err
	}
	err = os.Chdir(destDir)
	if err != nil {
		l.Error(err, "os.Chdir", "destDir", destDir)
		return err
	}

	f, err := os.Open(srcFile)
	if err != nil {
		l.Error(err, "os.Open", "srcFile", srcFile)
		return err
	}
	defer f.Close()

	gzf, err := gzip.NewReader(f)
	if err != nil {
		l.Error(err, "gzip.NewReader", "srcFile", srcFile)
		return err
	}
	defer gzf.Close()

	tarReader := tar.NewReader(gzf)
	for {
		header, err := tarReader.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			l.Error(err, "tarReader.Next")
			return err
		}

		switch header.Typeflag {
		case tar.TypeDir:
			if err := os.MkdirAll(header.Name, os.FileMode(header.Mode)); err != nil {
				l.Error(err, "os.MkdirAll", "dir", header.Name)
				return err
			}
		case tar.TypeReg:
			targetFile, err := os.OpenFile(header.Name, os.O_CREATE|os.O_WRONLY, os.FileMode(header.Mode))
			if err != nil {
				l.Error(err, "os.OpenFile", "file", header.Name)
				return err
			}
			if _, err := io.Copy(targetFile, tarReader); err != nil {
				l.Error(err, "io.Copy", "file", header.Name)
				return err
			}
			targetFile.Close()
		default:
			l.Info("Unable to extract file type in file", "type", header.Typeflag, "file", header.Name)
		}
	}
	return nil
}

func submitCloudBuildJob(ctx context.Context, projectID string, obj string, image string) error {
	l := log.FromContext(ctx)
	c, err := cloudbuild.NewClient(ctx)
	if err != nil {
		l.Error(err, "unable to create cloudbuild client")
		return err
	}
	defer c.Close()

	req := &cloudbuildpb.CreateBuildRequest{
		Parent:    fmt.Sprintf("projects/%s/locations/global", projectID),
		ProjectId: projectID,
		Build: &cloudbuildpb.Build{
			Source: &cloudbuildpb.Source{
				Source: &cloudbuildpb.Source_StorageSource{
					StorageSource: &cloudbuildpb.StorageSource{
						Bucket: projectID + "_cloudbuild",
						Object: obj,
					},
				},
			},
			Steps: []*cloudbuildpb.BuildStep{
				{
					Name: "gcr.io/cloud-builders/docker",
					Args: []string{
						"build",
						"-t",
						image,
						".",
					},
				},
				{
					Name: "gcr.io/cloud-builders/docker",
					Args: []string{
						"push",
						image,
					},
				},
			},
		},
	}
	_, err = c.CreateBuild(ctx, req)
	if err != nil {
		l.Error(err, "unable to create cloudbuild job")
		return err
	}
	return nil
}

func save2gcs(ctx context.Context, projectID string, srcFile string) (string, error) {
	// save bytes to gcs and return the path
	l := log.FromContext(ctx)
	bucket := projectID + "_cloudbuild"
	dstFile := "source/pt-scripts-" + strconv.FormatInt(time.Now().UnixNano(), 10) + ".tgz"
	fh, err := os.Open(srcFile)
	if err != nil {
		l.Error(err, "unable to open source file", "src", srcFile)
		return dstFile, err
	}
	l.Info("file opened", "file", srcFile)

	client, err := storage.NewClient(ctx)
	if err != nil {
		l.Error(err, "unable to create GCS client")
		return dstFile, err
	}
	wc := client.Bucket(bucket).Object(dstFile).NewWriter(ctx)
	if _, err = io.Copy(wc, fh); err != nil {
		l.Error(err, "unable to copy file to GCS", "src", srcFile, "dst", dstFile)
		return dstFile, err
	}
	l.Info("file copied to GCS", "src", srcFile, "dst", dstFile)

	if err := wc.Close(); err != nil {
		l.Error(err, "unable to close GCS writer", "src", srcFile, "dst", dstFile)
		return dstFile, err
	}
	l.Info("file saved to GCS", "file", dstFile)
	return dstFile, nil
}

func DestroyResources(ctx context.Context, c *gin.Context) error {
	l := log.FromContext(ctx)
	projectID := c.Param("projectId")
	correlationID := c.Param("correlationId")
	// userEmail := c.Param("userEmail")
	ti := &helper.TInfra{}

	trans, err := helper.Read(ctx, projectID, "pt-transactions", correlationID, "")
	if err != nil {
		l.Error(err, "unable to read transaction", "projectId", projectID, "correlationId", correlationID)
		return err
	}
	l.Info("transaction read", "projectId", projectID, "executionId", trans.ExecutionID, "trans.correlationId", trans.CorrelationID)

	// delete GKE Autopilot cluster
	var input helper.ProvisionWf
	buf, err := json.Marshal(trans.Input)
	if err != nil {
		l.Error(err, "unable to marshal transaction input", "projectId", projectID, "executionId", trans.ExecutionID)
	}
	err = json.Unmarshal(buf, &input)
	if err != nil {
		l.Error(err, "unable to unmarshal transaction input", "projectId", projectID, "executionId", trans.ExecutionID)
	}

	for _, gke := range input.GKEs {
		l.Info("deleting GKE cluster", "cluster", gke.Cluster, "location", gke.Location)
		_, err = ti.DeleteAutopilotCluster(ctx, gke.ProjectID, gke.Cluster, gke.Location)
		if err != nil {
			l.Error(err, "ti.DeleteAutopilotCluster", "cluster", gke.Cluster, "location", gke.Location)
			return err
		}
	}

	// Do not delete Service Account as it is used by other PTs and speed up PTs
	// Do not delete VPC as it is used by other PTs and speed up PTs

	return nil
}

func CreatePtTask(ctx context.Context, c *gin.Context) (*api.PtLaunchedTask, error) {
	l := log.FromContext(ctx).WithName("CreatePtTask")
	l.Info("Reveived request from client to create a PtTask")
	// userEmail := c.GetString("user_email")
	// ts, err := helper.RetrieveGoogleTokenSource(ctx, userEmail)
	// if err != nil {
	// 	l.Error(err, "unable to retrieve GoogleTokenSource")
	// 	return nil, err
	// }
	// tk, err := ts.Token()
	// if err != nil {
	// 	l.Error(err, "unable to retrieve token")
	// 	return nil, err
	// }
	// l.Info("GoogleTokenSource retrieved", "token", tk.AccessToken)
	var ptr api.PtTaskRequest
	buf, err := io.ReadAll(c.Request.Body)
	if err != nil {
		l.Error(err, "io.ReadAll")
		return nil, err
	}
	err = json.Unmarshal(buf, &ptr)
	if err != nil {
		l.Error(err, "json.Unmarshal", "buf", string(buf))
		return nil, err
	}
	if ptr.CorrelationId == "" {
		return nil, errors.New("correlationId is empty & uploading script to get correlationId")
	}

	// Get URL of CloudRun service
	runService := os.Getenv("K_SERVICE")
	projectID := os.Getenv("PROJECT_ID")
	location := os.Getenv("LOCATION")
	bucket := os.Getenv("ARCHIEVE_BUCKET")
	crID := ptr.CorrelationId
	l.Info("creating a pttask", "projectId", projectID, "location", location, "runService", runService, "correlationId", crID, "bucket", bucket)
	cloudrun, err := run.NewServicesClient(ctx)
	if err != nil {
		l.Error(err, "unable to create cloudrun client")
		return nil, err
	}
	req := &runpb.GetServiceRequest{
		Name: fmt.Sprintf("projects/%s/locations/%s/services/%s", projectID, location, runService),
	}
	resp, err := cloudrun.GetService(ctx, req)
	if err != nil {
		l.Error(err, "unable to get cloudrun service")
		return nil, err
	}

	// Construct the input for the workflow
	network := "pt-vpc-9uej2d" // + randString()
	pwf := helper.ProvisionWf{
		URL:           resp.Uri,
		ProjectID:     projectID,
		CorrelationID: crID,
		GKEs: []helper.GKE{
			{
				AccountID:  "pt-service-account",
				ProjectID:  projectID,
				Cluster:    "pt-cluster-9uej2d", // + randString()
				IsMater:    "true",
				Location:   location,
				Network:    network,
				Subnetwork: network,
			},
		},
		VPC: helper.VPC{
			Mtu:       1460,
			Network:   network,
			ProjectID: projectID,
		},
		ServiceAccount: helper.ServiceAccount{
			AccountID: "pt-service-account",
			ProjectID: projectID,
		},
		TaskRequest: helper.TaskRequest{
			ProjectID:     projectID,
			ArchiveBucket: bucket,
			Executor:      "locust",
			NumOfUsers:    int(ptr.TotalUsers),
			Duration:      int(ptr.Duration),
			RampUp:        int(ptr.RampUp),
			TargetURL:     ptr.TargetUrl,
			WorkerNumber:  int(ptr.WorkerNumber),
			IsLocal:       api.PtTaskType(ptr.Type.Number()) == api.PtTaskType_LOCAL,
			Script4Task:   fmt.Sprintf("gs://%s/upload-scripts/%s.tgz", bucket, crID),
		},
		// CreatorEmail: helper.EncryptData(userEmail),
	}

	// Adding GKEs per distributed traffics
	for _, t := range ptr.Traffics {
		pwf.GKEs = append(pwf.GKEs, helper.GKE{
			AccountID:  "pt-service-account",
			ProjectID:  projectID,
			Cluster:    "pt-cluster-9uej2d", // + randString()
			IsMater:    "false",
			Location:   t.Region,
			Network:    network,
			Subnetwork: network,
			Percent:    int(t.Percent),
		})
	}
	//

	// Respond to client
	launchedTask := &api.PtLaunchedTask{
		CorrelationId:   crID,
		TaskStatus:      api.PtLaunchedTaskStatus_PENDING,
		ProvisionStatus: api.WorkflowStatus_PROVISIONING,
		Created:         timestamppb.Now(),
		LastUpdated:     timestamppb.Now(),
		Task:            &ptr,
	}
	// Attached info as a part of the workflow
	pwf.OriginTaskRequest = &ptr
	pwf.OriginLaunchedTask = launchedTask

	ibuf, err := json.Marshal(pwf)
	if err != nil {
		l.Error(err, "json.Marshal")
		return nil, err
	}

	// Send message to PubSub and trigger provisoning workflow
	topic := "pt-provision-wf"
	// client, err := pubsub.NewClient(ctx, projectId, option.WithTokenSource(ts))
	client, err := pubsub.NewClient(ctx, projectID)
	if err != nil {
		l.Error(err, "unable to create pubsub client")
		return nil, err
	}
	ret := client.Topic(topic).Publish(ctx, &pubsub.Message{
		Data: ibuf,
	})
	_, err = ret.Get(ctx)
	if err != nil {
		l.Error(err, "unable to publish message to pubsub")
		return nil, err
	}

	return launchedTask, nil
}

func round(x float64) int {
	return int(math.Floor(x + 0.5))
}

// Generate a random string of a-z chars with len = 6
func randString() string {
	rand.Seed(time.Now().UnixNano())
	chars := []rune("abcdefghijklmnopqrstuvwxyz0123456789")
	b := make([]rune, 6)
	for i := range b {
		b[i] = chars[rand.Intn(len(chars))]
	}
	return string(b)
}

func GetPtTask(ctx context.Context, c *gin.Context) (*api.PtLaunchedTask, error) {
	l := log.FromContext(ctx).WithName("GetPtTask")
	// userEmail := c.GetString("user_email")
	correlationId := c.Param("correlationId")
	l.Info("Get a PtTask by correlationId", "correlationId", correlationId)

	projectID := os.Getenv("PROJECT_ID")
	// ptt, err := helper.Read(ctx, projectId, "pt-transactions", correlationId, userEmail)
	ptt, err := helper.Read(ctx, projectID, "pt-transactions", correlationId, "")
	if err != nil {
		l.Error(err, "unable to read pt-transactions from firestore")
		return nil, err
	}

	launchedTask := &api.PtLaunchedTask{
		CorrelationId:   ptt.CorrelationID,
		TaskStatus:      api.PtLaunchedTaskStatus(api.PtLaunchedTaskStatus_value[ptt.PtTaskStatus]),
		ProvisionStatus: api.WorkflowStatus(api.WorkflowStatus_value[ptt.WorkflowStatus]),
		Created:         ptt.Created,
		Finished:        ptt.Finished,
		LastUpdated:     ptt.LastUpdated,
		Task:            ptt.OriginTaskRequest,
		// MetricsLink:     *ptt.MetricsLink,
		// LogsLink:        *ptt.LogsLink,
		// DownloadLink:    *ptt.DownloadLink,
	}
	if ptt.MetricsLink != nil {
		launchedTask.MetricsLink = *ptt.MetricsLink
	}
	if ptt.LogsLink != nil {
		launchedTask.LogsLink = *ptt.LogsLink
	}
	if ptt.DownloadLink != nil {
		launchedTask.DownloadLink = *ptt.DownloadLink
	}

	return launchedTask, nil
}

func ListPtTasks(ctx context.Context, c *gin.Context) ([]*api.PtLaunchedTask, error) {
	l := log.FromContext(ctx).WithName("ListPtTasks")
	l.Info("Retrieve all PtTasks", "gin.Context", c)
	// userEmail := c.GetString("user_email")

	projectId := os.Getenv("PROJECT_ID")
	// pts, err := helper.ReadAll(ctx, projectId, "pt-transactions", userEmail)
	pts, err := helper.ReadAll(ctx, projectId, "pt-transactions", "")
	if err != nil {
		l.Error(err, "unable to read pt-transactions from firestore")
		return nil, err
	}

	var launchedTasks []*api.PtLaunchedTask
	for _, ptt := range pts {
		launchedTask := &api.PtLaunchedTask{
			CorrelationId:   ptt.CorrelationID,
			TaskStatus:      api.PtLaunchedTaskStatus(api.PtLaunchedTaskStatus_value[ptt.PtTaskStatus]),
			ProvisionStatus: api.WorkflowStatus(api.WorkflowStatus_value[ptt.WorkflowStatus]),
			Created:         ptt.Created,
			Finished:        ptt.Finished,
			LastUpdated:     ptt.LastUpdated,
			Task:            ptt.OriginTaskRequest,
			// MetricsLink:     *ptt.MetricsLink,
			// LogsLink:        *ptt.LogsLink,
			// DownloadLink:    *ptt.DownloadLink,
		}
		if ptt.MetricsLink != nil {
			launchedTask.MetricsLink = *ptt.MetricsLink
		}
		if ptt.LogsLink != nil {
			launchedTask.LogsLink = *ptt.LogsLink
		}
		if ptt.DownloadLink != nil {
			launchedTask.DownloadLink = *ptt.DownloadLink
		}

		launchedTasks = append(launchedTasks, launchedTask)
	}

	return launchedTasks, nil
}

func DeletePtTask(ctx context.Context, c *gin.Context) error {
	l := log.FromContext(ctx).WithName("DeletePtTask")
	// userEmail := c.GetString("user_email")
	// ts, err := helper.RetrieveGoogleTokenSource(ctx, userEmail)
	// if err != nil {
	// 	l.Error(err, "unable to retrieve GoogleTokenSource")
	// 	return err
	// }

	correlationID := c.Param("correlationId")
	l.Info("Delete a PtTask by correlationId", "correlationId", correlationID)
	// ti := &helper.TInfra{}
	projectId := os.Getenv("PROJECT_ID")
	runService := os.Getenv("K_SERVICE")
	location := os.Getenv("LOCATION")
	// ptt, err := helper.Read(ctx, projectId, "pt-transactions", correlationId, userEmail)
	ptt, err := helper.Read(ctx, projectId, "pt-transactions", correlationID, "")
	if err != nil {
		l.Error(err, "unable to read pt-transactions from firestore")
		return err
	}

	// Reretive the url of cloudrun
	cloudrun, err := run.NewServicesClient(ctx)
	if err != nil {
		l.Error(err, "unable to create cloudrun client")
		return err
	}
	req := &runpb.GetServiceRequest{
		Name: fmt.Sprintf("projects/%s/locations/%s/services/%s", projectId, location, runService),
	}
	resp, err := cloudrun.GetService(ctx, req)
	if err != nil {
		l.Error(err, "unable to get cloudrun service")
		return err
	}

	topic := "pt-destroy-wf"
	// client, err := pubsub.NewClient(ctx, projectId, option.WithTokenSource(ts))
	client, err := pubsub.NewClient(ctx, projectId)
	if err != nil {
		l.Error(err, "unable to create pubsub client")
		return err
	}
	ret := client.Topic(topic).Publish(ctx, &pubsub.Message{
		Data: []byte("{\"url\": \"" + resp.Uri + "\", \"executionId\": \"" + ptt.ExecutionID + "\", \"correlationId\": \"" + ptt.CorrelationID + "\", \"projectId\": " + projectId + "}"),
	})
	_, err = ret.Get(ctx)
	if err != nil {
		l.Error(err, "unable to publish message to pubsub")
		return err
	}

	// Update status to CANCELLED in Firestore
	_, err = helper.UpdatePtTaskStatus(ctx, projectId, "pt-transactions", correlationID, api.PtLaunchedTaskStatus_CANCELLED.String())
	if err != nil {
		l.Error(err, "unable to update pttask status")
		return err
	}

	return nil
}

// UpdatePtTaskStatus updates the status of a pttask, call from Cloud Run with status name
func UpdatePtTaskStatus(ctx context.Context, c *gin.Context) error {
	l := log.FromContext(ctx).WithName("UpdatePtTask")
	l.Info("UpdatePtTask")
	correlationId := c.Param("correlationId")
	projectId := os.Getenv("PROJECT_ID")

	status, err := io.ReadAll(c.Request.Body)
	if err != nil {
		l.Error(err, "io.ReadAll")
		return err
	}
	_, err = helper.UpdatePtTaskStatus(ctx, projectId, "pt-transactions", correlationId, string(status))
	return err
}

// UpdateWorkflowStatus updates the status of a workflow, call from Workflow with status name
func UpdateWorkflowStatus(ctx context.Context, c *gin.Context) error {
	l := log.FromContext(ctx).WithName("UpdateWorkflowStatus")
	correlationID := c.Param("correlationId")
	projectID := os.Getenv("PROJECT_ID")
	l.Info("Update the status of workflow", "correlationId", correlationID, "projectId", projectID, "status", api.WorkflowStatus_PROVISIONING_FINISHED.String())

	_, err := helper.UpdateWorkflowStatus(ctx, projectID, "pt-transactions", correlationID, api.WorkflowStatus_PROVISIONING_FINISHED.String())
	return err
}

func UploadScriptsFile(ctx context.Context, c *gin.Context) (string, error) {
	l := log.FromContext(ctx).WithName("UploadScriptsFile")
	l.Info("UploadScriptsFile with mixmium size 5MB")

	crID := uuid.New().String()
	file, err := c.FormFile("file")
	if err != nil {
		l.Error(err, "unable to get file from form")
		return crID, err
	}

	l.Info("file info", "name", file.Filename, "size", file.Size)
	uploadedFile, err := file.Open()
	if err != nil {
		l.Error(err, "unable to open file")
		return crID, err
	}
	defer uploadedFile.Close()

	bucket := os.Getenv("ARCHIEVE_BUCKET")
	dstFile := fmt.Sprintf("upload-scripts/%s.tgz", crID)
	// Using Cloud Storage API
	client, err := storage.NewClient(ctx)
	if err != nil {
		l.Error(err, "unable to create GCS client")
		return crID, err
	}
	defer client.Close()

	wc := client.Bucket(bucket).Object(dstFile).NewWriter(ctx)
	if _, err = io.Copy(wc, uploadedFile); err != nil {
		l.Error(err, "unable to copy file to GCS", "dst", dstFile)
		return crID, err
	}
	if err := wc.Close(); err != nil {
		l.Error(err, "unable to close GCS writer", "dst", dstFile)
		return crID, err
	}

	return crID, nil
}

func downloadFromGcs(ctx context.Context, bucket, srcFile string) ([]byte, error) {
	l := log.FromContext(ctx).WithName("downloadFromGcs")
	l.Info("downloadFromGcs", "bucket", bucket, "srcFile", srcFile)
	client, err := storage.NewClient(ctx)
	if err != nil {
		l.Error(err, "unable to create GCS client")
		return nil, err
	}
	defer client.Close()

	rc, err := client.Bucket(bucket).Object(srcFile).NewReader(ctx)
	if err != nil {
		l.Error(err, "unable to create GCS reader", "src", srcFile)
		return nil, err
	}
	defer rc.Close()

	data, err := io.ReadAll(rc)
	if err != nil {
		l.Error(err, "unable to read GCS file", "src", srcFile)
		return nil, err
	}

	return data, nil
}
