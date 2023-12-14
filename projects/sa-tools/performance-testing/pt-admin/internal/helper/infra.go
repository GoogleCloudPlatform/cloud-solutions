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
	"fmt"
	"time"

	compute "cloud.google.com/go/compute/apiv1"
	computepb "cloud.google.com/go/compute/apiv1/computepb"
	container "cloud.google.com/go/container/apiv1"
	containerpb "cloud.google.com/go/container/apiv1/containerpb"
	admin "cloud.google.com/go/iam/admin/apiv1"
	adminpb "cloud.google.com/go/iam/admin/apiv1/adminpb"
	"cloud.google.com/go/pubsub"
	wfexec "cloud.google.com/go/workflows/executions/apiv1"
	wfexecpb "cloud.google.com/go/workflows/executions/apiv1/executionspb"
	"google.golang.org/api/cloudresourcemanager/v1"
	"sigs.k8s.io/controller-runtime/pkg/log"
)

// TInfra is the struct for testing infrastructure, which is to be provisioned
type TInfra struct {
	// service account for all related operations
	ServiceAccount string
	// Key for the service account
	Key string
	// All provisoned GKE clusters: (region, cluster)
	Clusters map[string]GKECluster
}

// GKECluster is the struct for GKE cluster
type GKECluster struct {
	// Cluster operation record from create/update/delete
	Operation *containerpb.Operation
	// Network
	Network string
	// Subnetwork
	Subnet string
	// Cluster name
	Name string
	// Cluster region
	Region string
	// Certificate of the cluster
	CA string
	// External IP of the cluster
	Endpoint string
}

type OperationalStuff interface {
	// Create a VPC network
	CreateVPCNetwork(ctx context.Context, projectID string, name string, mtu int32) error
	// Create a service account
	CreateServiceAccount(ctx context.Context, projectID string, accountID string) (*adminpb.ServiceAccount, error)
	// Create a service account key
	CreateServiceAccountKey(ctx context.Context, projectID string, accountID string) (*adminpb.ServiceAccountKey, error)
	// Set IAM policies to a service account
	SetIamPolicies2SA(ctx context.Context, projectID string, saName string) error
	// Set IAM policies to a Kubernetes service account
	SetIamPolicies2KSA(ctx context.Context, projectID string, ns string, ksa string) error
	// Create a GKE Autopilot cluster
	CreateAutopilotCluster(ctx context.Context, projectID string, cluster string, region string, network string, subnet string, saID string) (*containerpb.Operation, error)
	// Delete a GKE Autopilot cluster
	DeleteAutopilotCluster(ctx context.Context, projectID string, cluster string, region string) (*containerpb.Operation, error)
	// Get status of provisioning a GKE Autopilot cluster
	AutopilotClusterStatus(ctx context.Context, opID string) (*containerpb.Operation, error)
	// Get status of provisioning a Zonalcluster
	// ZonalClusterStatus(ctx context.Context, projectID, region, opId string) (*containerpb.Operation, error)
	// Create a zonal GKE cluster
	// CreateZonalCluster(ctx context.Context, projectID string, cluster string, zone string, network string, subnet string, saName string) (*containerpb.Operation, error)
	// Execute a workflow
	ExecWorkflow(ctx context.Context, projectID string, workflow string, input []byte) error
}

// ExecWorkflow send message to a pubsub topic to trigger a workflow execution
// projectID: project id
// workflow: workflow name
// input: input to the workflow, which is JSON format
// return: error
func (ti *TInfra) ExecWorkflow(ctx context.Context, projectID string, workflow string, input []byte) error {
	l := log.FromContext(ctx).WithName("ExecWorkflow")
	// Trigger workflow execution directly has limit 32K for input data and very hard to use through REST API.
	// So use pubsub to trigger the workflow execution.
	client, err := pubsub.NewClient(ctx, projectID)
	if err != nil {
		l.Error(err, "Failed to create a pubsub client")
	}
	defer client.Close()
	topic := client.Topic(workflow)

	msg := &pubsub.Message{
		Data: input,
	}
	sid, err := topic.Publish(ctx, msg).Get(ctx)
	if err != nil {
		l.Error(err, "Failed to publish a message to trigger workflow", "workflow", workflow)
		return err
	}
	l.Info("Published a message to trigger workflow", "sid", sid, "workflow", workflow)
	return nil
}

