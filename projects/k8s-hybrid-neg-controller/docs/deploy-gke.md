# Deploy to a Google Kubernetes Engine (GKE) cluster

Follow the instructions below to set up a
[Google Kubernetes Engine (GKE)](https://cloud.google.com/kubernetes-engine/docs)
cluster and a container image repository in
[Artifact Registry](https://cloud.google.com/artifact-registry/docs) for
building and running the controller.

## Costs

In this document, you use the following billable components of Google Cloud:

- [Artifact Registry](https://cloud.google.com/artifact-registry/pricing)
- [Cloud NAT](https://cloud.google.com/nat/pricing)
- [Compute Engine](https://cloud.google.com/compute/all-pricing)
- [Google Kubernetes Engine (GKE)](https://cloud.google.com/kubernetes-engine/pricing)

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

1.  Install `kubectl` and `gke-gcloud-auth-plugin`:

    ```shell
    gcloud components install kubectl gke-gcloud-auth-plugin
    ```

    `gke-gcloud-auth-plugin` enables `kubectl` to authenticate to GKE clusters
    using credentials obtained using `gcloud`.

1.  To build the binary and the container image for the controller, install
    _all_ of the following:

    - [Go v1.23.0 or later](https://go.dev/dl/)
    - [Kustomize v4.5.5 or later](https://kubectl.docs.kubernetes.io/installation/kustomize/)
    - [Skaffold v2.10.1 or later](https://skaffold.dev/docs/install/)

1.  Set the Google Cloud project you want to use:

    ```shell
    gcloud config set project PROJECT_ID
    ```

    Replace `PROJECT_ID` with the
    [project ID](https://cloud.google.com/resource-manager/docs/creating-managing-projects)
    of the Google Cloud project you want to use.

1.  Enable the Artifact Registry and GKE APIs:

    ```shell
    gcloud services enable \
      artifactregistry.googleapis.com \
      container.googleapis.com
    ```

1.  Clone the Git repository and navigate to the directory
    `projects/k8s-hybrid-neg-controller`.

## Firewall rules

1.  If this is a temporary project, create a firewall rule that allows all TCP,
    UDP, and ICMP traffic within your VPC network:

    ```shell
    gcloud compute firewall-rules create allow-internal \
      --allow tcp,udp,icmp \
      --network default \
      --source-ranges "10.0.0.0/8"
    ```

    If you are unable to create such a wide rule, you can instead create more
    specific firewall rules that only allow traffic between your GKE cluster
    nodes.

1.  Create a firewall rule that allows health checks from Google Cloud Load
    Balancers to Compute Engine instances in your VPC network that have the
    `allow-health-checks` network tag:

    ```shell
    gcloud compute firewall-rules create allow-health-checks \
      --allow tcp \
      --network default \
      --source-ranges "35.191.0.0/16,130.211.0.0/22" \
      --target-tags allow-health-checks
    ```

## Artifact Registry setup

1.  Define environment variables that you use when creating the Artifact
    Registry container image repository:

    ```shell
    REGION=us-west1
    AR_LOCATION="$REGION"
    AR_REPOSITORY=hybrid-neg
    PROJECT_ID="$(gcloud config get project 2> /dev/null)"
    PROJECT_NUMBER="$(gcloud projects describe $PROJECT_ID --format 'value(projectNumber)')"
    ```

    Note the following about the environment variables:

    - `REGION`: the
      [Compute Engine region](https://cloud.google.com/compute/docs/regions-zones)
      where you have or will create your GKE cluster..
    - `AR_LOCATION`: an
      [Artifact Registry location](https://cloud.google.com/artifact-registry/docs/repositories/repo-locations).
      In order to reduce network cost, you can use the region that you will use
      for your GKE cluster. If you have GKE clusters in multiple regions, you
      may consider using a multi-region location such as `us`.
    - `AR_REPOSITORY`: the repository name. You can use a different name if you
      like.
    - `PROJECT_ID`: the project ID of your
      [Google Cloud project](https://cloud.google.com/resource-manager/docs/creating-managing-projects).
    - `PROJECT_NUMBER`: the automatically generate project number of your
      [Google Cloud project](https://cloud.google.com/resource-manager/docs/creating-managing-projects).

1.  Create a container image repository in Artifact Registry:

    ```shell
    gcloud artifacts repositories create $AR_REPOSITORY \
      --location $AR_LOCATION \
      --repository-format docker
    ```

1.  Configure authentication for `gcloud` and other command-line tools to the
    Artifact Registry host of your repository location:

    ```shell
    gcloud auth configure-docker "${AR_LOCATION}-docker.pkg.dev"
    ```

1.  Grant the
    [Artifact Registry Reader role](https://cloud.google.com/artifact-registry/docs/access-control#roles)
    on the container image repository to the IAM service account assigned to the
    GKE cluster nodes. By default, this is the
    [Compute Engine default service account](https://cloud.google.com/compute/docs/access/service-accounts#default_service_account):

    ```shell
    gcloud artifacts repositories add-iam-policy-binding $AR_REPOSITORY \
      --location "$AR_LOCATION" \
      --member "serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
      --role roles/artifactregistry.reader
    ```

## Create the Google Kubernetes Engine (GKE) cluster

1.  Create GKE cluster:

    ```shell
    gcloud container clusters create hybrid-neg \
      --enable-dataplane-v2 \
      --enable-ip-alias \
      --enable-l4-ilb-subsetting \
      --enable-master-global-access \
      --enable-private-nodes \
      --gateway-api standard \
      --location "$REGION" \
      --network default \
      --release-channel rapid \
      --subnetwork default \
      --workload-pool "${PROJECT_ID}.svc.id.goog" \
      --enable-autoscaling \
      --max-nodes 3 \
      --min-nodes 1 \
      --num-nodes 1 \
      --scopes cloud-platform,userinfo-email \
      --tags allow-health-checks,hybrid-neg-cluster-node \
      --workload-metadata GKE_METADATA

    kubectl config set-context --current --namespace=hybrid-neg-system
    ```

1.  Allow access to the cluster API server from your current public IP address,
    and from private IP addresses in your VPC network:

    ```shell
    PUBLIC_IP="$(dig TXT +short o-o.myaddr.l.google.com @ns1.google.com | sed 's/"//g')"

    gcloud container clusters update hybrid-neg \
      --enable-master-authorized-networks \
      --location "$REGION" \
      --master-authorized-networks "${PUBLIC_IP}/32,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
    ```

    If you want to allow access from other IP address ranges, or if you use
    [non-RFC1918 IPv4 address ranges](https://cloud.google.com/vpc/docs/subnets#valid-ranges)
    for your GKE cluster nodes and/or Pods, add those address ranges to the
    `--master-authorized-networks` flag.

## Configure Workload Identity Federation for GKE

Allow the controller manager to authenticate to Google Cloud APIs, by using
[Workload Identity Federation for GKE](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity)
to grant an IAM role to the controller's Kubernetes service account.

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

1.  Grant the custom IAM role on the Google Cloud project to the
    `hybrid-neg-controller-manager` Kubernetes service account in the
    `hybrid-neg-system` namespace:

    ```shell
    gcloud projects add-iam-policy-binding $PROJECT_ID \
      --member "principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${PROJECT_ID}.svc.id.goog/subject/ns/hybrid-neg-system/sa/hybrid-neg-controller-manager" \
      --role projects/$PROJECT_ID/roles/compute.networkEndpointGroupAdmin
    ```

## Configure the controller

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

## Deploy the hybrid NEG controller

1.  Create and export an environment variable called `SKAFFOLD_DEFAULT_REPO` to
    point to your container image registry:

    ```shell
    export SKAFFOLD_DEFAULT_REPO=$AR_LOCATION-docker.pkg.dev/$PROJECT_ID/$AR_REPOSITORY
    ```

1.  Build the controller manager container image, render the manifests, deploy
    to the GKE cluster, and tail the logs:

    ```shell
    make run
    ```

## Verify that the controller can create hybrid NEGs

1.  Create a Kubernetes Deployment resource with Pods running nginx, and expose
    them using a Kubernetes Service that has the
    `solutions.cloud.google.com/hybrid-neg` annotation:

    ```shell
    kubectl apply --namespace=default \
      --filename=./hack/nginx-service.yaml,./hack/nginx-deployment-gcr.yaml
    ```

1.  Verify that the controller created one hybrid NEG in each of the Compute
    Engine zones `us-west1-{a,b,c}`:

    ```shell
    gcloud compute network-endpoint-groups list \
      --filter 'name=nginx-80 AND networkEndpointType:NON_GCP_PRIVATE_IP_PORT'
    ```

    The output looks similar to the following:

    ```shell
    NAME      LOCATION    ENDPOINT_TYPE            SIZE
    nginx-80  us-west1-a  NON_GCP_PRIVATE_IP_PORT  1
    nginx-80  us-west1-b  NON_GCP_PRIVATE_IP_PORT  1
    nginx-80  us-west1-c  NON_GCP_PRIVATE_IP_PORT  0
    ```

1.  Verify that the hybrid NEGs in zones `us-west1-{a,b,c}` have two
    `networkEndpoints` in total:

    ```shell
    for zone in us-west1-a us-west1-b us-west1-c ; do
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

1.  Set up environment variables:

    ```shell
    PROJECT_ID="$(gcloud config get project 2> /dev/null)"
    PROJECT_NUMBER="$(gcloud projects describe $PROJECT_ID --format 'value(projectNumber)')"
    REGION=us-west1
    AR_LOCATION=$REGION
    AR_REPOSITORY=hybrid-neg
    ```

1.  Undeploy the controller manager from the GKE cluster:

    ```shell
    make delete
    ```

1.  Delete the GKE cluster:

    ```shell
    gcloud container clusters delete hybrid-neg \
      --async \
      --location $REGION \
      --quiet
    ```

1.  Delete the container image repository in Artifact Registry:

    ```shell
    gcloud artifacts repositories delete $AR_REPOSITORY \
      --async \
      --location $AR_LOCATION \
      --quiet
    ```

1.  Remove the IAM policy binding:

    ```shell
    gcloud projects remove-iam-policy-binding $PROJECT_ID \
      --member "principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${PROJECT_ID}.svc.id.goog/subject/ns/hybrid-neg-system/sa/hybrid-neg-controller-manager" \
      --role projects/$PROJECT_ID/roles/compute.networkEndpointGroupAdmin
    ```
