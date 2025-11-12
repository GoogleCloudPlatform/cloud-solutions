# Java and Web Stacks on Axion

## Requirements

To deploy this demo, you need:

- A Google Cloud project.
- An account that has the `owner` role on that Google Cloud project.
- To know the external IP that the client you will access the demo from appears
  as, you can check a site like
  [Whatis MyIPAddress](https://whatismyipaddress.com/) to find it out.

## Prepare the environment

1.  Open
    [Cloud Shell](https://cloud.google.com/shell/docs/launching-cloud-shell).

1.  Configure environment variables:

    ```bash
    CLIENT_IP="<CLIENT_IP>"
    PROJECT_ID="<PROJECT_ID>"
    REGION="<LOCATION>"
    CONTAINER_IMAGE_REPOSITORY_NAME="arm-web-demo"
    VPC_NAME="arm-web-demo"
    CLOUD_ROUTER_NAME="arm-web-demos-router"
    NAT_GATEWAY_NAME="arm-web-demos-nat"
    GKE_CLUSTER_NAME="auto-multi-arch-cluster"
    CATALOG_CONTAINER_IMAGE_URL="${LOCATION}-docker.pkg.dev/${PROJECT_ID}/${CONTAINER_IMAGE_REPOSITORY_NAME}/book-catalog-service:latest"
    UI_CONTAINER_IMAGE_URL="${LOCATION}-docker.pkg.dev/${PROJECT_ID}/${CONTAINER_IMAGE_REPOSITORY_NAME}/book-ui-service:latest"
    REVIEW_CONTAINER_IMAGE_URL="${LOCATION}-docker.pkg.dev/${PROJECT_ID}/${CONTAINER_IMAGE_REPOSITORY_NAME}/review-service:latest"
    K6_CONTAINER_IMAGE_URL="${LOCATION}-docker.pkg.dev/${PROJECT_ID}/${CONTAINER_IMAGE_REPOSITORY_NAME}/custom-k6:latest"
    export CATALOG_CONTAINER_IMAGE_URL
    export UI_CONTAINER_IMAGE_URL
    export REVIEW_CONTAINER_IMAGE_URL
    export K6_CONTAINER_IMAGE_URL
    ```

    Where:

    - `<CLIENT_IP>` is the external IP of your demo client machine.
    - `<PROJECT_ID>` is the ID of your Google Cloud project.
    - `<REGION>` is the location where to provision cloud resources. Example:
      `us-central1`

1.  Clone this repository:

    ```bash
    git clone https://github.com/GoogleCloudPlatform/cloud-solutions.git
    ```

1.  Change the working directory to the directory where you cloned this
    repository:

    ```bash
    cd cloud-solutions
    ```

1.  Select the Google Cloud project where to provision resources:

    ```bash
    gcloud config set project "${PROJECT_ID}"
    ```

## Provision and configure cloud infrastructure

1.  Enable Google Cloud APIs:

    ```bash
    gcloud services enable \
      artifactregistry.googleapis.com \
      cloudbuild.googleapis.com \
      container.googleapis.com
    ```

1.  Create a Artifact Registry repository for container images:

    ```bash
    gcloud artifacts repositories create "${CONTAINER_IMAGE_REPOSITORY_NAME}" \
      --repository-format=docker \
      --location="${REGION}"
    ```

1.  Create a VPC network with Auto subnets:

    ```bash
    gcloud compute networks create "${VPC_NAME}" \
      --subnet-mode=auto \
      --bgp-routing-mode=regional
    ```

1.  Create a Cloud Router for NAT Gateway:

    ```bash
    gcloud compute routers create "${CLOUD_ROUTER_NAME}" \
      --network="${VPC_NAME}" \
      --region="${REGION}"
    ```

1.  Create a NAT Gateway:

    ```bash
    gcloud compute routers nats create "${NAT_GATEWAY_NAME}" \
      --router="${CLOUD_ROUTER_NAME}" \
      --region="${REGION}" \
      --nat-all-subnet-ip-ranges \
      --auto-allocate-nat-external-ips
    ```

1.  Create a private Google Kubernetes Engine (GKE) autopilot cluster:

    ```bash
    gcloud container clusters create-auto "${GKE_CLUSTER_NAME}" \
    --region="${REGION}" \
    --release-channel=regular \
    --network="${VPC_NAME}" \
    --subnetwork=arm-demos \
    --enable-dns-access \
    --enable-private-endpoint \
    --enable-private-nodes \
    --enable-master-authorized-networks \
    --master-ipv4-cidr=172.16.2.0/28
    ```

1.  Configure the cluster connection:

    ```bash
    gcloud container clusters get-credentials "${GKE_CLUSTER_NAME}" \
    --location="${LOCATION}" \
    --project="${PROJECT_ID}" \
    --dns-endpoint
    ```

## Build the multi-arch container images

*Note, add the ```--machine-type=e2-highcpu-8``` option to the
below commands to speed up build times if applicable*

1.  Build the catalog service container image for both the `arm64` and `amd64`
    architecture, and push it to the registry:

    ```bash
    gcloud builds submit \
      --config=projects/arm-reference-guides/web-demo/book-catalog-service/cloudbuild.yaml projects/arm-reference-guides/web-demo/book-catalog-service \
      --project "${PROJECT_ID}" \
      --region "${LOCATION}" \
      --substitutions=_LOCATION="${LOCATION}",_REPOSITORY="${CONTAINER_IMAGE_REPOSITORY_NAME}"
    ```

1.  Build the review service container image for both the `arm64` and `amd64`
    architecture, and push it to the registry:

    ```bash
    gcloud builds submit \
      --config=projects/arm-reference-guides/web-demo/review-service/cloudbuild.yaml projects/arm-reference-guides/web-demo/review-service \
      --project "${PROJECT_ID}" \
      --region "${LOCATION}" \
      --substitutions=_LOCATION="${LOCATION}",_REPOSITORY="${CONTAINER_IMAGE_REPOSITORY_NAME}"
    ```

1.  Build the ui service container image for both the `arm64` and `amd64`
    architecture, and push it to the registry:

    ```bash
    gcloud builds submit \
      --config=projects/arm-reference-guides/web-demo/book-ui-service/cloudbuild.yaml projects/arm-reference-guides/web-demo/book-ui-service \
      --project "${PROJECT_ID}" \
      --region "${LOCATION}" \
      --substitutions=_LOCATION="${LOCATION}",_REPOSITORY="${CONTAINER_IMAGE_REPOSITORY_NAME}"
    ```

## Deploy services

1.  Prepare the cluster :

    ```bash
    kubectl apply -f projects/arm-reference-guides/web-demo/k8s-manifests/hdb-class.yaml
    kubectl apply -f projects/arm-reference-guides/web-demo/k8s-manifests/book-service-secrets.yaml
    ```

1.  Configure Helm:

    ```bash
    helm repo add bitnami https://charts.bitnami.com/bitnami
    helm repo add grafana https://grafana.github.io/helm-charts
    helm repo update
    ```

1.  Install an Arm based postgresql :

    ```bash
    helm install arm-postgres \
      --values projects/arm-reference-guides/web-demo/k8s-manifests/autopilot/arm-postgres-helm-values.yaml
    ```

1.  Install an Arm based redis :

    ```bash
    helm install arm-redis \
      --values projects/arm-reference-guides/web-demo/k8s-manifests/autopilot/arm-redis-helm-values.yaml
    ```

1.  Install an x64 based postgresql :

    ```bash
    helm install x64-postgres \
      --values projects/arm-reference-guides/web-demo/k8s-manifests/autopilot/x64-postgres-helm-values.yaml
    ```

1.  Install an x64 based redis :

    ```bash
    helm install x64-redis \
      --values projects/arm-reference-guides/web-demo/k8s-manifests/autopilot/x64-redis-helm-values.yaml
    ```

1.  Deploy the Arm based workloads :

    ```bash
    envsubst <projects/arm-reference-guides/web-demo/k8s-manifests/arm-book-service-deployment.yaml | sponge projects/arm-reference-guides/web-demo/k8s-manifests/arm-book-service-deployment.yaml
    envsubst <projects/arm-reference-guides/web-demo/k8s-manifests/arm-book-ui-deployment.yaml | sponge projects/arm-reference-guides/web-demo/k8s-manifests/arm-book-ui-deployment.yaml
    envsubst <projects/arm-reference-guides/web-demo/k8s-manifests/arm-review-service-deployment.yaml | sponge projects/arm-reference-guides/web-demo/k8s-manifests/arm-review-service-deployment.yaml
    kubectl apply -f projects/arm-reference-guides/web-demo/k8s-manifests/arm-book-service-deployment.yaml
    kubectl apply -f projects/arm-reference-guides/web-demo/k8s-manifests/arm-book-ui-deployment.yaml
    kubectl apply -f projects/arm-reference-guides/web-demo/k8s-manifests/arm-review-service-deployment.yaml
    ```

1.  Deploy the x64 based workloads :

    ```bash
    envsubst <projects/arm-reference-guides/web-demo/k8s-manifests/x64-book-service-deployment.yaml | sponge projects/arm-reference-guides/web-demo/k8s-manifests/x64-book-service-deployment.yaml
    envsubst <projects/arm-reference-guides/web-demo/k8s-manifests/x64-book-ui-deployment.yaml | sponge projects/arm-reference-guides/web-demo/k8s-manifests/x64-book-ui-deployment.yaml
    envsubst <projects/arm-reference-guides/web-demo/k8s-manifests/x64-review-service-deployment.yaml | sponge projects/arm-reference-guides/web-demo/k8s-manifests/ax64rm-review-service-deployment.yaml
    kubectl apply -f projects/arm-reference-guides/web-demo/k8s-manifests/x64-book-service-deployment.yaml
    kubectl apply -f projects/arm-reference-guides/web-demo/k8s-manifests/x64-book-ui-deployment.yaml
    kubectl apply -f projects/arm-reference-guides/web-demo/k8s-manifests/x64-review-service-deployment.yaml
    ```

1.  Deploy the Arm services :

    ```bash
    envsubst <projects/arm-reference-guides/web-demo/k8s-manifests/arm-book-ui-service.yaml | sponge projects/arm-reference-guides/web-demo/k8s-manifests/arm-book-ui-service.yaml
    kubectl apply -f projects/arm-reference-guides/web-demo/k8s-manifests/autopilot/arm-book-service-service.yaml
    kubectl apply -f projects/arm-reference-guides/web-demo/k8s-manifests/autopilot/arm-review-service-service.yaml
    kubectl apply -f projects/arm-reference-guides/web-demo/k8s-manifests/autopilot/arm-book-ui-service.yaml
    ```

1.  Deploy the x64 services :

    ```bash
    envsubst <projects/arm-reference-guides/web-demo/k8s-manifests/x64-book-ui-service.yaml | sponge projects/arm-reference-guides/web-demo/k8s-manifests/x64-book-ui-service.yaml
    kubectl apply -f projects/arm-reference-guides/web-demo/k8s-manifests/autopilot/x64-book-service-service.yaml
    kubectl apply -f projects/arm-reference-guides/web-demo/k8s-manifests/autopilot/x64-review-service-service.yaml
    kubectl apply -f projects/arm-reference-guides/web-demo/k8s-manifests/autopilot/x64-book-ui-service.yaml
    ```

## Exploring the environment

1.  Get information about the deployments :

    ```bash
    kubectl get deployments
    ```

    The output is similar to the following:

    ```text
    NAME                       READY   UP-TO-DATE   AVAILABLE   AGE
    arm-book-catalog-service   2/2     2            2           5m43s
    arm-book-ui-service        2/2     2            2           5m42s
    arm-review-service         2/2     2            2           5m42s
    x64-book-catalog-service   2/2     2            2           5m38s
    x64-book-ui-service        2/2     2            2           5m36s
    x64-review-service         2/2     2            2           5m37s
    ```

1.  Get information about the stateful worklads :

    ```bash
    kubectl get statefulsets
    ```

    The output is similar to the following:

    ```text
    NAME                     READY   AGE
    arm-postgres-svc         1/1     3h32m
    arm-redis-svc-master     1/1     131m
    arm-redis-svc-replicas   0/0     131m
    x64-postgres-svc         1/1     3h32m
    x64-redis-svc-master     1/1     131m
    x64-redis-svc-replicas   0/0     131m
    ```

    `The replicas in the above output should be 0/0`

1.  Take note of the Arm stacks external Loadbalancer IP address :

    ```bash
    echo "http://$(kubectl get service arm-book-ui-loadbalancer -o jsonpath='{.status.loadBalancer.ingress[0].ip}')"
    ```

1.  Take note of the x64 stacks external Loadbalancer IP address :

    ```bash
    echo "http://$(kubectl get service x64-book-ui-loadbalancer -o jsonpath='{.status.loadBalancer.ingress[0].ip}')"
    ```

## Connect to the demo

Visit those two URL's from the above steps, you should be greeted with a page
that displays the CPU architecture of each of the components in the stack.
aarch64 for Arm, and x64 for x64.

## Loading synthetic data

1.  Run the books.py script to generate synthetic data :

    ```bash
    python projects/arm-reference-guides/web-demo/books.py
    ```

    Download those files to your local machine via the download option behind
    the three dot menu in CloudShell. In your browser navigate to the bulk
    upload section of each stack and upload the three files. Once complete, you
    can navigate through the application and see it in action.

## Optional load testing

1.  Build the custom k6 container image for both the `arm64` and `amd64`
    architecture, and push it to the registry:

    ```bash
    gcloud builds submit \
      --config=projects/arm-reference-guides/web-demo/load-testing/cloudbuild.yaml projects/arm-reference-guides/web-demo/load-testing \
      --project "${PROJECT_ID}" \
      --region "${LOCATION}" \
      --substitutions=_LOCATION="${LOCATION}",_REPOSITORY="${CONTAINER_IMAGE_REPOSITORY_NAME}" \
      --machine-type=e2-highcpu-8
    ```

`This k6 image can take a while to build, around 15 minutes`

1.  Install an Arm based K6:

    ```bash
    helm install arm-k6-operator \
      --values projects/arm-reference-guides/web-demo/k8s-manifests/autopilot/arm-k6-operator-helm-values.yaml
    ```

## Destroying the demo

To destroy the demo environment, you do the following:

1.  Destroy the GKE cluster

    ```bash
    gcloud container clusters delete "${GKE_CLUSTER_NAME}" \
      --region="${REGION}" \
      --quiet
    ```

1.  Destroy the VPC network

    ```bash
    gcloud compute networks delete "${VPC_NAME}" \
      --quiet
    ```

1.  Destroy the Artifact Registry repository

    ```bash
    gcloud artifacts repositories delete "${CONTAINER_IMAGE_REPOSITORY_NAME}" \
      --location="${REGION}" \
      --quiet
    ```

1.  Destroy the Cloud Router

    ```bash
    gcloud compute routers delete "${CLOUD_ROUTER_NAME}" \
      --network="${VPC_NAME}" \
      --region="${REGION}" \
      --quiet

    ```

1.  Destroy the NAT Gateway

    ```bash
    gcloud compute routers nats delete "${NAT_GATEWAY_NAME}" \
      --region="${REGION}" \
      --quiet
    ```
