# Binpacker

Provides 2 key capabilities:

-   Scrape running GKE standard clusters, node pools and pods in a Google
    Project
-   Provide binpacking recommendations(custom machine size, number of nodes) for
    selected workloads

## Prerequisite

-   Binpacker is assumed to be executed on local environments(Laptop, Cloud
    Shell)
-   At least one GKE standard cluster is running on a project

## APIs and static contents

-   POST /api/metrics
    -   Scrape GKE standard clusters, node pools and pods using google cloud
        SDK, kube API and return metrics
-   POST /api/binpacker
    -   Calculate and provide binpacking recommendation includes the spec per
        node(vCPUs, Memory) and the number of nodes

## Folder structure

```text
- cmd/binpacker/
  Entry point
- pkg/
  - domain/
    Domain models
  - infrastructure/repository/
    Actual implementations
  - interface/handler/
    API handle functions called in entrypoint
  - usecase/
    Usecases called by handlers
- proto/
  proto files for APIs
```

## Setup procedure

### Running on local machine

1.  Set account who has access to target Google Project

    ```bash
    gcloud config set account [ACCOUNT]
    ```

    Replace `ACCOUNT` with your actual one

1.  Acquire new user credentials to use for Application Default Credentials

    ```bash
    gcloud auth application-default login
    ```

1.  Build binpacker

    ```bash
    make build
    ```

1.  Run binpacker

    ```bash
    make run PROJECT_ID=[PROJECT_ID]
    ```

    Replace `PROJECT_ID` with your actual one

1.  Access metrics API from another terminal

    ```bash
    curl -X POST -H "Content-Type: application/json" -d '{"projectId" : "PROJECT_ID"}' http://localhost:8080/api/metrics
    ```

    Replace `PROJECT_ID` with your actual one