func (ti *TInfra) StatusWorkflow(ctx context.Context, projectID string, region string, workflow string, execution string) (*wfexecpb.Execution, error) {
	c, err := wfexec.NewClient(ctx)
	if err != nil {
		return &wfexecpb.Execution{}, err
	}
	defer c.Close()

	return c.GetExecution(ctx, &wfexecpb.GetExecutionRequest{
		Name: fmt.Sprintf("projects/%s/locations/%s/workflows/%s/executions/%s", projectID, region, workflow, execution),
	})

}

func (ti *TInfra) CreateVPCNetwork(ctx context.Context, projectID string, name string, mtu int32) error {
	// https://cloud.google.com/go/docs/reference/cloud.google.com/go/networkmanagement/latest/apiv1

	l := log.FromContext(ctx).WithName("CreateVPCNetwork")
	c, err := compute.NewNetworksRESTClient(ctx)
	if err != nil {
		l.Error(err, "Failed to create a network client")
		return err
	}
	defer c.Close()
	auto := true
	mode := "GLOBAL"

	_, err = c.Get(ctx, &computepb.GetNetworkRequest{
		Project: projectID,
		Network: name,
	})
	if err != nil {
		l.Info("Network does not exist, creating a new one")
		op, err := c.Insert(ctx, &computepb.InsertNetworkRequest{
			Project: projectID,
			NetworkResource: &computepb.Network{
				Name:                  &name,
				AutoCreateSubnetworks: &auto,
				Mtu:                   &mtu,
				RoutingConfig: &computepb.NetworkRoutingConfig{
					RoutingMode: &mode,
				},
			},
		})
		if err != nil {
			l.Error(err, "Failed to create a network")
			return err
		}
		return op.Wait(ctx)

	}
	l.Info("Network already exists")

	return nil

}

func (ti *TInfra) CreateAutopilotCluster(ctx context.Context, projectID string, cluster string, region string, network string, subnet string, saID string) (*containerpb.Operation, error) {
	// https://cloud.google.com/go/docs/reference/cloud.google.com/go/container/apiv1
	l := log.FromContext(ctx).WithName("CreateAutopilotCluster")
	c, err := container.NewClusterManagerClient(ctx)
	if err != nil {
		return &containerpb.Operation{}, err
	}
	defer c.Close()

	_, err = c.GetCluster(ctx, &containerpb.GetClusterRequest{
		Name: fmt.Sprintf("projects/%s/locations/%s/clusters/%s", projectID, region, cluster),
	})
	if err != nil {
		l.Info("Cluster does not exist, creating a new one")
		req := &containerpb.CreateClusterRequest{
			Parent: fmt.Sprintf("projects/%s/locations/%s", projectID, region),
			Cluster: &containerpb.Cluster{
				Name:       cluster,
				Network:    network,
				Subnetwork: subnet,
				Autopilot: &containerpb.Autopilot{
					Enabled: true,
				},
				ReleaseChannel: &containerpb.ReleaseChannel{
					Channel: containerpb.ReleaseChannel_RAPID,
				},
				// Assign a service account to the cluster: THIS DOES NOT WORK, SO USE FOLLOWING INSTEAD!
				NodeConfig: &containerpb.NodeConfig{
					ServiceAccount: fmt.Sprintf("%s@%s.iam.gserviceaccount.com", saID, projectID),
					OauthScopes: []string{
						"https://www.googleapis.com/auth/cloud-platform",
					},
				},
				// Assign a service account to the cluster
				Autoscaling: &containerpb.ClusterAutoscaling{
					AutoprovisioningNodePoolDefaults: &containerpb.AutoprovisioningNodePoolDefaults{
						ServiceAccount: fmt.Sprintf("%s@%s.iam.gserviceaccount.com", saID, projectID),
						OauthScopes: []string{
							"https://www.googleapis.com/auth/cloud-platform",
						},
					},
				},
			},
		}

		return c.CreateCluster(ctx, req)
	}

	l.Info("Cluster already exists")
	return &containerpb.Operation{}, nil

}

