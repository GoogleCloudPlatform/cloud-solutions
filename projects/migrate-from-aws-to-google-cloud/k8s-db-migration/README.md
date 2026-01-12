# Migrate Amazon EKS and Amazon RDS to Google Kubernetes Engine (GKE) and Cloud SQL

This guide walks you through replatforming a containerized application from
Amazon EKS and Amazon RDS to Google Kubernetes Engine (GKE) Autopilot and Cloud
SQL. You will perform a "lift-and-shift" migration for the application layer
(redeploying stateless workloads) and a data replication migration for the
database layer using Database Migration Service (DMS). We will begin by
assessing the source environment using the Kubernetes Cluster Discovery Tool to
build a comprehensive inventory of your Kubernetes objects.

## Requirements

To deploy this demo, you need:

- An AWS environment
- A Google Cloud project
- [Google Cloud SDK](https://docs.cloud.google.com/sdk/docs/install)
- [Terraform >= 1.11.1](https://developer.hashicorp.com/terraform/install)
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- [AWS EKSCTL](https://docs.aws.amazon.com/eks/latest/eksctl/installation.html)
- [Gemini CLI](https://geminicli.com/docs/get-started/installation/)
- **Python 3.9+ & pip**: Required to run the
  [k8s discovery tool](https://github.com/GoogleCloudPlatform/professional-services/tree/main/tools/k8s-discovery#1-system-requirements)

> [!CAUTION] **Use a local environment.** Cloud Shell's 5GB disk limit is
> insufficient, and its ephemeral sessions will clear your environment variables
> upon timeout.

### AWS Permissions

Your AWS credentials need permissions to create and manage the following
resources:

- IAM Roles and Policies: For the EKS control plane and nodes.
- VPC and Networking: VPC, subnets, security groups, and route tables.
- EKS Cluster: The Kubernetes control plane and worker nodes.
- RDS Database: A PostgreSQL database instance.
- ECR Repository: To store container images.

For demonstration purposes, the `AdministratorAccess` managed policy is
sufficient. In a production setting, always adhere to the principle of least
privilege.

### Google Cloud Permissions

Ensure your user account or service account has the following IAM roles in your
Google Cloud project:

- Kubernetes Engine Admin (`roles/container.admin`): To create and manage the
  GKE cluster.
- Cloud SQL Admin (`roles/cloudsql.admin`): To provision and manage the Cloud
  SQL instance.
- Compute Network Admin (`roles/compute.networkAdmin`): To manage VPC networks
  and firewall rules.
- Artifact Registry Admin (`roles/artifactregistry.admin`): To create a
  repository for container images.
- Database Migration Admin (`roles/datamigration.admin`): To create and manage
  the DMS job.
- Service Account Admin (`roles/iam.serviceAccountAdmin`): To create service
  accounts for GKE nodes and other resources.
- Project IAM Admin (`roles/resourcemanager.projectIamAdmin`): To grant IAM
  roles to service accounts.

For demonstration purposes, the basic `Owner` role (`roles/owner`) is
sufficient. In a production setting, always adhere to the principle of least
privilege.

## Deploy AWS Infrastructure

Set up your local environment and authenticate with both cloud providers.

1.  Open your terminal and configure AWS CLI:

    ```bash
    aws configure
    ```

    Enter your AWS Access Key ID and Secret Access Key. Set the default region
    name to your desired AWS region (e.g., `us-west-1`). Ensure this matches the
    `aws_region` variable if you plan to modify the default in
    `aws/terraform/variables.tf`.

1.  Clone the repository and set the working directory:

    ```bash
    git clone https://github.com/GoogleCloudPlatform/cloud-solutions && \
    cd cloud-solutions/projects/migrate-from-aws-to-google-cloud/k8s-db-migration
    ```

1.  Set deployment variables and deploy AWS infrastructure:

    ```bash
    export TF_VAR_rds_password="Chiapet22!"
    ./aws/deploy_aws.sh
    ```

    Example output:

    ```text
    --------------------------------
    EKS Cluster Name: <AWS_PREFIX>-cymbalbank
    EKS Cluster Config: aws eks update-kubeconfig --region us-west-1 --name <AWS_PREFIX>r-cymbalbank
    RDS Endpoint:     <AWS_PREFIX>-cymbalbankdb.cyhrzhhyuigb.us-west-1.rds.amazonaws.com
    Frontend URL:     http://k8s-default-frontend-05547d09c1-255394655.us-west-1.elb.amazonaws.com
    --------------------------------
    ```

Access the Frontend URL to ensure the application is up and running in your
Chrome browser.

## Assess the Amazon EKS environment

In this section, you will use the
[Kubernetes Cluster Discovery Tool](https://github.com/GoogleCloudPlatform/professional-services/tree/main/tools/k8s-discovery)
to generate a detailed inventory of your Amazon EKS cluster. This helps verify
which workloads are stateless and ready for direct redeployment.

### Discover Amazon EKS Resources

Use the Discovery Tool to scan your AWS EKS cluster and collect inventory data.

1.  In your terminal, clone the repository:

    ```bash
    CURRENT_DIR=$(pwd)
    git clone https://github.com/GoogleCloudPlatform/professional-services.git
    cd professional-services/tools/k8s-discovery
    ```

1.  Set up a Python virtual environment:

    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

1.  Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

1.  Execute the Python application to scan your Amazon EKS cluster:

    ```bash
    REGION=$(terraform -chdir="${CURRENT_DIR}/aws/terraform"  output -raw aws_region)
    python main.py aws --region $REGION --output-dir ${CURRENT_DIR}/discovery_output
    cd "$CURRENT_DIR"
    ```

Wait for the tool to fetch the inventory. It will connect to the EKS API and
retrieve details on Nodes, Workloads, Networking, and Storage.

### Review the Inventory Report

Verify the generated inventory files and deactivate the Python virtual
environment.

1.  Verify the files generated:

    ```bash
    ls -l discovery_output
    ```

    Example output:

    ```text
    configmaps.csv eks_data.json namespaces.csv pods.csv roles.csv
    service_accounts.csv workloads.csv eks_clusters.csv ingresses.csv
    nodes.csv role_bindings.csv secrets.csv services.csv
    ```

1.  In your local terminal, deactivate the Python environment:

    ```bash
    deactivate
    ```

With the inventory files generated, you can now use Gemini to create a migration
plan.

### Generate migration recommendations using Gemini

Utilize the Gemini CLI to analyze the EKS cluster inventory and generate a GKE
migration plan.

1.  In your terminal, create the `.gemini/commands` directory and copy the
    `aws-container-migration-analysis.toml` file into it:

    ```bash
    mkdir -p .gemini/commands
    cp "$(git rev-parse --show-toplevel)/projects/gemini-powered-migrations-to-google-cloud/.gemini/commands/aws-container-migration-analysis.toml" .gemini/commands/
    ```

1.  Start the Gemini terminal from the current directory:

    ```bash
    gemini
    ```

1.  In the Gemini CLI, run the custom command to generate the recommendations:

    ```bash
    /aws-container-migration-analysis discovery_output
    ```

1.  Review the migration report
    `eks-migration-assessments/eks-migration-plan.md`

1.  After the report is generated, exit Gemini CLI `Ctrl+c` twice

This command will analyze cluster and object inventory files from Amazon EKS
workloads to generate a Google Kubernetes Engine (GKE) migration plan. For more
information about the migration tool, see the
[Gemini-powered migrations](https://github.com/GoogleCloudPlatform/cloud-solutions/blob/main/projects/gemini-powered-migrations-to-google-cloud/test-data/sample-selection/aws-container-migration-analysis.md)

## Provision the Google Cloud infrastructure

You will now provision the target environment.

1.  Create a Google Cloud project:

    ```bash
    export GOOGLE_CLOUD_PROJECT_ID="<GOOGLE_CLOUD_PROJECT_ID>"
    ```

    - `GOOGLE_CLOUD_PROJECT_ID` Your Google Cloud Project ID.

1.  Set the default Google Cloud project and start deployment to GCP:

    ```bash
    export SOURCE_DATABASE_HOSTNAME="$(terraform -chdir='aws/terraform' output -raw rds_endpoint)"
    export SOURCE_DATABASE_DMS_USERNAME="postgres"
    export TF_VAR_rds_password="Chiapet22!"
    gcloud config set project $GOOGLE_CLOUD_PROJECT_ID
    ./gcp/deploy_gcp.sh
    ```

### Configure AWS Security Group for DMS

The AWS RDS instance is not accessible from the internet. The following steps
will configure the AWS security group to allow inbound connections from the
Database Migration Service.

1.  Retrieve the outbound IP address that DMS will use to connect to RDS:

    ```bash
    DB_IP=$(gcloud database-migration connection-profiles describe acp-a-g-demo-dest \
    --region=us-central1 \
    --format="value(cloudsql.publicIp)")
    echo $DB_IP
    ```

1.  Run terraform apply by passing the DB_IP variable. The variable is formatted
    as a list of strings with a /32 CIDR suffix to match the dms_source_ip_cidrs
    type constraint:

    ```bash
    terraform -chdir="aws/terraform" apply -var="dms_source_ip_cidrs=[\"${DB_IP}/32\"]"  --auto-approve
    ```

## Migrate the database to Cloud SQL

The Terraform script has already created the Connection Profile and Migration
Job. You simply need to start the job to begin the data replication.

1.  Navigate to the Database Migration Service console

1.  Select the **Demo migration job** from the list

1.  Click **Edit** to enter the configuration view

1.  Click **Test job** to verify connectivity between the source and destination

1.  If the test returns a success status, click **Save and start**

1.  Wait for the job status to transition to **Running**

1.  Monitor the job as it completes the **Full dump** phase and enters the
    Change Data Capture (CDC) state

    Note: In the CDC state, changes are continuously propagated from the source
    Amazon RDS instance to the target Cloud SQL instance.

1.  Change the password for the postgres user:

    ```bash
    gcloud sql users set-password postgres --instance=acp-a-g-demo-dest --password=$TF_VAR_rds_password
    ```

1.  Click **Promote** in the DMS console

1.  Wait for the migration job's status to say **Completed** before proceeding

Note: **CRITICAL PRODUCTION WARNING:** **Before clicking Promote:** Ensure no
new data is being written to the RDS instance

- In a production scenario, you **must stop the application** to prevent data
  loss.
- Once the DMS promotion is complete, you must update the application
  configuration to point to the new Cloud SQL instance before restarting the
  application.

### Connect to the Cloud SQL instance

In this section, you will connect to the migrated Cloud SQL instance to verify
the data replication.

1.  Open Cloud Shell and connect to the Cloud SQL instance:

    ```bash
    gcloud beta sql connect acp-a-g-demo-dest --user=postgres --quiet
    ```

    When prompted for the Postgres password enter `Chiapet22!`

1.  Connect to the accounts database:

    ```sql
    \c accounts-db
    ```

    When prompted for the Postgres password enter `Chiapet22!`

1.  List records in the contacts table:

    ```sql
    SELECT * FROM contacts;
    ```

    Example output:

    ```text
     id | username |     label     | account_num | routing_num | is_external
    ----+----------+---------------+-------------+-------------+-------------
    1 | testuser | Alice         | 1033623433  | 883745000   | f
    2 | testuser | Bob           | 1055757655  | 883745000   | f
    3 | testuser | Eve           | 1077441377  | 883745000   | f
    4 | alice    | Testuser      | 1011226111  | 883745000   | f
    5 | alice    | Bob           | 1055757655  | 883745000   | f
    6 | alice    | Eve           | 1077441377  | 883745000   | f
    7 | bob      | Testuser      | 1011226111  | 883745000   | f
    8 | bob      | Alice         | 1033623433  | 883745000   | f
    9 | bob      | Eve           | 1077441377  | 883745000   | f
    10 | eve      | Testuser      | 1011226111  | 883745000   | f
    11 | eve      | Alice         | 1033623433  | 883745000   | f
    12 | eve      | Bob           | 1055757655  | 883745000   | f
    13 | testuser | External Bank | 9099791699  | 808889588   | t
    14 | alice    | External Bank | 9099791699  | 808889588   | t
    15 | bob      | External Bank | 9099791699  | 808889588   | t
    16 | eve      | External Bank | 9099791699  | 808889588   | t
    (16 rows)
    ```

1.  Exit the database:

    ```bash
    exit
    ```

## Deploy the Application to GKE

Once the database migration is running and is in CDC state, deploy the
CymbalBank application to your GKE cluster. This involves building the container
images, pushing them to Artifact Registry, and deploying the Kubernetes
manifests.

1.  Open your local terminal where the source code was cloned, set environment
    variables:

    ```bash
    export REGION="us-central1"
    export GKE_CLUSTER="acp-a-g-demo"
    export REPOSITORY='acp-a-g-demo-repository'
    export INSTANCE_NAME='acp-a-g-demo-dest'
    export INSTANCE_CONNECTION_NAME=$(gcloud sql instances describe $INSTANCE_NAME --format='value(connectionName)')
    ```

1.  Run the `gcp/build_and_deploy.sh` script to build the application images,
    store the images to Artifact Registry and deploy the script to the GKE
    cluster:

    ```bash
    gcp/build_and_deploy.sh
    ```

Note: The build_and_deploy.sh script is intended solely for this tutorial to
streamline the setup. For production workloads, we recommend replacing manual
scripts with a managed continuous delivery pipeline using
[Google Cloud Deploy](https://cloud.google.com/deploy).

### Verify the Pod startup

After the build finishes, confirm that the Kubernetes pods are successfully
running on your cluster.

1.  Configure `kubectl` to communicate with your cluster:

    ```bash
    gcloud container clusters get-credentials acp-a-g-demo --region us-central1 --dns-endpoint
    ```

1.  List the running pods:

    ```bash
    kubectl get po,svc
    ```

    You should see output indicating the pods are `Running` and the frontend
    service has an `EXTERNAL-IP` assigned:

    ```text
    NAME                                      READY   STATUS    RESTARTS   AGE
    pod/balancereader-68b5b4f547-6mbcv        2/2     Running   0          33m
    pod/contacts-5459db85f-t9nsx              2/2     Running   0          33m
    pod/frontend-6cbfcf57fd-jzd9c             1/1     Running   0          33m
    pod/ledgerwriter-ffdbb8977-q988d          2/2     Running   0          32m
    pod/loadgenerator-b66884cc9-vxdc5         1/1     Running   0          33m
    pod/transactionhistory-6c99596fc5-t2ghj   2/2     Running   0          33m
    pod/userservice-8447c96568-tm4n5          2/2     Running   0          32m

    NAME                         TYPE           CLUSTER-IP       EXTERNAL-IP      PORT(S)        AGE
    service/balancereader        ClusterIP      34.118.227.70    <none>           8080/TCP       68m
    service/contacts             ClusterIP      34.118.229.170   <none>           8080/TCP       68m
    service/frontend             LoadBalancer   34.118.226.140   104.154.43.102   80:31822/TCP   68m
    service/kubernetes           ClusterIP      34.118.224.1     <none>           443/TCP        114m
    service/ledgerwriter         ClusterIP      34.118.225.150   <none>           8080/TCP       68m
    service/transactionhistory   ClusterIP      34.118.232.99    <none>           8080/TCP       68m
    service/userservice          ClusterIP      34.118.229.173   <none>           8080/TCP       68m
    ```

Troubleshooting:

- If you see ImagePullBackOff, check that your REPOSITORY name matches your
  Artifact Registry.

- If you see CrashLoopBackOff, the app may be failing to connect to the
  database. You will verify this connection in the next section.

- Now that the application workload is running on GKE, the final step is to
  confirm that it is correctly communicating with the migrated Cloud SQL
  instance.

### Verify the migration

Now that the application is running, you will verify that the frontend is
accessible and that it is successfully pulling customer data from the migrated
Cloud SQL database.

1.  Retrieve the external IP of the GKE Load Balancer and open it in your
    browser:

    ```bash
    export FRONTEND_URL="http://$(kubectl get service frontend -o jsonpath='{.status.loadBalancer.ingress[0].ip}')"
    echo $FRONTEND_URL
    ```

    Note: It may take a few minutes for the Load Balancer to provision an IP
    address. If the command returns nothing or `pending`, wait a minute and try
    again.

1.  Copy the IP address output from the previous step and paste it into your web
    browser (e.g., `http://34.x.x.x`)

1.  Verify you can log in, create and view transactions

## Clean up

To avoid incurring charges, destroy the infrastructure when finished.

### Destroy AWS infrastructure

1.  Destroy the demo infrastructure on AWS:

    ```bash
    terraform -chdir="aws/terraform" destroy --auto-approve
    ```

### Destroy Google Cloud infrastructure

1.  Destroy the GCP infrastructure:

    ```bash
    gcloud container clusters delete acp-a-g-demo --region us-central1 \
     --project $GOOGLE_CLOUD_PROJECT_ID --quiet
    devrel-demos/containers/aws-gcp-migration/gcp/google-cloud-infra-teardown.sh
    ```

Note: The `google-cloud-infra-teardown.sh` file is cloned into this repo as part
of the deployment steps.
