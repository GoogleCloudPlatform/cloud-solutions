# Game servers on Axion

## Requirements

To deploy this demo, you need:

- A Google Cloud project.
- An account that has the `owner` role on that Google Cloud project.

## Prepare the environment

1.  Open
    [Cloud Shell](https://cloud.google.com/shell/docs/launching-cloud-shell).

1.  Configure environment variables:

    ```bash
    AGONES_NS="agones-system"
    AGONES_VER="1.49.0"
    CONTAINER_IMAGE_REPOSITORY_NAME="arm-gaming-demo"
    PROJECT_ID="<PROJECT_ID>"
    LOCATION="<LOCATION>"
    GKE_CLUSTER_NAME="arm-gaming-demo"
    GAME_SERVER_CONTAINER_IMAGE_URL="${LOCATION}-docker.pkg.dev/${PROJECT_ID}/${CONTAINER_IMAGE_REPOSITORY_NAME}/supertuxkart-example:0.17"
    export GAME_SERVER_CONTAINER_IMAGE_URL
    ```

    Where:

    - `<PROJECT_ID>` is the ID of your Google Cloud project.
    - `<LOCATION>` is the location where to provision cloud resources. Example:
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
      --location="${LOCATION}"
    ```

1.  Create a VPC network and a subnet:

    ```bash
    gcloud compute networks create "${GKE_CLUSTER_NAME}" \
      --subnet-mode=auto
    ```

1.  Create a Google Kubernetes Engine (GKE) autopilot cluster:

    ```bash
    gcloud container clusters create-auto "${GKE_CLUSTER_NAME}" \
      --autoprovisioning-network-tags=game-server \
      --location="${LOCATION}" \
      --network="${GKE_CLUSTER_NAME}" \
      --project="${PROJECT_ID}"
    ```

1.  Configure firewall rules to allow connections to game servers running in the
    cluster:

    ```bash
    gcloud compute firewall-rules create gke-game-server-firewall \
      --allow tcp:7000-8000,udp:7000-8000 \
      --target-tags game-server \
      --description "Allow game server TCP and UDP traffic" \
      --network="${GKE_CLUSTER_NAME}"
    ```

1.  Configure the cluster connection:

    ```bash
    gcloud container clusters get-credentials "${GKE_CLUSTER_NAME}" \
    --location="${LOCATION}" \
    --project="${PROJECT_ID}"
    ```

## Build the game server for arm64

1.  Build the game server container image for the `arm64` architecture, and push
    it to the registry:

    ```bash
    gcloud builds submit \
      --config=projects/arm-reference-guides/gaming-demo/cloud-build/game-server.yaml \
      --project "${PROJECT_ID}" \
      --region "${LOCATION}" \
      --substitutions=_LOCATION="${LOCATION}",_REPOSITORY="${CONTAINER_IMAGE_REPOSITORY_NAME}" \
      --machine-type=e2-highcpu-8
    ```

    The container image build takes about 25 minutes.

## Deploy backend services

1.  Configure Helm:

    ```bash
    helm repo add agones https://agones.dev/chart/stable
    helm repo update
    ```

1.  Install Agones:

    ```bash
    helm install agones --namespace "${AGONES_NS}" \
      --create-namespace "agones/agones" \
      --values projects/arm-reference-guides/gaming-demo/kubernetes-manifests/helm-agones-values.yaml \
      --version "${AGONES_VER}"
    ```

1.  Deploy game servers:

    ```bash
    envsubst <projects/arm-reference-guides/gaming-demo/kubernetes-manifests/game-server.yaml | sponge projects/arm-reference-guides/gaming-demo/kubernetes-manifests/game-server.yaml
    kubectl apply -f projects/arm-reference-guides/gaming-demo/kubernetes-manifests/game-server.yaml
    ```

1.  Get information about the game server fleet:

    ```bash
    kubectl get fleet
    ```

    The output is similar to the following:

    ```text
    NAME           SCHEDULING   DESIRED   CURRENT   ALLOCATED   READY   AGE
    supertuxkart   Packed       2         2         0           2       3m55s
    ```

1.  Take note of the game server external IP address and port:

    ```bash
    kubectl get gameservers
    ```

    The output is similar to the following:

    ```text
    NAME                       STATE   ADDRESS        PORT   NODE                                             AGE
    supertuxkart-j8n8g-5glfr   Ready   REDACTED       7047   gk3-arm-gaming-demo-nap-redacted                 4m36s
    supertuxkart-j8n8g-xdp74   Ready   REDACTED       7672   gk3-arm-gaming-demo-nap-redacted                 4m36s
    ```

## Connect to the game server

On a host where you have access to a graphical desktop interface:

1.  Download the [game client](https://supertuxkart.net/Download)

1.  Start the game client you downloaded earlier by running the executable for
    your operating system.

1.  Navigate to Online Play: from the main menu, select the “Online” option and
    then select “Enter server address” from the available options.

1.  Enter Server Details: In the subsequent screen, you will be prompted to
    input the IP address and port number in order to join the game. Enter the IP
    address and port number obtained from the kubectl get gameservers command.

1.  Join the Game: After entering the server details, proceed to join the
    server. You should now be connected to your Agones-managed game server and
    ready to play.

## Destroying the demo

To destroy the demo environment, you do the following:

1.  Destroy firewall rules:

    ```bash
    gcloud compute firewall-rules delete gke-game-server-firewall \
      --quiet
    ```

1.  Destroy the GKE cluster

    ```bash
    gcloud container clusters delete "${GKE_CLUSTER_NAME}" \
      --location="${LOCATION}" \
      --quiet
    ```

1.  Destroy the VPC network

    ```bash
    gcloud compute networks delete "${GKE_CLUSTER_NAME}" \
      --quiet
    ```

1.  Destroy the Artifact Registry repository

    ```bash
    gcloud artifacts repositories delete "${CONTAINER_IMAGE_REPOSITORY_NAME}" \
      --location="${LOCATION}" \
      --quiet
    ```
