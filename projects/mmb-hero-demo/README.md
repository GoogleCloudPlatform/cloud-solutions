# MMB Hero Demo

This document describes the Migrate, Modernize, and Build (MMB) hero demo.

## Requirements

To deploy this demo, you need:

- A Google Cloud project.
- An account that has the `owner` role on that Google Cloud project.
- The [gcloud CLI](https://docs.cloud.google.com/sdk/docs/install)
- [Gemini CLI](https://geminicli.com/docs/get-started/deployment/)
- The
  [codmod CLI](https://docs.cloud.google.com/migration-center/docs/app-modernization-assessment)
- [Docker Engine](https://docs.docker.com/engine/install/) (to test locally on
  your host). This guide assumes that you can
  [manage Docker as a non-root user](https://docs.docker.com/engine/install/linux-postinstall/#manage-docker-as-a-non-root-user),
  so you can run Docker commands without `sudo`.
- [Chrome DevTools MCP](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/main/README.md)

## Prepare the environment

1.  Open
    [Cloud Shell](https://cloud.google.com/shell/docs/launching-cloud-shell).

1.  Install the
    [codmod CLI](https://docs.cloud.google.com/migration-center/docs/app-modernization-assessment#set_up_codmod)

1.  Install the Chrome DevTools MCP in Gemini CLI:

    ```bash
    gemini mcp add chrome-devtools npx chrome-devtools-mcp@latest
    ```

    For more information, see the
    [Chrome DevTools MCP README](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/main/README.md):

1.  Clone the repository and set the working directory:

    ```bash
    git clone https://github.com/GoogleCloudPlatform/cloud-solutions && \
    cd cloud-solutions
    ```

## Chapter 1: Migrate pillar

## Migrate VMs to Compute Engine and databases to Cloud SQL

This guide walks you through migrating a three-tier application from AWS to
Google Cloud using Database Migration Service and Migrate to Virtual Machines.

This process involves:

1.  Discover AWS assets in the Migration Center.
1.  Generate Total Cost of Ownership (TCO) and asset reports.
1.  Migrate an RDS PostgreSQL to Cloud SQL using Database Migration Service
    (DMS).
1.  Migrate Amazon EC2 VMs to Compute Engine using Migrate to Virtual Machines
    (M2VM).

### Migrate Requirements

To deploy this demo, you need:

- An AWS environment.
- A Google Cloud project.
- [Google Cloud SDK latest](https://docs.cloud.google.com/sdk/docs/install)
- [Terraform >= 1.0](https://developer.hashicorp.com/terraform/install)
- [AWS CLI v2+](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)

#### AWS Permissions

Your AWS credentials need permissions for:

- `AdministratorAccess`

#### Google Cloud Permissions

Ensure you have the following permissions:

- `Owner`

### Prepare the Environment

Set up your local environment and authenticate with both cloud providers.

1.  Configure AWS CLI:

    ```bash
    aws configure
    ```

    Enter your AWS Access Key ID and Secret Access Key. Set the default region
    name to `us-east-1`.

#### Store AWS Credentials securely

To avoid storing secrets in your shell history, create a temporary file for your
credentials and source it.

1.  Create a file named `aws_creds.env` with the following content:

    ```bash
    export AWS_ACCESS_KEY_ID=[YOUR_AWS_ACCESS_KEY_ID]
    export AWS_SECRET_ACCESS_KEY=[YOUR_AWS_SECRET_KEY]
    ```

1.  Load the variables and retrieve your user ID:

    ```bash
    source aws_creds.env
    export AWS_USER=$(basename $(aws sts get-caller-identity --query Arn --output text))
    echo $AWS_USER
    ```

    - `AWS_ACCESS_KEY_ID` is your AWS Access Key ID.
    - `AWS_SECRET_ACCESS_KEY` is your AWS Secret Access Key.
    - `AWS_USER` is your AWS user.

1.  Authenticate with Google Cloud:

    ```bash
    export GCP_PROJECT_ID=[YOUR_GCP_PROJECT ID]
    gcloud config set project $GCP_PROJECT_ID
    gcloud auth application-default login
    ```

    Note: This demo is configured to the use region _us-east_ in both AWS and
    Google Cloud. If you need to change regions, remain consistent. Mixing
    regions/zones could cause issues.

### Deploy AWS Infrastructure

To prepare the source environment, open your terminal and deploy the three-tier
application on AWS using Terraform.

1.  Initialize and deploy the Terraform configuration:

    ```bash
    cd "$(git rev-parse --show-toplevel)/projects/migrate-from-aws-to-google-cloud/vm-compute-db-modernization/terraform"
    terraform init
    terraform apply -var="aws_user=$AWS_USER" --auto-approve
    ```

    Example output:

    ```text
    Apply complete! Resources: 22 added, 0 changed, 0 destroyed.

    Outputs:

    alb_dns_name = "hero-demo-app-alb-28618933.us-east-1.elb.amazonaws.com"
    app_instance_id = "i-0cf580505681e92e0"
    app_public_ip = "52.90.5.158"
    app_url = "http://hero-demo-app-alb-28618933.us-east-1.elb.amazonaws.com"
    db_security_group_id = "sg-0ce29207489c05638"
    rds_endpoint = "hero-demo-app-db.cvxdeuwsbkmc.us-east-1.rds.amazonaws.com"
    rds_port = 5432
    summary = <<EOT

    APPLICATION URL:
    http://hero-demo-app-alb-28618933.us-east-1.elb.amazonaws.com

    RDS DATABASE INFO (for GCP DMS):
    Endpoint: hero-demo-app-db.cvxdeuwsbkmc.us-east-1.rds.amazonaws.com
    Port:     5432
    Database: appdb
    DMS User: dms_user
    Password: SecureDmsPass123!

    APP SERVER INFO (for GCP M2VM):
    Instance ID: i-0cf580505681e92e0
    Public IP:   52.90.5.158

    SECURITY GROUP (to add DMS IPs):
    sg-0ce29207489c05638

    NEXT STEPS:
    1. Wait 3-5 minutes for initialization
    2. Test: curl http://hero-demo-app-alb-28618933.us-east-1.elb.amazonaws.com/health

    ============================================================


    EOT
    vpc_id = "vpc-0911d5899f5cbf7b8"
    ```

    Capture Output Details: Upon completion, Terraform displays a summary
    containing critical values. Keep this output visible or save it, as you will
    need the RDS Endpoint, Instance ID, and Security Group ID later.

1.  Verify Deployment: Wait 3-5 minutes for the application to initialize, then
    test the health endpoint:

    ```bash
    APP_URL=$(terraform output -raw app_url)
    curl $APP_URL/health
    ```

    Expected output:

    ```text
    {"database":"connected","status":"healthy"}
    ```

### Assess with Migration Center

Use Migration Center to discover assets and generate reports for planning.

1.  **Run Setup Script:** Execute the helper script to prepare your project:

    ```sh
    cd "$(git rev-parse --show-toplevel)/projects/migrate-from-aws-to-google-cloud/vm-compute-db-modernization/scripts"
    ./migration_center_aws_setup.sh
    ```

    - Creates Service Account: Provisions aws-discovery-sa to run the discovery
      job.
    - Enables APIs: Activates required services (Migration Center, Compute,
      Cloud SQL, etc.).
    - Grants Permissions: Binds the necessary IAM roles (migrationcenter.admin,
      secretmanager.secretAccessor) to the service account.
    - Secures Credentials: Safely stores your AWS_SECRET_ACCESS_KEY in Secret
      Manager (aws-discovery-secret).

#### Initialize Migration Center

Configure
[Migration Center](https://console.cloud.google.com/migration/overview) in the
Google Cloud Console.

1.  Navigate to **Migration Center** and click **Get Started**.
1.  Configure settings:
    - Region: `us-east-1`
    - Account: Add custom account named `TEST`
    - Opportunity: Add custom opportunity named `TEST`

1.  Click **Next**, then **Continue**.

#### Run Discovery

Discover AWS assets using direct AWS discovery.

1.  Navigate to **Data import** \> **Add data** \> **Direct AWS discovery**

1.  Provide the following information:
    - Account ID: `AWS Access Key ID`
    - Account secret: `aws-discovery-secret` (created by the script).
    - Region: `us-east-1`
    - Service account: `Migration Center AWS Discovery SA` (created by the
      script).

1.  Click **Start AWS discovery**

1.  Monitor progress in **Cloud Run** > **Jobs**.
    - Wait for the job to complete successfully.
    - Once the Cloud Run job is successful, navigate back to Migration Center \>
      Assets to view the discovered AWS resources.

#### Generate Reports

Generate TCO and asset reports to inform your migration strategy.

1.  In Migration Center, click **Groups** > **Create group** and enter:
    - Group name: `migration group`
    - Add assets:
        1.  Click on **Servers** and select the server.
        1.  Click on **Database deployments** and select the RDS arn.
        1.  Click **Create**

1.  Generate a TCO Report:
    - In **Migration Center** > **Reports** > **Create reports**
    - Click on **TCO and detailed pricing**
    - Enter a report name and click **Next**
    - Select the group and click **Next**
    - Click **Generate report**

1.  Click on the generated TCO report to view the Asset summary.

1.  Generate an Asset Inventory:
    - In **Migration Center** > **Reports** > **Create reports**
    - Click on **Asset detail export**
    - In the **All assets**, select **Servers** and **Database deployments**
    - Click **Export to CSV/Google Sheets**
    - Open the CSVs to inspect vCPU count, RAM, and other specifications

### Plan the Migration

Using the data gathered in the assessment phase, you create a mapping plan.

This ensures your target infrastructure is "right-sized" and compatible.

1.  **Analyze Database Requirements:** Review the source database specifications
    identified in the asset report and map them to the appropriate Cloud SQL
    version to ensure compatibility and performance.
1.  **Analyze Compute Requirements:** Review the source VM specifications (vCPU,
    RAM, and OS) identified in the asset report and map them to a Google Cloud
    instance type that provides equivalent capacity for the workload.

### Migrate

With the migration plan in place, you can now proceed with migrating the
database as first using the Database Migration Service (DMS)from AWS RDS to
Cloud SQL and then migrate the VM from EC2 to Compute Engine using Migrate to
Virtual Machines (M2VM).

#### Migrate Database (RDS to Cloud SQL)

Use
[Database Migration Service](https://console.cloud.google.com/dbmigration/connection-profiles)
to replicate data from AWS RDS to Cloud SQL.

##### Download RDS Certificate

Download the certificate bundle for secure TLS authentication.

1.  Download the certificate:

    ```bash
    wget https://truststore.pki.rds.amazonaws.com/us-east-1/us-east-1-bundle.pem
    ```

    This will download the certificates as `us-east-1-bundle.pem`.

##### Create Source Connection Profile

1.  Click **Create profile**:
    - Profile: **Source**
    - Database engine: **Amazon RDS for PostgreSQL**
    - Connection profile name: **aws-postgres-source**
    - Region: **us-east1**

1.  Click **Define** in \*\*Define connection configurations:
    - Hostname or IP address: [Enter the RDS endpoint],
      example:`hero-demo-app-db.cvxdeuwsbkmc.us-east-1.rds.amazonaws.com`
    - Port: **5432**
    - User: **dms_user**
    - Password: **SecureDmsPass123!**
    - Encryption type: **Server-only**

1.  Upload the certificate `us-east-1-bundle.pem`

1.  Click **Create**.

##### Create Migration Job

Create a migration job to replicate data to Cloud SQL.

1.  Navigate to **Migration jobs** > **Create Migration Job**.

1.  Configure job settings:
    - Migration job name: `hero-demo-db-migration`
    - Source database engine: **Amazon RDS for PostgreSQL**
    - Destination database engine: **Cloud SQL for PostgreSQL**
    - Destination region: `us-east1`

1.  Click **Save & Continue**.

1.  Select source: **aws-postgres-source**, then **Save & Continue**.

1.  Create destination:
    - Select **New Instance**
    - Instance ID: **postgres-instance**
    - Password: **SecureAppPass123!**
    - Database version: **Cloud SQL for PostgreSQL 16**
    - Edition: **Enterprise**
    - Network: Check **Private** and **Public**
    - Click **Create & Continue**
    - Wait for instance creation to complete

1.  Define connectivity method:
    - Select **IP allowlist**
    - Copy the displayed IP addresses

##### Configure AWS Security Group

Allow DMS to connect to your RDS instance.

1.  In AWS Console, navigate to **RDS** > **Databases**.

1.  Select the application EC2 instance

1.  Under **Connectivity & security**, click the Security group link.

1.  Click **Edit inbound rules** > **Add rule**:
    - Type: **PostgreSQL**
    - Source: Paste the DMS IP addresses

1.  Click **Save rules**.

##### Configure Parameter Group

Enable pglogical in the RDS parameter group.

1.  In AWS Console, navigate to **RDS** > **Parameter groups**.

1.  Select the parameter group used by your instance.

1.  Search for **shared_preload_libraries**.

1.  Edit the parameter:
    - Add `,pglogical` to the existing values

1.  Click **Save changes**.

1.  Reboot the RDS instance.

##### Enable pglogical Extension

Enable the pglogical extension and grant permissions to the migration user.

1.  Once the RDS instance is rebooted, go to **EC2** > **Instances**.

1.  Select your app instance and click **Connect**.

1.  Select **Session Manager** tab and click **Connect**.

1.  Log into the database:

    ```bash
    RDS_ENDPOINT=$(cat /opt/flask-app/.env | grep DB_HOST | cut -d= -f2)
    export PGPASSWORD='SecureAppPass123!'

    psql -h $RDS_ENDPOINT -U postgres -d appdb
    ```

1.  Run the following commands to configure the database for migration:

    ```sql
    CREATE EXTENSION pglogical;
    GRANT USAGE ON SCHEMA pglogical TO dms_user;
    GRANT ALL ON ALL TABLES IN SCHEMA pglogical TO dms_user;
    GRANT ALL ON ALL SEQUENCES IN SCHEMA pglogical TO dms_user;
    SELECT nspname, pg_catalog.has_schema_privilege('dms_user', nspname, 'USAGE') as has_usage
    FROM pg_namespace WHERE nspname = 'pglogical';
    ```

1.  Terminate the session.

##### Reboot Database

Reboot the RDS instance to apply parameter group changes.

1.  In AWS Console, navigate to **RDS** > **Databases**.

1.  Select the database.

1.  Click **Actions** > **Reboot**.

1.  Wait for status to return to **Available**.

#### Start and Promote Migration

1.  Start the Migration Job (Google Cloud):
    - Navigate back to the Google Cloud Console.
    - In the **Database to migrate** dropdown, select **Specific database**.
    - Select the database named **appdb**.
    - Click **Test**, the test should show as successful.
    - Click **Create & Start Job**.

1.  **CRITICAL PRODUCTION WARNING**:

    **Before clicking Promote**: Ensure no new data is being written to the RDS
    instance.

    In a production scenario, you **must stop the application** on EC2 now (or
    put it in Maintenance Mode/Read-Only) to prevent data loss.

    Once the DB promotion is complete, you must update the application
    configuration to point to the new Cloud SQL instance before restarting the
    application.

1.  Promote the Migration:
    - Monitor the job status.
    - When the status changes to CDC (Change Data Capture) and the lag is near
      zero, click **Promote**.
    - Confirm the promotion. This disconnects the AWS source and makes the Cloud
      SQL instance is your primary, standalone database.

#### Migrate Virtual Machine (EC2 to Compute Engine)

Use
[Migrate to Virtual Machines](https://console.cloud.google.com/compute/mfce/sources)
to replicate the application server.

##### Create AWS Source

Create a source to connect M2VM to your AWS account.

1.  Navigate to **Migrate to Virtual Machines** > **SOURCES** tab.

1.  Click **ADD SOURCE** > **Add AWS Source**.

1.  Enter source details:
    - Name: `aws-source`
    - Google Cloud region: `us-east1`
    - AWS region: `us-east-1`
    - AWS Access key ID: Enter your access key
    - AWS Secret access key: Enter your secret key

1.  Click **Create**.

1.  Wait up to 15 minutes for the **status** to become **Active**.

##### Start Replication

1.  From Sources tab, select your source VM, Click **Add Migrations** > **VM
    migration** and click **Confirm**

1.  Click on the **Migrate VMs** tab and click **Edit target details**

1.  In the Migrate VMs tab, select the Source asset VM and click edit.

1.  In Target details:
    1.  **General**:
        - Instance name: **hero-demo-app**
        - Project: **Select your project**
        - Zone: **us-east1-b**

    1.  In **Machine configuration**:
        - Machine type series: **e2**
        - Machine type: **e2-small**
        - On host maintenance: **Migrate VM instance**
        - Automatic restart: **On**

    1.  In **Networking**:
        - Network: **default**
        - Subnetwork: **default**
        - External IP: **Ephemeral**
        - Internal IP: **Ephemeral(Automatic)**

    1.  In **Additional configuration**:
        - Service account: **Compute Engine default**
        - Disk type: **SSD**

1.  In the Google Cloud console, open a new tab and navigate to **IAM**
    1.  Add the **Service Account User** role to the Migrate to Virtual Machines
        service account.

        This message will appear: Make sure that the Migrate to Virtual Machines
        service account
        `service-[PROJECT-NUMBER]@gcp-sa-vmmigration.iam.gserviceaccount.com`
        has the `iam.serviceAccountUser` role on the selected target VM service
        account.

1.  Navigate back to the Migrate to Virtual Machines page and click **Save**

1.  From Migrate VMs tab, select your migration, from dropdown **Migration** >
    **Start replication**

##### Cutover

Finalize the migration to create the Compute Engine instance.

1.  Wait for **Replication status** to reach **Active (Idle)**.

1.  Click **Cut-over and Test-clone** tab and select **Cut-Over**.

    Note: In real-world examples, select **Test-Clone** first.

1.  Review details and click **Start Cutover**.

1.  Click on the Migration job and select the **Test-clone/Cut-over history** to
    view the cutover progress.

1.  Wait for the cutover job to complete.

##### Configure Application and Load Balancing

Now that the VM is migrated to Compute Engine, you must configure it to connect
to the new Cloud SQL instance and expose the application to the internet using a
Global Application Load Balancer.

1.  Open the `scripts/connect_and_configure.sh` file and ensure the
    configuration variables are correct:

    ```text
    VM_NAME="hero-demo-app"
    ZONE="us-east1-b"
    CLOUD_SQL_INSTANCE="postgres-instance"
    NETWORK="default"

    # Database credentials
    DB_NAME="appdb"
    DB_USER="appuser"
    DB_PASSWORD="SecureAppPass123!"
    DB_PORT="5432"
    ```

1.  **Run the Configuration Script**: Execute the helper script. This script
    automatically connects to your VM via SSH to update the database connection
    strings (pointing to the new Cloud SQL Private IP) and restarts the
    application. It then provisions the required load balancing resources
    (Instance Group, Health Check, Backend Service, and Forwarding Rule).

    ```bash
    cd "$(git rev-parse --show-toplevel)/projects/migrate-from-aws-to-google-cloud/vm-compute-db-modernization/scripts"
    ./connect_and_configure.sh
    ```

    Example output:

    ```text
    ============================================================
    DEPLOYMENT COMPLETE
    ============================================================

    Load Balancer IP: 34.54.136.151
    Cloud SQL IP: 10.27.208.3

    Wait 2-3 minutes for health checks to pass, then test:

    curl http://34.54.136.151/health
    curl http://34.54.136.151/api/users

    ============================================================
    ```

1.  **Verify the Deployment**: Wait 2-3 minutes for the health checks to
    initialize and pass, then test the application health endpoint using the
    Load Balancer IP.

    ```bash
    curl http://34.54.136.151/health

    curl http://34.54.136.151/api/users
    ```

    Expected output:

    ```json
    {"database":"connected","db_host":"10.27.208.3","hostname":"test","status":"healthy"}

    {"count":10,"users":[{"created_at":"Wed, 03 Dec 2025 17:48:00 GMT","department":"Engineering","email":"alice@example.com","id":1,"name":"Alice Johnson"},{"created_at":"Wed, 03 Dec 2025 17:48:00 GMT","department":"Marketing","email":"bob@example.com","id":2,"name":"Bob Smith"},{"created_at":"Wed, 03 Dec 2025 17:48:00 GMT","department":"Engineering","email":"carol@example.com","id":3,"name":"Carol White"},{"created_at":"Wed, 03 Dec 2025 17:48:00 GMT","department":"Sales","email":"david@example.com","id":4,"name":"David Brown"},{"created_at":"Wed, 03 Dec 2025 17:48:00 GMT","department":"HR","email":"emma@example.com","id":5,"name":"Emma Davis"},{"created_at":"Wed, 03 Dec 2025 17:48:00 GMT","department":"Engineering","email":"frank@example.com","id":6,"name":"Frank Miller"},{"created_at":"Wed, 03 Dec 2025 17:48:00 GMT","department":"Marketing","email":"grace@example.com","id":7,"name":"Grace Lee"},{"created_at":"Wed, 03 Dec 2025 17:48:00 GMT","department":"Sales","email":"henry@example.com","id":8,"name":"Henry Wilson"},{"created_at":"Wed, 03 Dec 2025 17:48:00 GMT","department":"Engineering","email":"ivy@example.com","id":9,"name":"Ivy Chen"},{"created_at":"Wed, 03 Dec 2025 17:48:00 GMT","department":"HR","email":"jack@example.com","id":10,"name":"Jack Taylor"}]}
    ```

### Congratulations

The database and VM have been successfully migrated from AWS EC2 and RDS to
Google Cloud's Compute Engine and Cloud SQL.

### Cleanup

Remove all resources created during this demo.

1.  Finalize Migrate to Virtual Machines migration in Google Cloud Console.

    From Migrate VMs tab, select your migration, from dropdown **Migration** >
    **Finalize replication**

1.  Destroy AWS resources:

    ```bash
    terraform destroy -var="aws_user=$AWS_USER" -auto-approve
    ```

1.  Delete Google Cloud resources:
    - Forwarding rule
    - Compute Engine VM
    - Cloud SQL instance

## Chapter 2: Modernize pillar

### Gemini-powered .NET modernization

In this demo, you modernize a .NET Framework application to a Linux-ready .NET
application.

This demo guide walks you through the following steps:

1.  Prepare the environment
1.  Generate a modernization assessment
1.  Modernize the application
1.  Generate deployment descriptors
1.  Deploy on Google Cloud

#### Run the Migration Center App Modernization Assessment

To generate a Migration Center App Modernization Assessment report, you do the
following:

1.  Set the working directory:

    ```bash
    cd "$(git rev-parse --show-toplevel)/projects/dotnet-modernization-demo"
    ```

1.  Generate the report:

    ```bash
    codmod create full \
      --codebase ./dotnet-migration-sample \
      --output-path ./codmod-full-report-dotnet-mod.html \
      --experiments=enable_pdf,enable_images \
      --improve-fidelity \
      --intent=MICROSOFT_MODERNIZATION \
      --optional-sections "files,classes"
    ```

    This command takes about 15 minutes to run.

1.  Open the generated report with a web browser, such as Google Chrome.

To review how the output looks like, see the sample report:
`modernization-report-sample/third_party/codmod-full-report-dotnet-mod.html`.

#### Modernize the .NET application using Gemini CLI

1.  Change the working directory to the .NET application directory:

    ```bash
    cd "$(git rev-parse --show-toplevel)/projects/dotnet-modernization-demo/dotnet-migration-sample"
    ```

1.  Run Gemini CLI:

    ```bash
    gemini
    ```

1.  Copy the prompt defined in `modernization-prompt.md`, and paste the prompt
    in the Gemini CLI user interface, and press the Enter key.

To complete the execution, Gemini CLI takes about 25 minutes.

##### Sample modernized application

The `dotnet-migration-sample-modernized` directory contains an example of the
modernized .NET application resulting in running Gemini CLI with the above
prompt.

To run the example modernized application locally, you do the following:

1.  Change the working directory to the .NET application directory:

    ```bash
    cd "$(git rev-parse --show-toplevel)/projects/dotnet-modernization-demo/dotnet-migration-sample-modernized"
    ```

1.  Run the application using Docker Compose:

    ```bash
    docker compose up --build
    ```

1.  Wait for the application to accept connections. When the application is
    ready to accept connections, the output is similar to the following:

    ```text
    app-1  | {"EventId":14,"LogLevel":"Information","Category":"Microsoft.Hosting.Lifetime","Message":"Now listening on: http://0.0.0.0:8080","State":{"Message":"Now listening on: http://0.0.0.0:8080","address":"http://0.0.0.0:8080","{OriginalFormat}":"Now listening on: {address}"}}
    ```

1.  Open `http://localhost:8080/` with a web browser, such as Google Chrome.

1.  Navigate the application using the web browser.

After completing your test, stop the application by sending the `CTRL+C` key
combination.

#### Deploy the application to Google Cloud

To deploy the the example modernized application to Google Cloud using Cloud
Run, Artifact Registry, and Cloud SQL for PostgreSQL, follow the guidance in
this section.

You can follow similar steps to deploy your own modernized .NET application.

##### 1. Set up your Google Cloud environment

Set your project ID and region as environment variables in your shell.

```bash
export PROJECT_ID="[YOUR_PROJECT_ID]"
export REGION="[YOUR_REGION]" # e.g., us-central1
gcloud config set project $PROJECT_ID
gcloud config set run/region $REGION
```

##### 2. Enable necessary Google Cloud APIs

Enable the APIs for Artifact Registry, Cloud SQL, Cloud Build, and Cloud Run.
This allows the services to work together.

```bash
gcloud services enable \
    iam.googleapis.com \
    artifactregistry.googleapis.com \
    sqladmin.googleapis.com \
    run.googleapis.com \
    cloudbuild.googleapis.com
```

##### 3. Create an Artifact Registry repository

Create a Docker repository in Artifact Registry to store the container images
for your application.

```bash
export REPO_NAME="contoso-university-repo"
gcloud artifacts repositories create $REPO_NAME \
    --repository-format=docker \
    --location=$REGION \
    --description="Docker repository for Contoso University"
```

##### 4. Create a Cloud SQL for PostgreSQL instance

Create a PostgreSQL instance to host the application's database. This may take a
few minutes.

```bash
export INSTANCE_NAME="contoso-university-db"
export DB_PASSWORD="[YOUR_DB_PASSWORD]" # Choose a strong password
gcloud sql instances create $INSTANCE_NAME \
    --database-version=POSTGRES_13 \
    --tier=db-g1-small \
    --region=$REGION \
    --root-password=$DB_PASSWORD
```

After the instance is created, create a database for the application.

```bash
gcloud sql databases create contosouniversity --instance=$INSTANCE_NAME
```

##### 5. Build and push the container image

Use Google Cloud Build to build your container image and push it to the Artifact
Registry repository you created. Cloud Build uses the `Dockerfile` in your
project root.

```bash
cd "$(git rev-parse --show-toplevel)/projects/dotnet-modernization-demo/dotnet-migration-sample-modernized"
gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/contoso-university:latest .
```

##### 6. Deploy the application to Cloud Run

Deploy the container image from Artifact Registry to Cloud Run. This command
creates a new Cloud Run service and connects it to your Cloud SQL instance.

First, get your Cloud SQL instance connection name:

```bash
export INSTANCE_CONNECTION_NAME=$(gcloud sql instances describe $INSTANCE_NAME --format='value(connectionName)')
```

Now, deploy the service to Cloud Run:

```bash
gcloud run deploy contoso-university \
    --image=$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/contoso-university:latest \
    --platform managed \
    --allow-unauthenticated \
    --add-cloudsql-instances=$INSTANCE_CONNECTION_NAME \
    --region "${REGION}" \
    --set-env-vars "ConnectionStrings__SchoolContext=Host=/cloudsql/${INSTANCE_CONNECTION_NAME};Database=contosouniversity;Username=postgres;Password=${DB_PASSWORD}"
```

This command will prompt you to confirm the deployment. After it completes, it
will output the URL for your deployed service.

##### 7. Test the application

Once the deployment is complete, you can test the application:

1.  Copy the URL provided in the output of the `gcloud run deploy` command.
1.  Open the URL in a web browser.
1.  You should see the Contoso University application homepage. You can navigate
    through the site to view students, courses, instructors, and departments.
    The application is now running live on Cloud Run and connected to your Cloud
    SQL database.
1.  Optionally, you can go back to the Gemini CLI and ask it to run the
    automated UI tests again, this time against the deployed application's URL.

#### Clean up your Google Cloud environment

To avoid incurring unwanted charges, follow these steps to remove all the
resources provisioned for this demo.

1.  Delete the Cloud Run service

    ```bash
    gcloud run services delete contoso-university --platform managed --region=$REGION --quiet
    ```

1.  Delete the Artifact Registry repository

    ```bash
    gcloud artifacts repositories delete $REPO_NAME --location=$REGION --quiet
    ```

1.  Delete the Cloud SQL for PostgreSQL instance

    ```bash
    gcloud sql instances delete $INSTANCE_NAME --quiet
    ```

## Chapter 3: Build pillar

### Accelerating Development with Gemini: Prototyping, Implementation, and Code Review

In this demo, you prototype and implement application features with Gemini.

This demo guide walks you through the following steps:

1.  Prepare the environment
1.  Prototype ADK agents with Gemini CLI
1.  Implement new features with Gemini CLI
1.  Automate GitHub Pull Requests reviews with Code Review Agent

#### Build Pillar Requirements

In addition to the [requirements](#requirements), you also need the following to
follow this chapter:

- A Google Cloud project with the `Owner` role.
- GitHub account and repository
- Gemini CLI: Installed and configured. For installation instructions, visit
  [geminicli.com](https://geminicli.com/docs/get-started/deployment/).
- GitHub CLI: Installed and configured. For installation instructions, visit
  [Installation](https://github.com/cli/cli?tab=readme-ov-file#installation).

Detailed setup instructions for each demonstration are located within their
respective sections below.

#### Prototype ADK Agents with Gemini CLI

This demonstration guide walks through the process of rapidly prototyping an ADK
(Agent Development Kit) agent using the Gemini CLI. You will leverage the Gemini
CLI's planning and implementation capabilities to quickly scaffold and refine a
functional customer support agent. This "vibe prototyping" approach allows for
fast iteration and development, showcasing how AI-assisted tools can accelerate
the creation of complex agents and services. By the end of this demo section,
you will have a working ADK agent capable of looking up and summarizing
in-memory ticket data, all built and debugged primarily through natural language
commands in the Gemini CLI.

#### Key Files

1.  **GEMINI.md**: Provides instructions on how to use the reference
    documentation to build ADK agents.
1.  **AGENTS.txt**: Contains detailed information and best practices for agent
    development.

AGENTS.txt file is imported into the GEMINI.md and will be included in the
Gemini CLI session’s context when you interact with the Gemini CLI.

This feature facilitates the decomposition of large GEMINI.md files into
smaller, more manageable modules that can be seamlessly reused across varied
contexts. The import processor supports both relative and absolute paths,
incorporating robust safety mechanisms to avoid circular imports and ensure
secure file access.

#### Custom Commands

These custom commands help you in both planning and implementing ADK agents.

1.  `/plan:new` - this command leverages provided documentation (GEMINI.md,
    AGENTS.md) to generate an implementation plan, ensuring adherence to best
    practices.

1.  `/plan:impl` - this command uses the implementation plan to generate the
    necessary Python files, reducing boilerplate and focusing on ADK
    requirements.

#### Start building the agent

1.  Change the working directory:

    ```bash
    cd "$(git rev-parse --show-toplevel)/projects/build-with-gemini-demo/prototype-adk-agent-with-gemini-cli"
    ```

1.  Rename `.env.sample` to `.env` file and update with your Google Cloud
    project information:

    ```text
    GOOGLE_GENAI_USE_VERTEXAI=TRUE
    GOOGLE_CLOUD_PROJECT="<ENTER_YOUR_PROJECT_ID>"
    GOOGLE_CLOUD_LOCATION="<ENTER_YOUR_PROJECT_LOCATION>" # e.g. us-central1
    ```

1.  Acquire new user credentials:

    ```bash
    gcloud auth application-default login
    ```

1.  Run Gemini CLI:

    ```bash
    gemini
    ```

1.  Send prompt to create implementation plan:

    ```text
    /plan:new Build a customer support ADK agent that allows users to look up the full details of any ticket using its ID and also provide the ability to return a summary for any selected ticket. For summary requests return ticket description. Generate 20 sample tickets (each with an an integer based ID, title, and description) and use them as an in-memory db.
    ```

    Review generated plan and request implementation. You can find an example
    plan in the
    `projects/build-with-gemini-demo/prototype-adk-agent-sample/plans/customer_support_agent.md`
    file.

1.  Send prompt to implement the plan:

    ```text
    /plan:impl implement the plan and generate a requirements.txt file for more reproducible builds.
    ```

    Review and approve tools and suggested code changes.

    The `prototype-adk-agent-sample` folder contains sample implementation plan
    and customer support agent built with the prompts above.

1.  Exit from Gemini CLI and run commands to setup virtual environment and
    install required dependencies for ADK agent:

    ```bash
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

1.  Start ADK Web Server to test the agent:

    ```bash
    adk web .
    ```

    Click on the link to open application in the browser.

    In the Cloud Shell environment, select Web Preview from the menu and change
    port(eg. 8000) and preview the application.

1.  Testing the Agent

    After you start the application and select the agent from the dropdown in
    the top left corner. Send a greeting to the agent and ask how they can help.
    This will prompt the agent to describe available operations.

    Sample queries to try:

    ```text
    lookup ticket # 10
    ```

    ```text
    summarize ticket # 5
    ```

You can find an example implementation of this agent in the
`projects/build-with-gemini-demo/prototype-adk-agent-sample` directory.

Stop ADK Web server before moving to the next section.

### Implement features with Gemini CLI

This guide demonstrates how Gemini CLI accelerates feature development within
the Software Development Lifecycle (SDLC). By leveraging context files and
natural language prompts, Gemini CLI seamlessly integrates feature requirements
into the development environment, facilitating efficient planning, review, and
implementation. The workflow covers initial setup, autonomous code generation
(specifically, adding a rating feature to a menu service).

#### Setup directory

1.  Change the working directory:

    ```bash
    cd "$(git rev-parse --show-toplevel)/projects/build-with-gemini-demo/gemini-powered-development/menu-service"
    ```

#### Generating GEMINI.md file

Context files are a effective way to provide instructional context to the Gemini
model, eliminating the need to repeat instructions in every prompt. These files,
which default to the name GEMINI.md, help you define a persona, provide coding
style guides, or give project-specific instructions to ensure the Gemini's
responses are accurate and meet your specific requirements.

1.  Run Gemini CLI:

    ```bash
    gemini
    ```

1.  Send the prompt to analyze the project and create a tailored GEMINI.md file:

    ```text
    /init
    ```

    Review generated GEMINI.md file.

1.  Send the prompt to load generated file into the context:

    ```text
    /memory refresh
    ```

#### Codebase explanation

An onboarding use case is perfect for Gemini CLI because it allows a new
developer to quickly gain a deep understanding of an existing codebase without
manual, time-consuming investigation. By running simple commands, a developer
can prompt Gemini CLI to analyze the repository (using the codebase as context),
generate high-level summaries of the architecture, explain specific files or
functions, and create a tailored plan for their first task. This immediate,
Gemini-powered codebase exploration accelerates time-to-productivity, making the
new team member effective in minutes rather than days or weeks.

1.  Send the prompt to help you learn the codebase:

    ```text
    Act as a Technical Lead. I am a new developer joining this project.
    Please analyze this codebase and provide an Onboarding Guide.
    Include the following:
    - High-Level Architecture: What is the tech stack, and how do the components interact?
    - Key Functionality: What are the top 3 primary features this code executes?
    - Folder Structure: Briefly explain the purpose of the main directories.
    - Data Flow: Trace the path of a request from the entry point to the database and back.
    ```

#### Plan feature implementation

The Gemini CLI accelerates feature development by offering a "plan and
implement" workflow. For a new feature, a developer can prompt the CLI, which
then analyzes the codebase and user request to generate a detailed multi-step
plan. This plan outlines the necessary code changes, new files, and
modifications, serving as a blueprint. Once the developer approves the plan,
they execute the implementation command, and the Gemini CLI autonomously carries
out the planned tasks, significantly reducing the manual effort and accelerating
requirements to code.

1.  Send prompt with the task requirements:

    ```text
    Review the code and prepare the implementation plan for requirements below.
    I will approve the plan before you can start implementation.

    Update Menu service:
    1. add new fields: description and rating to Menu entity
    2. update other dependencies where Menu entity is used in the code, eg MenuResource.
    3. Add unit tests for all methods, including new fields.

    Rating must be an integer value from 1 to 5.
    Can’t be null.
    Can’t be empty.
    Can’t be zero.
    ```

    Review the plan and request to implement the changes.

#### Start feature implementation

1.  Send prompt to start the implementation:

    ```text
    Implement the changes in menu-service app
    ```

    Review and approve tools and suggested code changes. If Gemini CLI runs into
    issues, for example test validation, multiple iterations might be required
    to fix and re-run until generated code is valid.

#### SRE Resilience & Availability Audit

This prompt configures the Gemini CLI to act as a Senior Site Reliability
Engineer, performing a specialized architectural audit that looks beyond
standard linting to identify structural weaknesses capable of causing system
outages. It proactively detects hidden risks like missing network timeouts,
improper resource cleanup, and Single Points of Failure (SPOFs), while
highlighting tight coupling that prevents graceful degradation. Beyond just
identifying issues, it delivers actionable remediation strategies, offering
concrete code refactoring examples and architectural patterns to immediately
harden your system against runtime availability risks.

1.  Send prompt to start the implementation:

    ```text
    You are a Senior Site Reliability Engineer and System Architect. Analyze this codebase specifically for system resilience and availability.

    Please provide a report covering the following three areas:

    1. **Single Points of Failure (SPOF):**
    * Identify architectural bottlenecks where the failure of one component (e.g., a specific database connection, a hardcoded external API, a monolithic function, or a singleton service) would bring down the entire application.
    * Highlight tight coupling that prevents graceful degradation.

    2. **Runtime Availability Risks:**
    * Analyze the code for patterns that negatively impact uptime, such as:
        * Missing or aggressive timeouts on network calls.
        * Lack of retries or exponential backoff strategies.
        * Synchronous blocking operations in the main execution path.
        * Improper resource management (memory leaks, unclosed file handles/connections).
        * Inadequate error handling (swallowing exceptions or crashing ungracefully).

    3. **Remediation & Improvements:**
    * For every issue identified, provide a specific architectural or code-level recommendation (e.g., implementing Circuit Breakers, introducing caching, decoupling services, or adding health checks).
    * Provide brief code refactoring examples where applicable.
    ```

    Review recommendations in the generated report.

Exit from Gemini CLI before moving to the next section.

### Automate GitHub Pull Requests reviews with Code Review Agent

This section goes over the process of integrating and utilizing Gemini Code
Assist to improve GitHub code reviews. The demo will cover essential setup
procedures in both Google Cloud and GitHub, followed by a showcase of Gemini
Code Assist's capabilities in delivering smart suggestions, clear explanations,
and concise summaries to optimize the code review workflow.

#### GitHub Prerequisites

Use existing or create a new GitHub repository to configure Gemini Code Assist
on GitHub.

Below are the steps to create a new GitHub repository using `gh` cli from the
Cloud Shell environment.

1.  Authenticate with GitHub using HTTPS option:

    ```bash
    gh auth login
    ```

1.  Create a new private repository:

    ```bash
    cd ~ && gh repo create gemini-code-review-agent --private \
    --clone --add-readme -d "Gemini Code Assist on GitHub"
    ```

#### Google Cloud Project Prerequisites

You need `Admin` or `Owner` basic roles for your Google Cloud project.
[Setup details](https://developers.google.com/gemini-code-assist/docs/set-up-code-assist-github#before-you-begin).

#### Install Gemini Code Assist application on GitHub

Follow
[instructions](https://developers.google.com/gemini-code-assist/docs/set-up-code-assist-github#enterprise)
to install Gemini Code Assist on GitHub.

#### Code Review Agent Configuration

At this point, Code Review agent is enabled for the selected repositories.

1.  On the `Settings` screen for your Developer connection, you have an option
    to select comment severity level and also enable memory to improve review
    response quality.
1.  On the `Style Guide` tab, you have an option to provide a project specific
    style guide. If your repository already contains a `.gemini/styleguide.md`
    file, the instructions from both places will be concatenated and used as an
    input for the Code Review Agent during the PR review process.

#### GitHub MCP Server configuration

Return to the Cloud Shell terminal and configure GitHub MCP Server:

1.  Change into `gemini-code-review-agent` folder:

    ```bash
    cd ~/gemini-code-review-agent
    ```

1.  Copy `menu-service` folder into the new project:

    ```bash
    cp -r ~/cloud-solutions/projects/build-with-gemini-demo/gemini-powered-development/menu-service .
    ```

1.  Set environment variable in the terminal:

    ```bash
    export GITHUB_PERSONAL_ACCESS_TOKEN=$(gh auth token)
    ```

1.  Start Gemini CLI:

    ```bash
    gemini
    ```

1.  Commit new changes and open a pull request:

    ```text
    Create a new feature branch, add/commit all the changes and open a new pull request.
    ```

    Review and approve tools that Gemini CLI requires to complete this task.

Exit from Gemini CLI before moving to the next section.

#### Pull Request Review

Open GitHub repository in the browser and observe the Code Review Agent
providing a summary and review for the created pull request.

#### Invoking Gemini

You can request assistance from Gemini at any point by creating a PR comment in
the GitHub UI using either `/gemini <command>` or
`@gemini-code-assist <command>`.

1.  Code Review - Performs a code review of the pull request:

    ```text
    /gemini review
    ```

1.  Pull Request Summary - Provides a summary of the pull request:

    ```text
    /gemini summary
    ```

1.  Comment - Responds in comments when explicitly tagged, both in pull request
    comments and review comments:

    ```text
    @gemini-code-assist
    ```
