# Provision and configure a Google Kubernetes Engine platform for NVIDIA Omniverse applications

This document describes how to provision and configure a
[Google Kubernetes Engine (GKE)](https://cloud.google.com/kubernetes-engine/docs/concepts/kubernetes-engine-overview)
cluster to deploy NVIDIA Omniverse applications on Google Cloud.

The provisioning and configuration process follows GKE security and operational
best practices.

## Provision and configure a GKE cluster

To provision and configure a GKE cluster that implements best practices, you
deploy an instance of the
[Core GKE Accelerated Platform](https://github.com/GoogleCloudPlatform/accelerated-platforms/blob/main/platforms/gke/base/core/README.md).

To deploy an instance of the Core GKE Accelerated Platform, you do the
following:

1.  Clone the Accelerated Platforms repository and set the repository directory
    environment variable:

    ```bash
    git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
    cd accelerated-platforms && \
    export ACP_REPO_DIR="$(pwd)"
    ```

1.  Configure the Core GKE Accelerated Platform by adding setting the following
    Terraform configuration variables in
    `platforms/gke/base/_shared_config/initialize.auto.tfvars`:

    ```hcl
    # Disable initializing node pools without GPUs
    initialize_container_node_pools_cpu             = false
    # Disable initializing node pools with GPUs that don't offer NVIDIA RTX cores
    initialize_container_node_pools_gpu_without_rtx = false
    # Disable initializing node pools with Google TPUs because they are not needed for this workload
    initialize_container_node_pools_tpu             = false
    ```

1.  Deploy an instance of the Core GKE Accelerated Platform:

    ```bash
    CORE_TERRASERVICES_APPLY="networking container_cluster container_node_pool workloads/cluster_credentials" "${ACP_REPO_DIR}/platforms/gke/base/core/deploy.sh"
    ```

Note: the instructions in this section are a specialization of the
[Core GKE Accelerated Platform deployment instructions](https://github.com/GoogleCloudPlatform/accelerated-platforms/blob/main/platforms/gke/base/core/README.md)
that are tailored to this use case.

## Destroy the GKE cluster

To destroy the instance of the Core GKE Accelerated Platform you created, you do
the following:

1.  Destroy the instance of the Core GKE Accelerated Platform:

    ```bash
    CORE_TERRASERVICES_DESTROY="workloads/cluster_credentials container_node_pool container_cluster networking" "${ACP_REPO_DIR}/platforms/gke/base/core/teardown.sh"
    ```

## What's next

- Develop NVIDIA RTX applications on
  [NVIDIA RTX Virtual Workstations on Google Cloud](../README.md#nvidia-rtx-virtual-workstations).
- [Deploy a NVIDIA Omniverse Kit Streaming application on GKE](../kit-app-streaming/README.md).
