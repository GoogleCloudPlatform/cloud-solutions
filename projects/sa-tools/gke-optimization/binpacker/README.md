# Binpacker

Scrape running workloads from Google Kubernetes Engine (GKE) standard clusters and provide binpacking recommendations for selected workloads.

Consists of 2 modules:

- UI

  The UI is implemented in pure HTML/ES6 and connects to the API endpoint. The UI is delivered as static files from the /static directory of the API server.

- API

  The API is a Golang web application that connects to GKE standard clusters and scrapes workload information. The API also exposes endpoints to calculate binpacking recommendations.

## Prerequisite

- Binpacker can be executed on local environments (laptops, etc.) or Cloud Shell.
  - On local environments, docker must be installed.
- GKE standard clusters must be reachable from the local environment.
- Your Google account must have the following specific IAM permissions for Google Cloud projects to be discovered: (If you are an owner or an editor of the project, you are good to go).
  - compute.instanceGroups.get
  - compute.machineTypes.list
  - container.clusters.get
  - container.clusters.getCredentials
  - container.clusters.list
  - container.pods.list
  - container.replicaSets.list

## Binpacking calculation

BinPacking Recommendation on gTools is the theoretical minima calculated using the [First-fit-decreasing algorithm](https://en.wikipedia.org/wiki/First-fit-decreasing_bin_packing). It is an estimate and may differ from how Kubernetes Scheduler might choose to pack the pod. The calculation does not take into account the following factors:

- Persistent volumes
- Taint and Toleration
- Hardwares (GPU, TPU)

Please test your workloads thoroughly with the new config before deploying in production.

## APIs and static contents

- GET /

  Web UI of the tool

- POST /api/metrics

  Scrape GKE standard clusters, node pools and pods using google cloud SDK, kube API and return metrics

- POST /api/binpacker

  Calculate and provide binpacking recommendation includes the spec per node(vCPUs, Memory) and the number of nodes

## Folder structure

- api/
  - cmd/binpacker/
    - Entry point
  - pkg/
    - domain/
      - Domain models
    - infrastructure/repository/
      - Actual implementations
    - interface/handler/
      - API handle functions called in entrypoint
    - usecase/
      - Usecases called by handlers
- proto/
  - Proto files for APIs/UI
- ui/src
  - UI related files written in React and TypeScript

## Set up

The tool is designed to use the user's credentials to connect to Google Cloud and GKE clusters. The way to provide the credentials varies depending on the environment.

- Cloud Shell (Recommended)

  The credential is automatically provided when running the tool. You do not need to explicitly prepare it.

- Local environments (Laptop, etc.)

  You need to prepare a credential and provide it as Application Default Credentials (ADC).

### On Cloud Shell

1. Make sure you are in the root directory of tools(sa-tools):

   If your current folder is as same as this `README.md`, execute a following command and move to the root directory of gTools:

   ```bash
   cd ../.. && pwd
   ```

   Make sure you are in the directory called `sa-tools`.

1. Build the application from Dockerfile:

   ```bash
   docker build -f ./gke-optimization/binpacker/Binpacker.dockerfile -t binpacker .
   ```

1. Run the application:

   ```bash
   docker run -d -p 8080:8080 --name binpacker binpacker
   ```

1. Access to the application:

   Click `Web Preview` button and click `Preview on port 8080`. You will see the UI of binpacker.

1. Discover workloads from a specific project:

   On the UI, enter the `Project ID` and click `DISCOVER` button. You will be asked to authorize Cloud Shell on the Cloud Shell tab. Click `AUTHORIZE` to proceed.

1. Stop the application:

   ```bash
   docker stop binpacker
   ```

1. Delete the container images:

   ```bash
   docker rmi binpacker --force
   ```

### On Laptop

1. Make sure you are in the root directory of tools(sa-tools):

   If your current folder is as same as this `README.md`, execute a following command and move to the root directory of gTools:

   ```bash
   cd ../.. && pwd
   ```

   Make sure you are in the directory called `sa-tools`.

1. Provide your user credentials to ADC:

   ```bash
   gcloud auth application-default login
   ```

   Make a note of the path of the application default credentials. We will use the path in a later step.

1. Build the application from Dockerfile:

   ```bash
   docker build -f ./gke-optimization/binpacker/Binpacker.dockerfile -t binpacker .
   ```

1. Run the application with the ADC:

   Replace `PATH_OF_ADC_FILE` to what you noted in the previous step.

   ```bash
   docker run -d -p 8080:8080 \
     -v PATH_OF_ADC_FILE:/.config/gcloud/application_default_credentials.json \
     --name binpacker \
     binpacker
   ```

1. Access to the application:

   Open `http://localhost:8080/` with your browser.

1. Discover workloads from a specific project:

   On the UI, input `Project ID` and click `DISCOVER` button.

1. Stop the application:

   ```bash
   docker stop binpacker
   ```

1. Delete the container images:

   ```bash
   docker rmi binpacker --force
   ```

## Troubleshooting

### Errors during discovering workloads

- Failed to discover clusters, node pools and pods
  failed to list machine type: googleapi: Error 404: The resource 'projects/xxxxxxxx' was not found
  - Confirm the Project ID is correct and it exists.
- Failed to discover clusters, node pools and pods
  failed to fetch pods from xxxxx(yyyyy): Get "https://xxx.xxx.xxx.xxx/api/v1/pods": dial tcp xxx.xxx.xxx.xxx:443: i/o timeout
  - One of the standard clusters are not reachable from your environment. Confirm master authorized networks configuration if one of GKE clusters is private.
