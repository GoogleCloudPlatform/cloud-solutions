# serve a LLM application using vLLM on GKE

## Bake a disk image for secondary boot disk

Follow this [doc](https://cloud.google.com/kubernetes-engine/docs/how-to/data-container-image-preloading#:~:text=GKE%20provisions%20secondary%20boot%20disks,images%20from%20secondary%20boot%20disks.)
to create a disk image for caching the container image `vllm/vllm-openai:v0.5.3`.

## Create a node pool using the secondary boot disk

Use the following command, replace `_DISK_IMAGE_FOR_CONTAINER_IMAGE_CACHE_`
with the disk image for secondary boot disk.

```bash
gcloud container node-pools create _YOUR_NODE_POOL_ --cluster=_YOUR_GKE_CLUSTER_ \
  --node-locations=_YOUR_ZONE_ \
  --machine-type=_MACHINE_TYPE_ \
  --max-nodes=5 \
  --min-nodes=1 \
  --accelerator=type=_GPU_TYPE_,count=_NUM_OF_GPUS_,gpu-driver-version=latest \
  --disk-type=pd-ssd \
  --location=_CLUSTER_LOCATION \
  --enable-autoscaling \
  --enable-image-streaming \
  --secondary-boot-disk=disk-image=projects/$PROJECT_ID/global/images/_DISK_IMAGE_FOR_CONTAINER_IMAGE_CACHE_,mode=CONTAINER_IMAGE_CACHE
```

## Bake a disk image for model weights

Follow the guides in `download-model` to create a disk image containing the
model weights.

## Create a pv and a pvc for use by the vllm application

-   Create a persistent disk from the baked disk image with model weigts.
    -   Disk type should be pd-ssd
    -   Disk size should be larger than 1TB to have reasonable throughput
-   Create a PersistentVolume and a PersistentVolumeClaim from the disk just
    created.
    -   You can use the `example-pd-pv.yaml` as an example.

## Deploy the `vllm-openai-use-pd.yaml`

You can use the `vllm-openai-use-pd.yaml` as an example, use the following
command to replace the place holders:

```bash
sed -i 's/_MODEL_NAME_/<your-model-name>';
s/_YOUR_MODEL_PVC_/<your-model-pvc/;
s/_YOUR_ZONE_/<your-zone>/;
s/_YOUR_NODE_POOL_/<your-node-pool/' vllm-openai-use-pd.yaml
```

## Configure HPA

### vLLM Pod Monitoring for Prometheus

Deploy pod monitoring, use `pod-monitoring.yaml`

```bash
kubectl apply -f pod-monitoring.yaml
```

### Custom metrics HPA

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

### Deploy the HPA resource

Use the `hpa-vllm-openai.yaml` to deploy the HPA resource:

```bash
kubectl apply -f hpa-vllm-openai.yaml
```
