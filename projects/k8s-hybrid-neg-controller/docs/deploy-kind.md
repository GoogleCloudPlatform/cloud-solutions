# Deploy to a local `kind` Kubernetes cluster

Follow the instructions below to set up a local
[kind](https://kind.sigs.k8s.io/) Kubernetes cluster for building and running
the controller.

## Costs

In this document, you use the following billable components of Google Cloud:

-   [Compute Engine](https://cloud.google.com/compute/all-pricing)

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

1.  Install the `kubectl` Kubernetes client command-line tool:

    ```shell
    gcloud components install kubectl
    ```

1.  Install
    [`kind`](https://kind.sigs.k8s.io/docs/user/quick-start#installation).

    To create `kind` Kubernetes clusters, you need _one_ of the following:

    -   [Podman](https://podman.io/docs/installation), or
    -   [Docker Engine](https://docs.docker.com/engine/install/) (Linux only),
        or
    -   [Docker Desktop](https://docs.docker.com/desktop/).

1.  Install the [`jq`](https://jqlang.github.io/jq/download/) command-line tool.

1.  To build the binary and the container image for the controller, install
    _all_ of the following:

    -   [Go v1.23.0 or later](https://go.dev/dl/)
    -   [Kustomize v4.5.5 or later](https://kubectl.docs.kubernetes.io/installation/kustomize/)
    -   [Skaffold v2.10.1 or later](https://skaffold.dev/docs/install/)

1.  Clone the Git repository and navigate to the directory
    `projects/k8s-hybrid-neg-controller`.

## Create the local `kind` Kubernetes cluster

1.  Create cluster:

    ```shell
    make kind-create
    ```

    This command creates a multi-node Kubernetes cluster with fake
    [`topology.kubernetes.io/zone` labels](https://kubernetes.io/docs/reference/labels-annotations-taints/#topologykubernetesiozone)
    to simulate a Kubernetes cluster with Nodes spread across multiple zones.

## Configure Workload Identity Federation with Kubernetes

Allow the controller manager to authenticate to Google Cloud APIs using
Kubernetes ServiceAccount tokens, by configuring
[Workload Identity Federation with Kubernetes](https://cloud.google.com/iam/docs/workload-identity-federation-with-kubernetes#kubernetes).

1.  Get the cluster's OpenID Connect issuer URL and save it as an environment
    variable:

    ```shell
    ISSUER_URL="$(kubectl get --raw /.well-known/openid-configuration | jq -r .issuer)"
    ```

1.  Download the cluster's JSON Web Key Set (JWKS):

    ```shell
    kubectl get --raw /openid/v1/jwks > cluster-jwks.json
    ```

1.  Create a workload identity pool:

    ```shell
    export WORKLOAD_IDENTITY_POOL=hybrid-neg

    gcloud iam workload-identity-pools create ${WORKLOAD_IDENTITY_POOL} \
      --description "For Hybrid NEG Controllers running in Kubernetes clusters" \
      --display-name "Hybrid NEG Controller Manager" \
      --location global
    ```

1.  Add the Kubernetes cluster OIDC issuer as a provider to the workload pool:

    ```shell
    export WORKLOAD_IDENTITY_PROVIDER=hybrid-neg-provider

    gcloud iam workload-identity-pools providers create-oidc $WORKLOAD_IDENTITY_PROVIDER \
      --attribute-mapping "google.subject=assertion.sub,attribute.namespace=assertion['kubernetes.io']['namespace'],attribute.service_account_name=assertion['kubernetes.io']['serviceaccount']['name']" \
      --issuer-uri "$ISSUER_URL" \
      --jwk-json-path cluster-jwks.json \
      --location global \
      --workload-identity-pool $WORKLOAD_IDENTITY_POOL
    ```

1.  Create a
    [custom IAM role](https://cloud.google.com/iam/docs/creating-custom-roles)
    with permissions to manage zonal network endpoint groups (NEGs):

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
    identity representing the Kubernetes service account of the controller:

    ```shell
    gcloud projects add-iam-policy-binding $PROJECT_ID \
      --member "principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WORKLOAD_IDENTITY_POOL}/subject/system:serviceaccount:hybrid-neg-system:hybrid-neg-controller-manager" \
      --role projects/$PROJECT_ID/roles/compute.networkEndpointGroupAdmin
    ```

1.  Create a credential configuration file:

    ```shell
    gcloud iam workload-identity-pools create-cred-config \
      projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WORKLOAD_IDENTITY_POOL}/providers/${WORKLOAD_IDENTITY_PROVIDER} \
      --credential-source-file /var/run/secrets/iam.googleapis.com/token \
      --credential-source-type text \
      --output-file k8s/components/secure-token-service/credential-configuration.json
    ```

1.  Create a patch that adds a
    [`serviceAccountToken` projected volume](https://kubernetes.io/docs/concepts/storage/projected-volumes/#serviceaccounttoken)
    to the controller Pod spec:

    ```shell
    echo PROJECT_NUMBER=$PROJECT_NUMBER
    echo WORKLOAD_IDENTITY_POOL=$WORKLOAD_IDENTITY_POOL
    echo WORKLOAD_IDENTITY_PROVIDER=$WORKLOAD_IDENTITY_PROVIDER

    eval "echo \"$(cat k8s/components/secure-token-service/patch-google-sts-token-volume.yaml.template)\"" \
      > k8s/components/secure-token-service/patch-google-sts-token-volume.yaml
    ```

## Configure the controller

1.  Create a patch that sets the Google Cloud project ID as an environment
    variable in the controller Pod spec:

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

## Build and deploy the controller

1.  Build the controller manager container image, render the manifests, deploy
    to the Kubernetes cluster, and tail the controller manager logs:

    ```shell
    make run
    ```

## Verify that the controller can create hybrid NEGs

1.  Create a Kubernetes Deployment resource with Pods running nginx, and expose
    them using a Kubernetes Service that has the
    `solutions.cloud.google.com/hybrid-neg` annotation:

    ```shell
    kubectl apply --namespace=default \
      --filename=./hack/nginx-service.yaml,./hack/nginx-deployment-docker-hub.yaml
    ```

1.  Verify that the controller created one hybrid NEG in each of the Compute
    Engine zones `us-west1-{a,b,c}`:

    ```shell
    gcloud compute network-endpoint-groups list \
      --filter 'name=nginx-80 AND networkEndpointType:NON_GCP_PRIVATE_IP_PORT'
    ```

    The output matches the following:

    ```shell
    NAME      LOCATION    ENDPOINT_TYPE            SIZE
    nginx-80  us-west1-a  NON_GCP_PRIVATE_IP_PORT  1
    nginx-80  us-west1-b  NON_GCP_PRIVATE_IP_PORT  1
    nginx-80  us-west1-c  NON_GCP_PRIVATE_IP_PORT  0
    ```

1.  Verify that the hybrid NEGs in zones `us-west1-{a,b}` have one endpoint
    each:

    ```shell
    for zone in us-west1-a us-west1-b ; do
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

1.  Set up environment variables to use in the following steps:

    ```shell
    PROJECT_ID="$(gcloud config get project 2> /dev/null)"
    PROJECT_NUMBER="$(gcloud projects describe $PROJECT_ID --format 'value(projectNumber)')"
    WORKLOAD_IDENTITY_POOL=hybrid-neg
    WORKLOAD_IDENTITY_PROVIDER=hybrid-neg-provider
    ```

1.  Undeploy `k8s-hybrid-neg-controller` from the `kind` Kubernetes cluster:

    ```shell
    make delete
    ```

1.  Delete the `kind` cluster:

    ```shell
    make kind-delete
    ```

1.  Delete the workload provider:

    ```shell
    gcloud iam workload-identity-pools providers delete $WORKLOAD_IDENTITY_PROVIDER \
      --location global \
      --quiet \
      --workload-identity-pool $WORKLOAD_IDENTITY_POOL
    ```

1.  Delete the workload pool:

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
      --filter 'networkEndpointType:NON_GCP_PRIVATE_IP_PORT'
    ```

    The output matches the following:

    ```shell
    Listed 0 items.
    ```

    To delete NEGs manually, use the command
    [`gcloud compute network-endpoint-groups delete`](https://cloud.google.com/sdk/gcloud/reference/compute/network-endpoint-groups/delete).
