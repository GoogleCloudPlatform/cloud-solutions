# Benchmark model loading time

This folder holds tools used to benchmark model loading time.

## Explanation

The program `generate_k8s_jobs.py` can generate kubernetes Job manifest files
which will benchmark model loading time.

The 3 ways of loading models are supported:

-   gcsfuse: load model from attached gcsfuse volume
-   pd-volume: load model from a persistent disk which specified by a persistent
    volume claim.
-   nfs-volume: load model from a nfs volume which specified by a persistent
    volume claim.

The `model-loading-code` holds the script actually running from a kubenetes pod
and prints out the model loading time.

## Usage

### Prepare a kubernetes cluster with GPUs

The cluster should have workloadidentity enabled.

The cluster should have nodepool with GPUs

### Create a kubernetes secret holding the hugging-face access token

### Create a gcs bucket and prepare for use

-   Create a gcs bucket

-   Grant access to the kubernetes serviceaccount

  For example:

```bash
BUCKET_NAME=<your_bucket_name>
PROJECT_NUMBER=<your_gcp_project_number>
PROJECT_ID=<your_gcp_project_id>
KNS=<the_namespace_used>
KSA=<the_service_account>
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET_NAME" \
    --member "principal://iam.googleapis.com/projects/"$PROJECT_NUMBER"/locations/global/workloadIdentityPools/${PROJECT_ID}.svc.id.goog/subject/ns/$KNS/sa/$KSA" \
    --role "roles/storage.objectViewer"
```

-   Give the bucket "uniform bucket level access"

```bash
gcloud storage buckets update "gs://$BUCKET_NAME" --uniform-bucket-level-access
```

-   Upload the model weight files to the bucket, the filepath should be exactly
    the huggingface model id. For example, a huggingface model
    `google/gemma-1.1-7b-it` should be uploaded to the bucket as
    `gs://$BUCKET_NAME/google/gemma-1.1-7b-it`.

### Create Persistent Volumes and a Persistent Volumes Claim for use

-   One PV should be created for each of the zones
-   The PVs should have node affility
-   Download the model weight files to the root of the volume.

The directory `download-model` contains guides about how to use models in a GCS
bucket to create a disk image. Then we can use that disk image to create
volumes.

### Upload the model-loading-code to a ConfigMap

Simply run this:

```bash
kubectl apply -k model-loading-code
```

### Install needed python modules

Run `pip install --require-hashes -r requirements.txt`, this will install the
`yamlpath` python module and brings the `yaml-set` and `yaml-paths` commands.

### Adjust or create job definition overlays

The files `gcsfuse-case.yaml` `nfs-volume-case.yaml` `pd-volume-case.yaml` will
be merged upon `run-vllm-job/vllm-job.yaml` to generate the kubernetes job
manifest files for the test. You need to adjust these files, change things like
`_YOUR_BUCKET_NAME_` to your real values.

And you might also want to change the `MODEL_ID` to the model you are testing.

#### Use yaml-set to do the editing

To find what you need to change in those files, you can run this, use
`gcsfuse-case.yaml` as an example:

```bash
yaml-paths -L -s =~'/(^_|google)/' gcsfuse-case.yaml
```

You will get:

```text
gcsfuse-case.yaml/0: spec.template.spec.containers[0].env[1].value: /data/models/google/gemma-2b-it-chatbot
gcsfuse-case.yaml/0: spec.template.spec.volumes[0].csi.volumeAttributes.bucketName: _YOUR_BUCKET_NAME_
```

Then you know `spec.template.spec.containers[0].env[1].value` is the path about
models and `spec.template.spec.volumes[0].csi.volumeAttributes.bucketName` is
for bucket name.

Then you can run the following command to update the model to for example,
`/data/models/hyperparam/model-job-1`:

```bash
yaml-set -g "spec.template.spec.containers[0].env[1].value" \
    -a "/data/models/hyperparam/model-job-1" gcsfuse-case.yaml
```

### Generate the Job manifest files

```bash
python3 generate_k8s_jobs.py -i run-vllm-job/vllm-job.yaml gcsfuse-case.yaml \
    pd-volume-case.yaml nfs-volume-case.yaml
```

There will be yaml files created with the Job definition, the filenames have
this pattern:
`run-<casename>.yaml`, casename is one of "gcsfuse-case", "pd-volume-case" and
"nfs-volume-case".

### Run the Jobs

```bash
kubectl create -f run-<casename>.yaml|tee /tmp/kube-last-output
LAST_OBJ=$(sed 's/ created$//' /tmp/kube-last-output)
```

And fetch the log

```bash
kubectl logs -f "$LAST_OBJ"
```

The log will look like this:

```text
GCSFUSE             START at 556627.722416964
GCSFUSE   MODULE_IMPORTED at 556633.881632891 delta 6.159215927007608
GCSFUSE         start_run at 556633.882564083 delta 0.0009311919566243887
GCSFUSE     loaded_weight at 556718.512659439 delta 84.6300953560276
GCSFUSE start_inferencing at 556718.512660192 delta 7.529743015766144e-07
GCSFUSE   end_inferencing at 556719.769540476 delta 1.2568802840542048
```

The delta time in line `loaded_weight` is the model loading time.
