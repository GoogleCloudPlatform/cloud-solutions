# Speedup vLLM application starting

To spin up a pod running an LLM related application, the start-up time consists
of several portions:

-   The container initialization time
-   Application startup time.

The container initialization time is mostly the container image pull time,
while for a typical python LLM application using vLLM, the application startup
time is mostly the time spent loading LLM model weights.

## General discussion

### Accelerate the container image pull

With [secondary boot disk](https://cloud.google.com/kubernetes-engine/docs/how-to/data-container-image-preloading#:~:text=GKE%20provisions%20secondary%20boot%20disks,images%20from%20secondary%20boot%20disks.)
, we can cache container images in an additional disk attached to the GKE nodes.
This way, during the start-up of the pod, the downloading image step can be
accelerated.

### Accelerate the model loading

There are several ways to accelerate the model weights loading:

-   Loading weights from GCSFuse and
-   Loading weights from Persistent Disk
-   Loading weights from NFS backed by FileStore

#### Compare the model weight loading options

-   Manageability
    -   Convenience of use
        -   GCSFuse: Add volume definition to workload manifest, some extra
            parameters can be added in the same manifest
        -   Persistent Volume: Add volume definition to workload manifest,
            but `read_ahead_kb` should be added in the PV's manifest
        -   NFS Volume: Add volume definition to workload manifest, to tune
            `read_ahead_kb`, a privileged initContainer is needed
    -   Model update
        -   GCSFuse: just copy new model weights to GCS bucket
        -   Persistent Volume: an extra workflow is needed: bake an image
            \-\> create disks from image \-\> create PVs from disk \-\> discard
            old disks
        -   NFS Volume: just copy new model weights to NFS
    -   Other limitations
        -   NFS:  A privileged sidecar is needed to tune the performance
-   Performance
    -   Warmup time
        -   GCSFuse: Cache in the node's host disk needs warmup. Once the cache
            is filled, pods in the same node can benefit from it.
        -   Persistent Volume and NFS Volume: no warmup needed
    -   Maximum read throughput
        -   GCSFuse: Maximum read throughput depends on the node's host disk,
            larger host disk generates better performance, maximum at 2TB disk
            size.
        -   Persistent Volume: Maximum throughput depends on the volume size,
            maximum at 2TB disk size
        -   NFS Volume: Maximum throughput depends on volume size. 2.5TB volume
            as the same throughput as using PD
-   Price
    -   Over-provisioning requirements
        -   GCSFuse:
            -   Node disk needs to be large to achieve good performance. Also,
                since cache fill takes time, the first pod on new nodes still
                starts slow. Node over-provisioning is needed to mitigate this.
            -   Extra memory needed by the GCSFuse sidecar
        -   Persistent Volume
            -   Volume disk needs to be large to have high throughput. But
                since PVs can be mounted simultaneously by multiple pods, the
                overheads are relatively small
            -   Persistent Disk has attachment limit: one PD-SSD disk can only
                attach to 100 nodes
        -   NFS: Volume needs to be 2.5 to achieve the performance. But the
            space can be used for other purposes.
    -   Price Summary
        -   GCSFuse: \$\$
        -   Persistent Volume: \$
        -   NFS: \$\$\$

In this document, we choose persistent disk for model weights loading.

## Step by step guide

### Use secondary boot disk to accelerate container image loading

To use secondary boot disk, follow these steps

#### Bake a disk image with the container images

We can use this GKE provided tool called [gke-disk-image-builder](https://github.com/GoogleCloudPlatform/ai-on-gke/tree/main/tools/gke-disk-image-builder)
to create a virtual machine (VM) and pull the container images on a disk and
then create a disk image from that disk. In this case, we use
`vllm/vllm-openai:v0.5.3`.

To create a disk image with preloaded container images, do the following steps:

1.  Create a Cloud Storage bucket to store the execution logs of
    gke-disk-image-builder.
1.  Create a disk image with gke-disk-image-builder.

    ```bash

    go run ./cli \
        --project-name=PROJECT_ID \
        --image-name=DISK_IMAGE_NAME \
        --zone=LOCATION \
        --gcs-path=gs://LOG_BUCKET_NAME \
        --disk-size-gb=100 \
        --container-image=docker.io/vllm/vllm-openai:v0.5.3 \
        --network=NETWORK_NAME
    ```

    Replace the following:

    -   PROJECT_ID: the name of your Google Cloud project.
    -   DISK_IMAGE_NAME: the name of the image of the disk. For example,
        vllm-openai-image.
    -   LOCATION: the cluster location.
    -   LOG_BUCKET_NAME: the name of the Cloud Storage bucket to store the
        execution logs.

When you create a disk image with `gke-disk-image-builder`, Google Cloud creates
multiple resources to complete the process (for example, a VM instance, a
temporary disk, and a persistent disk). After its execution, this image builder
will clean up all the resources but the disk image you want.

#### Create a node pool with secondary boot disk

To use the secondary boot disk, you will need a new node pool. You can use the
following command to create a node pool with secondary boot disk as container
image cache.

```bash
gcloud container node-pools create NODE_POOL_NAME --cluster=GKE_CLUSTER \
  --node-locations=NODE_ZONE \
  --machine-type=MACHINE_TYPE \
  --max-nodes=5 \
  --min-nodes=1 \
  --accelerator=type=GPU_TYPE,count=NUM_OF_GPUS,gpu-driver-version=latest \
  --disk-type=pd-ssd \
  --location=LOCATION \
  --enable-autoscaling \
  --enable-image-streaming \
  --secondary-boot-disk=disk-image=projects/PROJECT_ID/global/images/DISK_IMAGE_NAME,mode=CONTAINER_IMAGE_CACHE
```

Replace the following:

-   PROJECT_ID: the name of your Google Cloud project.
-   GKE_CLUSTER: the gke cluster name you are going to create a node pool
-   NODE_POOL_NAME: the name of the node pool
-   DISK_IMAGE_NAME: the name of the image of the disk. In this case,
  vllm-openai-image.
-   LOCATION: the cluster location.
-   NODE_ZONES: the nodes in the pool will be in this zone(s).
-   MACHINE_TYPE: the machine type of the nodes in the pool
-   GPU_TYPE and NUM_OF_GPUS: attache this number of this type of GPUs to the
  nodes in the pool.

### Use Persistent Disk to accelerate model weight loading

The major limitation of a Persistent Disk is that in GKE, a Persistend Disk can
not be mount as readwrite on multiple nodes. So our strategy will come baking a
disk image with model weights and then create Persistent Disks for readonly use.

#### Bake a disk image for model weights

To bake the model weights into a disk image, you can do the following

-   Create a persistent disk for downloading the model weights, you can achieve
  this by creating a PVC with StorageClass standard
-   Download model weights to the disk. You can use a kubernetes job to do this,
  attach the PVC to the job
-   Find the disk of that PVC and create a image from the disk

You can find example in the `download-model` directory, to use that, you need
edit the file `download-model/model-downloader-job.yaml` to replace these:

-   _YOUR_BUCKET_NAME_ The GCS bucket storing the model
-   _YOUR_MODEL_NAME_ The model name
-   _YOUR_MODEL_DIR_ The directory name to the model.

The Job is going to copy everything in
`gs://_YOUR_BUCKET_NAME_/_YOUR_MODEL_DIR_/_YOUR_MODEL_NAME_`
to `/_YOUR_MODEL_DIR_/_YOUR_MODEL_NAME_` in the created disk  image.

#### Create a pv and a pvc for use by the vllm application

After baking the disk image of model weights, you can creat

-   Create a persistent disk from the baked disk image with model weights.
    -   Disk type should be pd-ssd
    -   Disk size should be larger than 1TB to have reasonable throughput
-   Create a PersistentVolume and a PersistentVolumeClaim from the disk just
    created.
    -   You can use the `example-pd-pv.yaml` in the `serving` directory as an
    example.

Pay attention to the `accessModes`, it should be `ReadOnlyMany`, and in the
`mountOptions`, a `read_ahead_kb=4096` should be specified, this can make model
weights loading faster(see section Performance evaluations).

### Deploy the vllm application and enable HPA

#### Deploy the vllm application

You can use the  `vllm-openai-use-pd.yaml` in the `serving` directory to deploy
a vllm application. Change the following:

-   `_YOUR_MODEL_DIR_` The directory name to the model
-   `_YOUR_MODEL_NAME_` The model name
-   `_YOUR_MODEL_PVC_` The persistent volume claim you created with model
    weights
-   `_YOUR_ZONE_` The zone you want to run your application, must be the same as
    the zone you created the persistent volume of model weights
-   `_YOUR_NODE_POOL_` The node pool you want to schedule the pods in. Must be
    the node pool you created with secondary boot disk

#### vLLM Pod Monitoring for Prometheus

To deploy pod monitoring, use `pod-monitoring.yaml` in the `serving` directory

```bash
kubectl apply -f pod-monitoring.yaml
```

#### Custom metrics HPA

Install the adapter in your cluster:

```bash
kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/k8s-stackdriver/master/custom-metrics-stackdriver-adapter/deploy/production/adapter_new_resource_model.yaml
```

Setup necessary privileges:

```bash
PROJECT_ID=<your_project_id>
PROJECT_NUMBER=<your_project_number>

gcloud projects add-iam-policy-binding projects/"$PROJECT_ID" \
  --role roles/monitoring.viewer \
  --member=principal://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/"$PROJECT_ID".svc.id.goog/subject/ns/custom-metrics/sa/custom-metrics-stackdriver-adapter
```

Change the following:

-   `<your_project_id>` Your GCP project id
-   `<your_project_number>` Your numerical GCP project number

#### Deploy the HPA resource

Use the `hpa-vllm-openai.yaml`  in the `serving` directory to deploy the HPA
resource:

```bash
kubectl apply -f hpa-vllm-openai.yaml
```

## Performance evaluations

The following table is about time (in seconds) of loading a Gemma 7B model,
the model's data file size is around 16GB:

| Model weight storage             | read_ahead_kb=1024 | read_ahead_kb=128(default) |
|----------------------------------|--------------------|----------------------------|
| GCSFuse, 100GB pd-balanced cache | Not tested         | 137.06888                  |
| GCSFuse $^1$, 1T pd-ssd cache    | 81.59027293795953  | 77.48203204700258          |
| PV, 0.5T, pd-ssd                 | 112.49156787904212 | 114.35550174105447         |
| PV, 1T pd-ssd                    | 38.00010781598394  | 84.12003243801882          |
| PV, 2T pd-ssd                    | 29.2281584230077   | 86.59166808301234          |
| NFS $^{2, 3}$, 2.5T Basic-SSD    | 29.446771587       | 115.49353002902353         |
| NFS, 1T Zonal                    | 52.83657205896452  | 212.9237892589881          |

-   $^1$ GCSFuse without Cache: 165.0438082399778
-   $^2$ read_ahead_kb was set to 16384, for 1024 read_ahead_kb,
    the time was 71.699842115
-   $^3$ Uses Cloud Filestore for NFS

The conclustion is using a pd-ssd with 2TB size will produce best performance.
