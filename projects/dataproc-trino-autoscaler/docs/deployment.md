# Manual Deployment

This document describes a method to run a demo deployment of the tool.

## Objectives

- Deploy autoscaler application
- Run a Demo job for autoscaling Dataproc workers for the Trino workloads
- Verify autoscaling of worker nodes in the monitoring and Trino dashboard

## Costs

This tutorial uses billable components of Google Cloud, including the following:

- [Dataproc](https://cloud.google.com/dataproc/pricing)
- [Cloud Build](https://cloud.google.com/build/pricing)
- [Bigquery](https://cloud.google.com/bigquery/pricing)
- [Cloud Storage](https://cloud.google.com/storage/pricing)
- [Cloud Monitoring](https://cloud.google.com/stackdriver/pricing)

Use the [pricing calculator](https://cloud.google.com/products/calculator) to
generate a cost estimate based on your projected usage.

## Before you begin

For this tutorial, you need a Google Cloud
[project](https://cloud.google.com/resource-manager/docs/cloud-platform-resource-hierarchy#projects).
To make cleanup easiest at the end of the tutorial, we recommend that you create
a new project for this tutorial.

1.  [Create a Google Cloud project](https://console.cloud.google.com/projectselector2/home/dashboard)
1.  Make sure that
    [billing is enabled](https://support.google.com/cloud/answer/6293499#enable-billing)
    for your Google Cloud project
1.  [Open Cloud Shell](https://console.cloud.google.com/?cloudshell=true)

    > At the bottom of the Cloud Console, a
    > [Cloud Shell](https://cloud.google.com/shell/docs/features) session opens
    > and displays a command-line prompt. Cloud Shell is a shell environment
    > with the Cloud SDK already installed, including the
    > [gcloud](https://cloud.google.com/sdk/gcloud/) command-line tool, and with
    > values already set for your current project. It can take a few seconds for
    > the session to initialize.

1.  In Cloud Shell, clone the source repository and go to the directory for this
    tutorial:

    ```bash
    git clone https://github.com/GoogleCloudPlatform/dataproc-trino-autoscaler.git\
    cd dataproc-trino-autoscaler
    ```

### Setting up your environment

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
    SERVICE_ACCOUNT="<SERVICE_ACCOUNT>"
    ```

1.  Make sure that the Service Account used by Dataproc cluster, should have the
    following roles:

    ```bash
    gcloud projects add-iam-policy-binding ${PROJECT_ID} --member=serviceAccount:${SERVICE_ACCOUNT} --role=roles/compute.admin && \
    gcloud projects add-iam-policy-binding ${PROJECT_ID} --member=serviceAccount:${SERVICE_ACCOUNT} --role=roles/bigquery.dataViewer && \
    gcloud projects add-iam-policy-binding ${PROJECT_ID} --member=serviceAccount:${SERVICE_ACCOUNT} --role=roles/bigquery.user && \
    gcloud projects add-iam-policy-binding ${PROJECT_ID} --member=serviceAccount:${SERVICE_ACCOUNT} --role=roles/dataproc.editor && \
    gcloud projects add-iam-policy-binding ${PROJECT_ID} --member=serviceAccount:${SERVICE_ACCOUNT} --role=roles/dataproc.worker && \
    gcloud projects add-iam-policy-binding ${PROJECT_ID} --member=serviceAccount:${SERVICE_ACCOUNT} --role=roles/monitoring.viewer && \
    gcloud projects add-iam-policy-binding ${PROJECT_ID} --member=serviceAccount:${SERVICE_ACCOUNT} --role=roles/storage.objectViewer
    ```

## How to use

The solution is packaged as a JAR file that needs to be executed on the Trino
master node as a daemon process.

1.  Build the JAR file

    ```bash
    ./gradlew clean build shadowJar
    ```

1.  Write your configuration by making a copy of the
    demo/sample_config.textproto file and update it.

1.  Copy the JAR and config file to the master node of the Dataproc cluster
    running Trino using gcloud compute scp command.

    ```bash
    gcloud compute scp <JAR_FILE_PATH> <CONFIG_FILE_PATH> <MASTER_NODE_NAME>:~/.
    ```

    | Variable           | Description                                         |
    | ------------------ | --------------------------------------------------- |
    | `JAR_FILE_PATH`    | full path to the JAR file on your local machine.    |
    | `CONFIG_FILE_PATH` | full path to the config file on your local machine. |
    | `MASTER_NODE_NAME` | name of the master node in the Dataproc cluster.    |

1.  Invoke the autoscaler application using:

    ```bash
    java -jar <path/to/jarFile> <path/to/configfile> [optional:trino-worker-port:-8060]
    ```

    It is recommended that the autoscaler be installed as a systemd daemon.

### Install autoscaler daemon

To install autoscaler as a systemd daemon follow the steps:

1.  Create the variable `TRINO_AUTO_SCALER_SERVICE_FOLDER` if it does not
    already exist.
1.  Create the variable and directory `TRINO_AUTOSCALE_FOLDER` if it does not
    already exist.
1.  Copy the autoscaler jar to `TRINO_AUTOSCALE_FOLDER`.
1.  Create a log file called trino_autoscaler.log in the directory
    `TRINO_AUTOSCALE_FOLDER`.
1.  Create a systemd service file called trino_autoscaler.service in the
    directory `TRINO_AUTO_SCALER_SERVICE_FOLDER`.
1.  The service file contains the following configuration:

    - The description of the service: `Trino Autoscaler Service`
    - The dependencies of the service: `trino.service`
    - The command to start the service:
      `#!bash java -jar   ${TRINO_AUTOSCALE_FOLDER}/trino_autoscaler.jar   ${TRINO_AUTOSCALE_FOLDER/config.textproto`
    - The command to stop the service: `#!bash /bin/kill -15 \${MAINPID}` The
      restart policy for the service: `always`. The standard output and standard
      error logs for the service: `/var/log/trino_autoscaler.log`. Changes the
      permissions of the service file `trino_autoscaler.service` to allow read,
      write, and execute permissions for all users.
    - The code `#!bash if [[ "{ROLE}" == 'Master' ]];` then checks the value of
      the environment variable ROLE. If the value of the variable is Master,
      then the `#!bash setup_trino_autoscaler()` function is executed. This
      ensures that the Trino autoscaler is only set up on the master node.
    - The code systemctl daemon-reload reloads the systemd daemon configuration.
      This ensures that the systemd daemon is aware of the new service file
      trino_autoscaler.service.
    - When you are using a port other than 8060 for Trino, add the port number
      with a space after `config.textproto` on the `ExecStart` command.

    ```bash
    TRINO_AUTO_SCALER_SERVICE_FOLDER="/usr/lib/systemd/system/"
    TRINO_AUTO_SCALER_SERVICE="/usr/lib/systemd/system/trino_autoscaler.service"
    TRINO_AUTOSCALE_FOLDER="/opt/trino_autoscaler"
    function setup_trino_autoscaler {

    cat <<EOF >"${TRINO_AUTO_SCALER_SERVICE}"

    [Unit]

    Description=Trino autoscaler Service
    After=trino.service

    [Service]

    Type=simple
    ExecStart=java -jar ${TRINO_AUTOSCALE_FOLDER}/trino_autoscaler.jar ${TRINO_AUTOSCALE_FOLDER}/config.textproto
    ExecStop=/bin/kill -15 \$MAINPID
    Restart=always
    StandardOutput=append:/var/log/trino_autoscaler.log
    StandardError=append:/var/log/trino_autoscaler.log

    [Install]

    WantedBy=multi-user.target
    EOF
    chmod a+rx ${TRINO_AUTO_SCALER_SERVICE}
    }

    if [[ "${ROLE}" == 'Master' ]]; then
    # Run only on Master
    setup_trino_autoscaler
    systemctl daemon-reload
    systemctl enable trino_autoscaler
    systemctl start trino_autoscaler
    fi
    ```