func (ti *TInfra) DeleteAutopilotCluster(ctx context.Context, projectID string, cluster string, region string) (*containerpb.Operation, error) {
	// https://cloud.google.com/go/docs/reference/cloud.google.com/go/container/apiv1
	l := log.FromContext(ctx).WithName("DeleteAutopilotCluster")
	c, err := container.NewClusterManagerClient(ctx)
	if err != nil {
		return &containerpb.Operation{}, err
	}
	defer c.Close()

	_, err = c.GetCluster(ctx, &containerpb.GetClusterRequest{
		Name: fmt.Sprintf("projects/%s/locations/%s/clusters/%s", projectID, region, cluster),
	})
	if err != nil {
		l.Info("Cluster does not exist, nothing to delete")
		return &containerpb.Operation{}, nil
	}
	l.Info("Cluster exists, deleting")
	req := &containerpb.DeleteClusterRequest{
		Name: fmt.Sprintf("projects/%s/locations/%s/clusters/%s", projectID, region, cluster),
	}
	return c.DeleteCluster(ctx, req)

}

func (ti *TInfra) AutopilotClusterStatus(ctx context.Context, projectID, region, opID string) (*containerpb.Operation, error) {
	// https://cloud.google.com/go/docs/reference/cloud.google.com/go/container/apiv1
	c, err := container.NewClusterManagerClient(ctx)
	if err != nil {
		return &containerpb.Operation{}, err
	}
	defer c.Close()

	req := &containerpb.GetOperationRequest{
		Name: fmt.Sprintf("projects/%s/locations/%s/operations/%s", projectID, region, opID),
	}

	return c.GetOperation(ctx, req)

}

func (ti *TInfra) CreateServiceAccount(ctx context.Context, projectID string, accountID string) (*adminpb.ServiceAccount, error) {
	l := log.FromContext(ctx).WithName("CreateServiceAccount")
	c, err := admin.NewIamClient(ctx)
	if err != nil {
		l.Error(err, "Failed to create a service account client")
		return &adminpb.ServiceAccount{}, err
	}
	sa, err := c.GetServiceAccount(ctx, &adminpb.GetServiceAccountRequest{
		Name: fmt.Sprintf("projects/%s/serviceAccounts/%s@%s.iam.gserviceaccount.com", projectID, accountID, projectID),
	})
	if err != nil {
		l.Info("Service account does not exist, creating a new one")
		req := &adminpb.CreateServiceAccountRequest{
			Name:      fmt.Sprintf("projects/%s", projectID),
			AccountId: accountID,
		}
		return c.CreateServiceAccount(ctx, req)
	}
	l.Info("Service account already exists")
	return sa, nil

}

func (ti *TInfra) CreateServiceAccountKey(ctx context.Context, projectID string, accountID string) (*adminpb.ServiceAccountKey, error) {
	c, err := admin.NewIamClient(ctx)
	if err != nil {
		return &adminpb.ServiceAccountKey{}, err
	}

	req := &adminpb.CreateServiceAccountKeyRequest{
		Name: fmt.Sprintf("projects/%s/serviceAccounts/%s@%s.iam.gserviceaccount.com", projectID, accountID, projectID),
	}

	return c.CreateServiceAccountKey(ctx, req)

}

// Grant following roles to a specific service account:
//
// roles/iam.workloadIdentityUser
// roles/container.clusterAdmin
// roles/artifactregistry.reader
// roles/iam.serviceAccountUser
// roles/storage.objectCreator
// roles/compute.networkAdmin
// roles/logging.admin
// roles/monitoring.admin
// roles/resourcemanager.projectIamAdmin
// roles/run.invoker
func (ti *TInfra) SetIamPolicies2SA(ctx context.Context, projectID string, saName string) error {

	crm, err := cloudresourcemanager.NewService(ctx)
	if err != nil {
		return err
	}

	roles := []string{
		"roles/iam.workloadIdentityUser",
		"roles/container.clusterAdmin",
		"roles/artifactregistry.reader",
		"roles/iam.serviceAccountUser",
		"roles/storage.objectCreator",
		"roles/compute.networkAdmin",
		"roles/logging.admin",
		"roles/monitoring.admin",
		"roles/resourcemanager.projectIamAdmin",
		"roles/run.invoker",
	}
	member := fmt.Sprintf("serviceAccount:%s@%s.iam.gserviceaccount.com", saName, projectID)
	for _, role := range roles {
		policy, err := getPolicy(crm, projectID)
		if err != nil {
			return err
		}
		// Find the policy binding for role. Only one binding can have the role.
		var binding *cloudresourcemanager.Binding
		for _, b := range policy.Bindings {
			if b.Role == role {
				binding = b
				break
			}
		}

		if binding != nil {
			// If the binding exists, adds the member to the binding
			binding.Members = append(binding.Members, member)
		} else {
			// If the binding does not exist, adds a new binding to the policy
			binding = &cloudresourcemanager.Binding{
				Role:    role,
				Members: []string{member},
			}
			policy.Bindings = append(policy.Bindings, binding)
		}

		if err := setPolicy(crm, projectID, policy); err != nil {
			return err
		}

	}

	return nil
}

