# Demo

To run a demo deployment of the autoscaler for Trino workloads, you need to
initialize and execute a Terraform script. This script will create the necessary
infrastructure and configuration for the autoscaler to work.

Once the autoscaler is deployed, you can run a Trino query on the BigQuery
public dataset. The autoscaler will monitor the cluster CPU utilization and
scale the cluster up or down as needed to ensure that the query can run
efficiently. You can monitor the job through the autoscaler job dashboard. By
monitoring the cluster CPU utilization and the autoscaler actions, you can
verify that the autoscaler is working correctly and that the cluster is being
scaled appropriately.

A demo deployment script is in the `/demo` folder.

## Setting up your environment

1.  Enable APIs for Compute Engine, Cloud Storage, Dataproc, Bigquery,
    Monitoring and Cloud Build services:

    ```bash
    gcloud services enable \
    compute.googleapis.com \
    bigquery.googleapis.com \
    bigqueryconnection.googleapis.com \
    cloudbuild.googleapis.com \
    dataproc.googleapis.com \
    storage.googleapis.com \
    monitoring.googleapis.com
    ```

1.  In Cloud Shell, set the
    [Cloud Region](https://cloud.google.com/compute/docs/regions-zones#available)
    that you want to create your Dataproc resources in:

    ```bash
    PROJECT_ID="<PROJECT_ID>"
    REGION="<YOUR_REGION>"
    ZONE="<YOUR_ZONE>"
    CLUSTER_NAME="<dataproc_cluster_name>"
    ```

## Run Demo

Do the modifications based on your requirements like using private VPC and
firewall rules etc.

Run below commands to execute terraform :

```bash
cd demo && \
terraform init && \
terraform apply \
-var project_id="${PROJECT_ID}" \
-var region="${REGION}" \
-var zone="${ZONE}" \
-var  dataproc_staging_gcs_bucket_name=<bucket-name> \
-var dataproc_cluster_name="${CLUSTER_NAME}" \
-var autoscaler_folder=<folder-name>
```

You can view the autoscaler job monitoring dashboard url printed at the end of
terraform execution.

Example as below:

```text
Apply complete! Resources: xx added, 0 changed, 0 destroyed.

Outputs:

dashboard_url = https://console.cloud.google.com/monitoring/dashboards/builder/<dashboard-id>;duration=PT30M?project=<your-project-id>

trino-master-ssh-command = gcloud compute ssh --zone "<zone-id>" "<cluster-id>" --project "<project-id>"
```

### Run a test Trino job

Establish an SSH connection to Dataproc master node, that runs the Trino
coordinator:

```bash
gcloud compute ssh \
--project "${PROJECT_ID}" \
--zone "${ZONE}" \
"${CLUSTER_NAME}-m' \
-- -L 8060:localhost:8060
```

Download Trino CLI to work on local machine :
<https://trino.io/docs/current/client/cli.html>

Use the below command to run the Trino command pointing to the public bigquery
dataset

```bash
trino \
--catalog=bigquery_public_data \
--schema=worldpop \
--server=localhost:8060
```

Execute below Trino query to run a job:

```sql
SELECT
    country_name,
    SUM(population)
FROM population_grid_1km
GROUP BY 1
ORDER BY 2 DESC;
```

You can monitor the Trino job on Trino UI as well.

## (Optional) Manual demo deployment

1.  Set Variables

    ```bash
    GCS_BUCKET_NAME="gs://trino-staging"
    JAR_LOCATION_FOLDER="gs://${GCS_BUCKET_NAME}/trino_scaler"
    INIT_SCRIPT_LOCATION="gs://${GCS_BUCKET_NAME}/trino_scaler/init-script.sh"
    ```

1.  Build using Cloud Build

    ```bash
    gcloud builds submit . \
    --config=./cloudbuild.yaml \
    --machine-type=e2-highcpu-8 \
    --substitutions=_JAR_LOCATION="${JAR_LOCATION_FOLDER}"
    ```

1.  Make a copy of the configuration file `demo/sample_config.textproto`, edit
    its values and rename it as myconfig.textproto

1.  Copy the config to GCS

    ```bash
    gsutil cp \
    demo/myconfig.textproto \
    "gs://${GCS_BUCKET_NAME}/trino_scaler/config.textproto"
    ```

1.  Update Init Script: Use your preferred text editor edit following lines in
    the `demo/trino-autoscaler-init.sh` file:

    ```bash
    CONFIG_JAR_FILE_GCS_URI="gs://${GCS_BUCKET_NAME}/trino_scaler/trino-autoscaler-on-dataproc-all.jar";
    CONFIG_PROTO_FILE_GCS_URI="gs://${GCS_BUCKET_NAME}/trino_scaler/config.textproto";
    ```

1.  Copy the dataproc init script to GCS

    ```bash
    gsutil cp \
    demo/trino-autoscaler-init.sh \
    "gs://${GCS_BUCKET_NAME}/trino_scaler/trino-autoscaler-init.sh"
    ```

1.  Use the Trino autoscaler init script as one of the Dataproc init scripts.

## Cleaning up

**Caution**: Deleting a project has the following effects:

-   **Everything in the project is deleted.** If you used an existing project
    for this tutorial, when you delete it, you also delete any other work
    you\'ve done in the project.

-   **Custom project IDs are lost.** When you created this project, you might
    have created a custom project ID that you want to use in the future. To
    preserve the URLs that use the project ID, such as an **appspot.com** URL,
    delete selected resources inside the project instead of deleting the whole
    project.

If you plan to explore multiple tutorials and quickstarts, reusing projects can
help you avoid exceeding project quota limits.

To avoid incurring charges to your Google Cloud account for the resources used
in this tutorial, you can delete the project:

1.  In the Cloud Console, go to the
    [**Manage resources** page](https://console.cloud.google.com/iam-admin/projects).

2.  In the project list, select the project that you want to delete and then
    click **Delete**.

3.  In the dialog, type the project ID and then click **Shut down** to delete
    the project.
