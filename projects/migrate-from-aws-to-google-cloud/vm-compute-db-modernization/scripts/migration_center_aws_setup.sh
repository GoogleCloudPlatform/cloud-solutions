#!/bin/bash
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# In-repo Cloud Build deployment for the Web Application (GCP Target).
# cloud-solutions/not-tracked-v0.0.0

set -o errexit
set -o nounset
set -o pipefail

export SECRET_ID="aws-discovery-secret"
export SA_NAME="aws-discovery-sa"
export SECRET_ID="aws-discovery-secret"
export SA_EMAIL="${SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
export SECRET_FULL_NAME="projects/${GCP_PROJECT_ID}/secrets/${SECRET_ID}"

gcloud config set project "$GCP_PROJECT_ID"
# ---------------------------------------------------

echo "--- Starting AWS Discovery Setup for Migration Center ---"
echo "Project ID: ${GCP_PROJECT_ID}"
echo "Service Account: ${SA_EMAIL}"
echo "Secret ID: ${SECRET_ID}"
echo "------------------------------------------------------"

# 1. ENABLE REQUIRED APIs (Skipping existence check here as 'gcloud services enable' is idempotent)
echo "1. Enabling required APIs (Core Migration, Networking, Compute, and Database services)..."
gcloud services enable migrationcenter.googleapis.com \
  cloudresourcemanager.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  datamigration.googleapis.com \
  sqladmin.googleapis.com \
  compute.googleapis.com \
  vmmigration.googleapis.com \
  networkmanagement.googleapis.com \
  servicenetworking.googleapis.com --project="${GCP_PROJECT_ID}" || {
  echo "ERROR: Failed to enable APIs."
  exit 1
}
echo "   APIs enabled successfully."

# 2. CREATE SERVICE ACCOUNT (WITH EXISTENCE CHECK)
echo "2. Creating Service Account: ${SA_NAME}..."
if gcloud iam service-accounts describe "${SA_EMAIL}" --project="${GCP_PROJECT_ID}" &>/dev/null; then
  echo "   Service Account already exists: ${SA_EMAIL}. Skipping creation."
else
  gcloud iam service-accounts create "${SA_NAME}" \
    --display-name="Migration Center AWS Discovery SA" \
    --project="${GCP_PROJECT_ID}" || {
    echo "ERROR: Failed to create Service Account."
    exit 1
  }
  echo "   Service Account created: ${SA_EMAIL}"

  echo "   Waiting 15 seconds for IAM identity propagation..."
  sleep 15
fi

# 3. CREATE SECRET (FROM VARIABLE - WITH EXISTENCE CHECK AND CORRECTED COMMAND)
echo "3. Creating Secret Manager secret '${SECRET_ID}' and adding AWS Secret Key from variable..."

echo "3. Creating Secret Manager secret '${SECRET_ID}' and adding AWS Secret Key from variable..."

# Check if the secret already exists
if ! gcloud secrets describe "${SECRET_ID}" --project="${GCP_PROJECT_ID}" &>/dev/null; then
  echo "Secret '${SECRET_ID}' does not exist. Creating it now..."

  # --- STEP 1: CREATE THE EMPTY SECRET (THE CONTAINER) ---
  gcloud secrets create "${SECRET_ID}" \
    --project="${GCP_PROJECT_ID}" \
    --replication-policy="automatic" || {
    echo "ERROR: Failed to create secret container."
    exit 1
  }

  # --- STEP 2: ADD THE DATA (THE VERSION) ---
  printf "%s" "${AWS_SECRET_ACCESS_KEY}" | gcloud secrets versions add "${SECRET_ID}" \
    --project="${GCP_PROJECT_ID}" \
    --data-file=- || {
    echo "ERROR: Failed to add secret version."
    exit 1
  }

  echo "   Secret created and version added: ${SECRET_ID}"
else
  echo "   Secret '${SECRET_ID}' already exists. Skipping secret creation."
fi

# 4. GRANT ROLES (WITH IDEMPOTENT CHECKS)
echo "4. Granting required IAM roles to Service Account (Idempotent)..."

# Grant Migration Center Admin Role (Project Level)
MIGRATION_ROLE="roles/migrationcenter.admin"
MEMBER="serviceAccount:${SA_EMAIL}"
echo "   - Granting ${MIGRATION_ROLE}..."
gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \
  --member="${MEMBER}" \
  --role="${MIGRATION_ROLE}" \
  --condition=None \
  --quiet --no-user-output-enabled # command is idempotent, no need for complex check

# Grant Secret Manager Secret Accessor Role (Secret Level)
SECRET_ACCESSOR_ROLE="roles/secretmanager.secretAccessor"
echo "   - Granting ${SECRET_ACCESSOR_ROLE} on secret '${SECRET_ID}'..."
gcloud secrets add-iam-policy-binding "${SECRET_ID}" \
  --member="${MEMBER}" \
  --role="${SECRET_ACCESSOR_ROLE}" \
  --condition=None \
  --quiet --no-user-output-enabled # command is idempotent, no need for complex check

echo "   All required permissions have been granted."

echo "--- Setup Complete ---"
echo "You can now proceed to Google Cloud Migration Center to set up the AWS discovery source."
echo "Use the AWS Access Key ID and the Service Account: ${SA_EMAIL}"