func (ti *TInfra) SetIamPolicies2KSA(ctx context.Context, projectID string, ns string, ksa string) error {
	// gcloud iam service-accounts add-iam-policy-binding gmp-test-sa@play-api-service.iam.gserviceaccount.com \
	// --role roles/iam.workloadIdentityUser \
	// --member "serviceAccount:play-api-service.svc.id.goog[default/pt-operator-controller-manager]"
	crm, err := cloudresourcemanager.NewService(ctx)
	if err != nil {
		return err
	}

	roles := []string{
		"roles/iam.workloadIdentityUser",
	}
	member := fmt.Sprintf("serviceAccount:%s.svc.id.goog[%s/%s]", projectID, ns, ksa)
	for _, role := range roles {
		policy, err := getPolicy(crm, projectID)
		if err != nil {
			return err
		}
		// Find the policy binding for role. Only one binding can have the role.
		var binding *cloudresourcemanager.Binding
		for _, b := range policy.Bindings {
			if b.Role == role {
				binding = b
				break
			}
		}

		if binding != nil {
			// If the binding exists, adds the member to the binding
			binding.Members = append(binding.Members, member)
		} else {
			// If the binding does not exist, adds a new binding to the policy
			binding = &cloudresourcemanager.Binding{
				Role:    role,
				Members: []string{member},
			}
			policy.Bindings = append(policy.Bindings, binding)
		}

		if err := setPolicy(crm, projectID, policy); err != nil {
			return err
		}

	}
	return nil
}

func getPolicy(crmService *cloudresourcemanager.Service, projectID string) (*cloudresourcemanager.Policy, error) {

	ctx := context.Background()

	_, cancel := context.WithTimeout(ctx, time.Second*10)
	defer cancel()
	request := new(cloudresourcemanager.GetIamPolicyRequest)
	return crmService.Projects.GetIamPolicy(projectID, request).Do()

}

func setPolicy(crmService *cloudresourcemanager.Service, projectID string, policy *cloudresourcemanager.Policy) error {

	ctx := context.Background()

	_, cancel := context.WithTimeout(ctx, time.Second*10)
	defer cancel()
	request := new(cloudresourcemanager.SetIamPolicyRequest)
	request.Policy = policy
	_, err := crmService.Projects.SetIamPolicy(projectID, request).Do()
	return err
}

func (ti *TInfra) GetClusterEndpoint(ctx context.Context, projectID string, cluster string, region string) (string, error) {
	c, err := container.NewClusterManagerClient(ctx)
	if err != nil {
		return "", err
	}
	defer c.Close()

	req := &containerpb.GetClusterRequest{
		Name: fmt.Sprintf("projects/%s/locations/%s/clusters/%s", projectID, region, cluster),
	}
	resp, err := c.GetCluster(ctx, req)
	if err != nil {
		return "", err
	}

	return resp.Endpoint, nil
}

func (ti *TInfra) GetClusterCaCertificate(ctx context.Context, projectID string, cluster string, region string) (string, error) {
	c, err := container.NewClusterManagerClient(ctx)
	if err != nil {
		return "", err
	}
	defer c.Close()

	req := &containerpb.GetClusterRequest{
		Name: fmt.Sprintf("projects/%s/locations/%s/clusters/%s", projectID, region, cluster),
	}
	resp, err := c.GetCluster(ctx, req)
	if err != nil {
		return "", err
	}
	fmt.Println(resp.MasterAuth.ClusterCaCertificate)
	return resp.MasterAuth.ClusterCaCertificate, nil
}
