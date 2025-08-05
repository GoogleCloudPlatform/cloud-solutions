# Deploy to an Azure Kubernetes Service (AKS) cluster

Follow the instructions below to deploy `k8s-hybrid-neg-controller` to an Azure
Kubernetes Service (AKS) cluster, including building the container image and
pushing it to a private container image registry in Azure Container Registry.

These instructions assume the following:

- You have already created an AKS cluster.

- The
  [OpenID Connect (OIDC) issuer feature](https://learn.microsoft.com/azure/aks/use-oidc-issuer)
  is enabled on the AKS cluster.

- Workloads in the AKS cluster can reach the Compute Engine API endpoint
  `compute.googleapis.com:443`, either via
  [Private Google Access over hybrid connectivity](https://cloud.google.com/vpc/docs/configure-private-google-access-hybrid),
  or via the public Internet.

- You have permissions to create the following resources in the AKS cluster:
  `ClusterRole`, `ClusterRoleBinding`, `Namespace`, `Role`, `RoleBinding`,
  `ServiceAccount`, `ConfigMap`, `Deployment`, and `Service`.

- Your current `kubectl` context points to the AKS cluster. You can view the
  details of your current `kubectl` context:

```shell
kubectl config view --minify
```

## Google Cloud costs

In this document, you use the following billable components of Google Cloud:

- [Compute Engine](https://cloud.google.com/compute/all-pricing)

To generate a cost estimate based on your projected usage, use the
[pricing calculator](https://cloud.google.com/products/calculator). New Google
Cloud users might be eligible for a free trial.

When you finish the tasks that are described in this document, you can avoid
continued billing by deleting the resources that you created. For more
information, see [Clean up](#clean-up).

## Before you begin

1.  Install the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install).

1.  [Configure authorization and a base set of properties](https://cloud.google.com/sdk/docs/initializing)
    for the `gcloud` command line tool. Choose a
    [project](https://cloud.google.com/resource-manager/docs/creating-managing-projects)
    that has
    [billing enabled](https://cloud.google.com/billing/docs/how-to/verify-billing-enabled).

1.  Set the Google Cloud project you want to use:

    ```shell
    gcloud config set project PROJECT_ID
    ```

    Replace `PROJECT_ID` with the
    [project ID](https://cloud.google.com/resource-manager/docs/creating-managing-projects)
    of the Google Cloud project you want to use.

1.  Define and export environment variables that you use to configure resources
    required to run the controller:

    ```shell
    export PROJECT_ID="$(gcloud config get project 2> /dev/null)"
    export PROJECT_NUMBER="$(gcloud projects describe $PROJECT_ID --format 'value(projectNumber)')"
    ```

1.  Enable the Compute Engine, Identity and Access Management (IAM), and
    Security Token Service APIs on your Google Cloud project:

    ```shell
    gcloud services enable \
      compute.googleapis.com \
      iam.googleapis.com \
      sts.googleapis.com
    ```

1.  Install and configure the
    [Azure Command-Line Interface (CLI)](https://learn.microsoft.com/en-us/cli/azure/)
    command-line tool (`az`).

1.  To build the container image for the controller and render the Kubernetes
    manifests, install _all_ of the following:

    - [Go v1.23.0 or later](https://go.dev/dl/)
    - [Kustomize v4.5.5 or later](https://kubectl.docs.kubernetes.io/installation/kustomize/)
    - [Skaffold v2.10.1 or later](https://skaffold.dev/docs/install/)

1.  To configure authentication to Azure Container Registry, install the
    [`crane`](https://github.com/google/go-containerregistry/blob/main/cmd/crane/README.md#crane)
    command-line tool.

    You can skip this step if you already have Docker Desktop or Docker Engine
    installed, and you have already configured Docker authentication to the
    `loginServer` of your private container image registry in Azure Container
    Registry (see `$HOME/.docker/config.json`).

1.  Clone the Git repository and navigate to the directory
    `projects/k8s-hybrid-neg-controller`.

## Authenticate to your private registry in Azure Container Registry

The private registry is used to store and serve the `k8s-hybrid-neg-controller`
container image.

1.  Enable the Skaffold `ko` builder to authenticate to your private container
    image registry in Azure Container Registry:

    ```shell
    ACR_NAME=<your private container image registry name>
    ACR_RESOURCE_GROUP=<your Azure resource group that contains your registry>

    ACR_LOGIN_SERVER=$(az acr show \
      --name $ACR_NAME \
      --expose-token \
      --resource-group $ACR_RESOURCE_GROUP \
      --output tsv \
      --query loginServer)

    az acr login \
      --name $ACR_NAME \
      --expose-token \
      --resource-group $ACR_RESOURCE_GROUP \
      --output tsv \
      --query accessToken | \
      crane auth login \
        --username 00000000-0000-0000-0000-000000000000 \
        --password-stdin \
        $ACR_LOGIN_SERVER
    ```

    You can skip this step if you have already configured Docker Desktop or
    Docker Engine authentication to the `loginServer` of your private container
    image registry in Azure Container Registry.

    If you don't use an Azure resource group for your private container image
    registry in Azure Container Registry, remove the `--resource-group` flags in
    the commands above.

## Configure Workload Identity Federation with Kubernetes

Allow `k8s-hybrid-neg-controller` to authenticate to Google Cloud APIs using
Kubernetes ServiceAccount tokens from a
[projected volume](https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/#serviceaccount-token-volume-projection),
by configuring
[Workload Identity Federation with Kubernetes](https://cloud.google.com/iam/docs/workload-identity-federation-with-kubernetes).

1.  Get the AKS cluster's OpenID Connect (OIDC) issuer URL and save it as an
    environment variable:

    ```shell
    AKS_CLUSTER_NAME=<your AKS cluster name>
    AKS_RESOURCE_GROUP=<your Azure resource group that contains your AKS cluster>

    ISSUER_URL=$(az aks show \
      --name $AKS_CLUSTER_NAME
      --resource-group $AKS_RESOURCE_GROUP \
      --output tsv \
      --query "oidcIssuerProfile.issuerUrl")
    ```

    If you don't use an Azure resource group for your AKS cluster, remove the
    `--resource-group` flag in the command above.

1.  Create a
    [workload identity pool](https://cloud.google.com/iam/docs/workload-identity-federation#pools):

    ```shell
    export WORKLOAD_IDENTITY_POOL=hybrid-neg

    gcloud iam workload-identity-pools create ${WORKLOAD_IDENTITY_POOL} \
      --description "For Hybrid NEG Controllers running in Kubernetes clusters" \
      --display-name "Hybrid NEG Controller Manager" \
      --location global
    ```

    You can use a different name for the workload identity pool if you like.

1.  Add the AKS cluster's OIDC issuer as a
    [workload identity pool provider](https://cloud.google.com/iam/docs/workload-identity-federation#providers)
    to the workload identity pool:

    ```shell
    export WORKLOAD_IDENTITY_PROVIDER=hybrid-neg-provider

    gcloud iam workload-identity-pools providers create-oidc $WORKLOAD_IDENTITY_PROVIDER \
      --attribute-mapping "google.subject=assertion.sub,attribute.namespace=assertion['kubernetes.io']['namespace'],attribute.service_account_name=assertion['kubernetes.io']['serviceaccount']['name']" \
      --issuer-uri "$ISSUER_URL" \
      --location global \
      --workload-identity-pool $WORKLOAD_IDENTITY_POOL
    ```

    You can use a different name for the workload identity pool provider if you
    like.

    IAM roles in Google Cloud can be granted to identities in a workload
    identity pool. If you plan to deploy `k8s-hybrid-neg-controller` to multiple
    Kubernetes clusters outside Google Cloud, you can grant the same permissions
    to all of the `k8s-hybrid-neg-controller` instances by adding each cluster's
    OIDC issuer as a provider to the same workload identity pool.

    Alternatively, if you want to manage the permissions of
    `k8s-hybrid-neg-controller` in each cluster separately, you can create a
    workload identity pool for each Kubernetes clusters outside Google Cloud.

    To learn more about IAM quotas and limits on Google Cloud, see the
    [IAM quotas and limits](https://cloud.google.com/iam/quotas).

1.  Create a
    [custom IAM role](https://cloud.google.com/iam/docs/creating-custom-roles)
    with permission to manage zonal network endpoint groups (NEGs):

    ```shell
    gcloud iam roles create compute.networkEndpointGroupAdmin \
      --description "Full control of zonal Network Endpoint Groups (NEGs)" \
      --permissions "compute.instances.use,compute.networkEndpointGroups.attachNetworkEndpoints,compute.networkEndpointGroups.create,compute.networkEndpointGroups.createTagBinding,compute.networkEndpointGroups.delete,compute.networkEndpointGroups.deleteTagBinding,compute.networkEndpointGroups.detachNetworkEndpoints,compute.networkEndpointGroups.get,compute.networkEndpointGroups.list,compute.networkEndpointGroups.listEffectiveTags,compute.networkEndpointGroups.listTagBindings,compute.networkEndpointGroups.use,compute.zones.list" \
      --project $PROJECT_ID \
      --stage GA \
      --title "Zonal Network Endpoint Groups Admin"
    ```

    This custom role provides permissions to manage zonal
    [network endpoint groups](https://cloud.google.com/load-balancing/docs/negs)
    using the
    [Compute Engine API](https://cloud.google.com/compute/docs/reference/rest/v1/networkEndpointGroups).

    You can create the custom role at the
    [organization](https://cloud.google.com/resource-manager/docs/creating-managing-organization)
    level instead of at the project level, by replacing the `--project` flag
    with the `--organization` flag and your organization resource ID.

    You can use predefined roles, such as the
    [Kubernetes Engine Service Agent role](https://cloud.google.com/iam/docs/understanding-roles#container.serviceAgent)
    (`container.serviceAgent`), instead of creating a custom role. However, the
    predefined roles typically provide additional permissions that aren’t needed
    to manage zonal NEGs.

1.  Grant the custom IAM role on the Google Cloud project to the federated
    identity in the workload identity pool that represents the Kubernetes
    ServiceAccount of the controller manager:

    ```shell
    gcloud projects add-iam-policy-binding $PROJECT_ID \
      --member "principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WORKLOAD_IDENTITY_POOL}/subject/system:serviceaccount:hybrid-neg-system:hybrid-neg-controller-manager" \
      --role projects/${PROJECT_ID}/roles/compute.networkEndpointGroupAdmin
    ```

1.  Create a
    [credential configuration](https://cloud.google.com/iam/docs/workload-download-cred-and-grant-access)
    file:

    ```shell
    gcloud iam workload-identity-pools create-cred-config \
      projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WORKLOAD_IDENTITY_POOL}/providers/${WORKLOAD_IDENTITY_PROVIDER} \
      --credential-source-file /var/run/secrets/iam.googleapis.com/token \
      --credential-source-type text \
      --output-file k8s/components/secure-token-service/credential-configuration.json
    ```

    The controller manager uses the credential configuration file to
    authenticate to the Compute Engine API, using the
    [Application Default Credentials (ADC)](https://cloud.google.com/docs/authentication/application-default-credentials)
    authentication strategy that is implemented in Google Cloud
    [client libraries](https://cloud.google.com/apis/docs/client-libraries-explained).

1.  Create a patch that adds a
    [`serviceAccountToken` projected volume](https://kubernetes.io/docs/concepts/storage/projected-volumes/#serviceaccounttoken)
    to the controller manager Pod spec:

    ```shell
    echo PROJECT_NUMBER=$PROJECT_NUMBER
    echo WORKLOAD_IDENTITY_POOL=$WORKLOAD_IDENTITY_POOL
    echo WORKLOAD_IDENTITY_PROVIDER=$WORKLOAD_IDENTITY_PROVIDER

    eval "echo \"$(cat k8s/components/secure-token-service/patch-google-sts-token-volume.yaml.template)\"" \
      > k8s/components/secure-token-service/patch-google-sts-token-volume.yaml
    ```

## Configure the controller

1.  Create a patch that sets the Google Cloud project ID as an environment
    variable in the controller manager Pod spec:

    ```shell
    echo PROJECT_ID=$PROJECT_ID

    eval "echo \"$(cat k8s/components/google-cloud-project-id/patch-google-cloud-project-id.yaml.template)\"" \
      > k8s/components/google-cloud-project-id/patch-google-cloud-project-id.yaml
    ```

1.  Create a patch that sets the name of your
    [VPC network on Google Cloud](https://cloud.google.com/vpc/docs/vpc) as an
    environment variable in the controller manager Pod spec:

    ```shell
    export NETWORK=VPC_NETWORK

    eval "echo \"$(cat k8s/components/google-cloud-vpc-network/patch-google-cloud-vpc-network.yaml.template)\"" \
      > k8s/components/google-cloud-vpc-network/patch-google-cloud-vpc-network.yaml
    ```

    Replace `VPC_NETWORK` with the
    [name of the VPC network](https://cloud.google.com/vpc/docs/vpc) you want
    the controller to use.

    You can list the VPC networks in your project with this command:

    ```shell
    gcloud compute networks list --project $PROJECT_ID
    ```

1.  Define the mapping of Kubernetes cluster Node zones to
    [Compute Engine zones](https://cloud.google.com/compute/docs/regions-zones)
    for creating zonal hybrid NEGs and adding network endpoints to the NEGs.

    ```shell
    export ZONE_MAPPING=<your zone mapping>

    eval "echo \"$(cat k8s/components/zone-mapping-flag/patch-zone-mapping-flag.yaml.template)\"" \
      > k8s/components/zone-mapping-flag/patch-zone-mapping-flag.yaml
    ```

    The value of the `ZONE_MAPPING` environment variable is a comma-separated
    list of mappings from Kubernetes cluster Node zones to Compute Engine zones.

    For instance, if you Kubernetes cluster Nodes are in the zones
    `uksouth-{1,2,3}`, and you want `k8s-hybrid-neg-controller` to map network
    endpoints in these zones to NEGs in the Compute Engine zones
    `europe-west2-{a,b,c}`, use the following value for `ZONE_MAPPING`:

    ```shell
    uksouth-1=europe-west2-a,uksouth-2=europe-west2-b,uksouth-3=europe-west2-c
    ```

    You can list the zone labels
    ([`topology.kubernetes.io/zone`](https://kubernetes.io/docs/reference/labels-annotations-taints/#topologykubernetesiozone))
    of your Kubernetes cluster Nodes with this command:

    ```shell
    kubectl get nodes --output go-template='{{range .items}}{{index .metadata.labels "topology.kubernetes.io/zone"}}{{"\n"}}{{end}}' | sort | uniq
    ```

    You can list the Compute Engine zones with this command:

    ```shell
    gcloud compute zones list
    ```

    If you have workloads deployed across both Google Cloud and other clouds, we
    suggest that you configure zone mappings that minimizes network latency
    between endpoints on different clouds.

    Multiple Kubernetes cluster Node zones can map to the same Compute Engine
    zone.

    For an example of a populated `ZONE_MAPPING` value, see the
    `../k8s/components/zone-mapping-flag-kind/patch-zone-mapping-flag-kind.yaml`.

## Build and deploy the controller

1.  Optional: Verify that you can build the controller manager binary:

    ```shell
    make build
    ```

    If this step fails, ensure that you have the required tools installed, as
    documented in the section [Before you begin](#before-you-begin).

1.  Build the controller manager container image, render the manifests, deploy
    to the Kubernetes cluster, and tail the controller manager logs:

    ```shell
    ACR_NAME=<your private container image registry name>
    ACR_RESOURCE_GROUP=<your Azure resource group that contains your registry>
    ACR_LOGIN_SERVER=$(az acr show \
      --name $ACR_NAME \
      --expose-token \
      --resource-group $ACR_RESOURCE_GROUP \
      --output tsv \
      --query loginServer)

    export SKAFFOLD_DEFAULT_REPO=$ACR_LOGIN_SERVER

    make run
    ```

    Press `Ctrl + C` to stop tailing the controller manager logs. This does not
    stop the controller manager Pods. If you want to start tailing the
    controller manager logs again, run `make tail`.

## Verify that the controller can create hybrid NEGs

1.  Create a Kubernetes Deployment resource with Pods running nginx, and expose
    them using a Kubernetes Service that has the
    `solutions.cloud.google.com/hybrid-neg` annotation:

    ```shell
    kubectl apply --namespace=default \
      --filename=./hack/nginx-service.yaml,./hack/nginx-deployment-docker-hub.yaml
    ```

1.  Verify that the controller created one hybrid NEG in each of the Compute
    Engine zones that you configured in your zone mapping:

    ```shell
    gcloud compute network-endpoint-groups list \
      --filter 'name=nginx-80 AND networkEndpointType:NON_GCP_PRIVATE_IP_PORT'
    ```

    The output should look similar to the following, but the locations will be
    the Compute Engine zones you configured in your zone mapping:

    ```shell
    NAME      LOCATION    ENDPOINT_TYPE            SIZE
    nginx-80  us-west1-a  NON_GCP_PRIVATE_IP_PORT  1
    nginx-80  us-west1-b  NON_GCP_PRIVATE_IP_PORT  1
    nginx-80  us-west1-c  NON_GCP_PRIVATE_IP_PORT  0
    ```

1.  Verify that the hybrid NEGs in your Compute Engine zones have two
    `networkEndpoints` in total:

    ```shell
    for zone in <your Compute Engine zones> ; do
      gcloud compute network-endpoint-groups list-network-endpoints nginx-80 \
        --format yaml \
        --zone $zone
    done
    ```

    The output looks similar to the following:

    ```yaml
    ---
    networkEndpoint:
      instance: ''
      ipAddress: 10.30.1.5
      port: 80
    ---
    networkEndpoint:
      instance: ''
      ipAddress: 10.30.2.5
      port: 80
    ```

## Verify that the controller can delete hybrid NEGs

1.  Remove the `solutions.cloud.google.com/hybrid-neg` from the `nginx`
    Kubernetes Service:

    ```shell
    kubectl annotate service/nginx --namespace=default \
      solutions.cloud.google.com/hybrid-neg-
    ```

1.  Verify that the controller deleted the hybrid NEGs:

    ```shell
    gcloud compute network-endpoint-groups list \
      --filter 'name=nginx-80 AND networkEndpointType:NON_GCP_PRIVATE_IP_PORT'
    ```

    The output matches the following:

    ```shell
    Listed 0 items.
    ```

    It may take a few seconds for the controller to delete the hybrid NEGs.

## Troubleshoot

If you run into problems, please review the
[troubleshooting guide](troubleshoot.md).

## Clean up

These clean-up steps do not delete the container image from your private
container image registry in Azure Container Registry, and they do not delete
your AKS cluster.

1.  Set up environment variables to use in the following steps:

    ```shell
    PROJECT_ID="$(gcloud config get project 2> /dev/null)"
    PROJECT_NUMBER="$(gcloud projects describe $PROJECT_ID --format 'value(projectNumber)')"
    WORKLOAD_IDENTITY_POOL=hybrid-neg
    WORKLOAD_IDENTITY_PROVIDER=hybrid-neg-provider
    ```

1.  Undeploy `k8s-hybrid-neg-controller` from the AKS cluster:

    ```shell
    make delete
    ```

1.  Delete the workload identity pool provider:

    ```shell
    gcloud iam workload-identity-pools providers delete $WORKLOAD_IDENTITY_PROVIDER \
      --location global \
      --quiet \
      --workload-identity-pool $WORKLOAD_IDENTITY_POOL
    ```

1.  Delete the workload identity pool:

    ```shell
    gcloud iam workload-identity-pools delete $WORKLOAD_IDENTITY_POOL \
      --location global \
      --quiet
    ```

1.  Delete the custom IAM role:

    ```shell
    gcloud iam roles delete compute.networkEndpointGroupAdmin \
      --project $PROJECT_ID
    ```

1.  Verify that the controller deleted the hybrid NEGs:

    ```shell
    gcloud compute network-endpoint-groups list \
      --filter 'name=nginx-80 AND networkEndpointType:NON_GCP_PRIVATE_IP_PORT'
    ```

    The output matches the following:

    ```shell
    Listed 0 items.
    ```

    To delete NEGs manually, use the command
    [`gcloud compute network-endpoint-groups delete`](https://cloud.google.com/sdk/gcloud/reference/compute/network-endpoint-groups/delete).
