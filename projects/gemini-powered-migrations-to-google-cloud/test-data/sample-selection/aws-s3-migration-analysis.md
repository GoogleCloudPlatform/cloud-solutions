# AWS S3 bucket migration analysis: aws-s3-migration-analysis

## AWS S3 bucket migration analysis summary

### **✦ Executive Summary: `mmb-1765935950`**

- **Region Mapping:** AWS `us-east-2` → GCP `us-east1`
- **Scale:** 0.19 GB across 30 objects.
- **Complexity:** **Medium** \- Presence of objects in GLACIER storage class
  requires retrieval before migration.
- **Storage Profile:** STANDARD (90%), GLACIER (10%).

**Optimization Opportunities:**

- **Glacier Warning:** Data is frozen. You must account for AWS Data Retrieval
  fees and 'thaw time' (minutes to hours) before transfer starts.

---

**I have mapped your source region `us-east-2` to Google Cloud `us-east1`. Would
you like to generate the creation instructions using this location?**

**User:** Yes

**How would you like to create this bucket and transfer job?**

- A. Terraform (IaC)
- B. gcloud CLI (Shell script)
- C. Console Steps (Manual UI Guide)

**User:** A

---

### **A. Terraform (IaC)**

**✦ PREREQUISITE: AWS Source Configuration** Before executing the commands
below, you must configure your AWS IAM permissions and credentials.
**Documentation:**
[Configure access to a source: Amazon S3](https://docs.cloud.google.com/storage-transfer/docs/source-amazon-s3)

Terraform

```hcl
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "5.34.0"
    }
  }
}

provider "google" {
  project = var.project_id
}

variable "project_id" {
  description = "The GCP project ID."
  type        = string
}

variable "aws_s3_bucket" {
  description = "The source AWS S3 bucket name."
  type        = string
  default     = "mmb-1765935950"
}

variable "aws_access_key" {
  description = "AWS access key ID."
  type        = string
  sensitive   = true
}

variable "aws_secret_key" {
  description = "AWS secret access key."
  type        = string
  sensitive   = true
}

data "google_storage_transfer_project_service_account" "default" {
  project = var.project_id
}

# --- Target Bucket ---
resource "google_storage_bucket" "migrated_bucket" {
  name                        = "${var.aws_s3_bucket}-migrated"
  location                    = "US-EAST1" # Mapped from AWS source region us-east-2
  project                     = var.project_id
  uniform_bucket_level_access = true

  # Mapped from GLACIER storage class
  autoclass {
    enabled = true
  }
}

resource "google_storage_bucket_iam_member" "s3-backup-bucket" {
  bucket     = google_storage_bucket.migrated_bucket.name
  role       = "roles/storage.admin"
  member     = "serviceAccount:${data.google_storage_transfer_project_service_account.default.email}"
  depends_on = [google_storage_bucket.migrated_bucket]
}

# --- Transfer Job (Batch/Run Once) ---
resource "google_storage_transfer_job" "s3-migration-job" {
  description = "Migration of ${var.aws_s3_bucket}"
  project     = var.project_id

  transfer_spec {
    aws_s3_data_source {
      bucket_name = var.aws_s3_bucket
      aws_access_key {
        access_key_id     = var.aws_access_key
        secret_access_key = var.aws_secret_key
      }
    }
    gcs_data_sink {
      bucket_name = google_storage_bucket.migrated_bucket.name
    }
    transfer_options {
      delete_objects_unique_in_sink = false
    }
  }

  schedule {
    schedule_start_date {
      year  = 2025
      month = 12
      day   = 18
    }
  }

  logging_config {
    log_actions       = ["COPY", "DELETE"]
    log_action_states = ["SUCCEEDED", "FAILED"]
  }

  depends_on = [google_storage_bucket_iam_member.s3-backup-bucket]
}
```

**Note:** Please verify all commands and configurations before executing them in
your production environment.

**Next Step:** Would you like me to write this Terraform configuration to a file
named `main.tf`?

---

**User:** B

### **B. gcloud CLI (Shell script)**

**✦ PREREQUISITE: AWS Source Configuration** Before executing the commands
below, you must configure your AWS IAM permissions and credentials.
**Documentation:**
[Configure access to a source: Amazon S3](https://docs.cloud.google.com/storage-transfer/docs/source-amazon-s3)

```bash
# 1. Set environment variables
export PROJECT_ID="your-gcp-project-id"
export AWS_SOURCE_BUCKET_NAME="mmb-1765935950"
export GCS_BUCKET_NAME="${AWS_SOURCE_BUCKET_NAME}-migrated"

# It is recommended to create a dedicated JSON file for your AWS credentials
# For example, create a file named 'aws-creds.json' with this content:
# {
#   "aws_access_key": {
#     "access_key_id": "YOUR_AWS_ACCESS_KEY_ID",
#     "secret_access_key": "YOUR_AWS_SECRET_ACCESS_KEY"
#   }
# }
export AWS_CREDS_FILE="path/to/your/aws-creds.json"

# 2. Create the GCS Bucket
gcloud storage buckets create "gs://${GCS_BUCKET_NAME}" \
  --project="${PROJECT_ID}" \
  --location="US-EAST1" \
  --uniform-bucket-level-access \
  --enable-autoclass

# 3. Create the Transfer Job (Batch Mode)
gcloud transfer jobs create \
  "s3://${AWS_SOURCE_BUCKET_NAME}" "gs://${GCS_BUCKET_NAME}" \
  --project="${PROJECT_ID}" \
  --source-creds-file="${AWS_CREDS_FILE}" \
  --name="migration-job-${AWS_SOURCE_BUCKET_NAME}" \
  --description="Migrate ${AWS_SOURCE_BUCKET_NAME} to GCS" \
  --overwrite-when=different \
  --schedule-once
```

**Note:** Please verify all commands and configurations before executing them in
your production environment.

**Next Step:** Would you like me to write these commands to a shell script file
named `migrate.sh`?

---

**User:** C

### **C. Console Steps (Manual UI Guide)**

**✦ PREREQUISITE: AWS Source Configuration** Before executing the commands
below, you must configure your AWS IAM permissions and credentials.
**Documentation:**
[Configure access to a source: Amazon S3](https://docs.cloud.google.com/storage-transfer/docs/source-amazon-s3)

#### **Step 1: Create Destination Bucket**

1.  Go to **Cloud Storage** \> **Buckets** \> **Create**.
1.  **Name**: Enter `mmb-1765935950-migrated`.
1.  **Location**: Select **US-EAST1**.
1.  **Storage Class**: Select **Autoclass** (Mapped from Glacier usage).
1.  Click **Create**.

#### **Step 2: Create Transfer Job**

1.  Go to the **Storage Transfer Service** page.
1.  Click **Create transfer job**.
1.  **Source type**: Select **Amazon S3**.
1.  **Destination type**: Select **Google Cloud Storage**.
1.  **Scheduling mode**: Select **Batch transfers** (Run once).
1.  **Source Settings**:

- **Bucket name**: Enter `mmb-1765935950`.
- **Authentication**: Enter **Access Key ID** and **Secret Access Key**.

1.  **Destination Settings**:

- **Bucket**: Browse/Select the bucket created in Step 1\.

1.  Click **Create**.

**Note:** Please verify all commands and configurations before executing them in
your production environment.
