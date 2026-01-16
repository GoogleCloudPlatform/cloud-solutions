# Migrate VMs to Compute Engine and databases to Cloud SQL

This guide walks you through migrating a three-tier application from AWS to
Google Cloud using Database Migration Service and Migrate to Virtual Machines.

This process involves:

1.  Discover AWS assets in the Migration Center.
1.  Generate Total Cost of Ownership (TCO) and asset reports.
1.  Migrate an RDS PostgreSQL to Cloud SQL using Database Migration Service
    (DMS).
1.  Migrate Amazon EC2 VMs to Compute Engine using Migrate to Virtual Machines
    (M2VM).

## Requirements

To deploy this demo, you need:

- An AWS environment.
- A Google Cloud project.
- [Google Cloud SDK latest](https://docs.cloud.google.com/sdk/docs/install)
- [Terraform >= 1.0](https://developer.hashicorp.com/terraform/install)
- [AWS CLI v2+](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)

### AWS Permissions

Your AWS credentials need permissions for:

- `AdministratorAccess`

### Google Cloud Permissions

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
    AWS_USER=$(basename $(aws sts get-caller-identity --query Arn --output text))
    export AWS_USER
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

1.  Clone the repository and set the working directory:

    ```bash
    git clone https://github.com/GoogleCloudPlatform/cloud-solutions && \
    cd cloud-solutions
    ```

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

##### Start and Promote Migration

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
