# Download model weights and create a (GCE) disk image

## Create a Persistent Volume Claim for holding the model weights

Apply the file `pvc-for-downloader.yaml`:

```bash
kubectl apply -f pvc-for-downloader.yaml
```

You can adjust the file according to your needs, e.g. increase the storage size.

## Run the kubernetes job

Adjust the file `model-downloader-job.yaml`, set the gcs bucket name, you can
use this command:

```bash
sed -i 's/_MODEL_NAME_/<you_model_name>/; s/_BUCKET_NAME_/<you_bucket_name>' model-downloader-job.yaml
```

Create the job:

```bash
kubectl create -f model-downloader-job.yaml
```

Wait until the job finishes.

## Create the disk image

Run these commands, replace _YOUR_DISK_IMAGE_NAME_ accordingly:

```bash
PV_NAME="$(kubectl get pvc/block-pvc -o jsonpath='{.spec.volumeName}')"
DISK_REF="$(kubectl get pv "$PV_NAME"  -o jsonpath='{.spec.csi.volumeHandle}')"
gcloud compute images create _YOUR_DISK_IMAGE_NAME_ --source-disk="$DISK_REF"
```
