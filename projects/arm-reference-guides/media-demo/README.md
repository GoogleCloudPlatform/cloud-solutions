# Event-based media streaming and transcoding on Axion

This demo demonstrates the end-to-end workflow of:

1.  Uploading media in a Cloud Storage bucket.
1.  Triggering, using Cloud Pub/Sub, an automatic transcoding job running on
    Google Kubernetes Engine (GKE) with Axion nodes.
1.  Storing the transcoded output in a Cloud Storage bucket.

## Deploy the demo

To deploy the demo on Google Cloud, you do the following:

1.  Open [Cloud Shell](https://cloud.google.com/shell).

    To deploy this reference implementation, you need Terraform >= 1.8.0. For
    more information about installing Terraform, see
    [Install Terraform](https://developer.hashicorp.com/terraform/install).

1.  Clone the repository and set the repository:

    ```bash
    git clone https://github.com/GoogleCloudPlatform/cloud-solutions && \
    cd cloud-solutions
    ```

1.  Configure your Google Cloud project ID in `platform.auto.tfvars`:

    ```hcl
    platform_default_project_id = "YOUR_PROJECT_ID"
    ```

1.  Run the following command:

    ```bash
    projects/arm-reference-guides/media-demo/terraform/deploy.sh
    ```

## Destroy the demo

To destroy the demo, you do the following:

1.  Open Cloud Shell.

1.  Change the working directory to the directory where you cloned this
    repository:

    ```bash
    cd cloud-solutions
    ```

1.  Run the following command:

    ```bash
    projects/arm-reference-guides/media-demo/terraform/teardown.sh
    ```
