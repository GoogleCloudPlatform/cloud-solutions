#!/bin/bash
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# No Google Cloud API calls in this script. Accounting for that
# cloud-solutions/not-tracked-v0.0.0

set -o errexit
set -o nounset
set -o pipefail

# Check prerequisites
check_prerequisites() {
  echo "[INFO] Checking prerequisites..."

  if ! command -v aws &>/dev/null; then
    echo "[ERROR] AWS CLI is not installed. Please install it first."
    exit 1
  fi

  if ! aws sts get-caller-identity &>/dev/null; then
    echo "[ERROR] AWS CLI is not configured. Please run 'aws configure' first."
    exit 1
  fi

  echo "[SUCCESS] Prerequisites check passed"
}

# Configuration
configure_environment() {
  echo "[INFO] Configuring environment..."

  TIMESTAMP=$(date +%s)

  REGION="${AWS_REGION:-us-east-1}"

  PROJECT_TAG="${PROJECT_TAG:-mmb}"
  COST_CENTER_TAG="${COST_CENTER_TAG:-123}"

  WORK_DIR="$HOME/s3-demo-files-${TIMESTAMP}"

  echo "[SUCCESS] Environment configured"
  echo "[INFO] Bucket Name: ${BUCKET_NAME}"
  echo "[INFO] Region: ${REGION}"
}

# Create S3 bucket
create_bucket() {
  echo "[INFO] Creating S3 bucket..."

  if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket \
      --bucket "$BUCKET_NAME" \
      --region "$REGION"
  else
    aws s3api create-bucket \
      --bucket "$BUCKET_NAME" \
      --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION"
  fi
  echo "[SUCCESS] Created bucket: ${BUCKET_NAME}"

  # Tag bucket
  aws s3api put-bucket-tagging \
    --bucket "$BUCKET_NAME" \
    --tagging "TagSet=[{Key=project,Value=${PROJECT_TAG}},{Key=cost-center,Value=${COST_CENTER_TAG}}]"
  echo "[SUCCESS] Tagged bucket"

  # Enable versioning
  aws s3api put-bucket-versioning \
    --bucket "$BUCKET_NAME" \
    --versioning-configuration Status=Enabled
  echo "[SUCCESS] Enabled versioning"
}

# Generate test files
generate_files() {
  echo "[INFO] Generating test files..."

  mkdir -p "$WORK_DIR"
  cd "$WORK_DIR"

  # Small files (1KB - 100KB)
  echo "[INFO] Generating small files (1-100KB)..."
  for i in {1..5}; do
    dd if=/dev/urandom of="small-file-${i}.bin" bs=1024 count=$((RANDOM % 100 + 1)) 2>/dev/null
  done

  # Medium files (1MB - 10MB)
  echo "[INFO] Generating medium files (1-10MB)..."
  for i in {1..5}; do
    dd if=/dev/urandom of="medium-file-${i}.bin" bs=1048576 count=$((RANDOM % 10 + 1)) 2>/dev/null
  done

  # Large files (10MB - 50MB)
  echo "[INFO] Generating large files (10-50MB)..."
  for i in {1..3}; do
    dd if=/dev/urandom of="large-file-${i}.bin" bs=1048576 count=$((RANDOM % 40 + 10)) 2>/dev/null
  done

  # Text files
  echo "[INFO] Creating text files..."
  echo "Migration demo document 1 - Project: ${PROJECT_TAG}" >document1.txt
  echo "Migration demo document 2 - Cost Center: ${COST_CENTER_TAG}" >document2.txt
  echo "Migration demo document 3 - Created: $(date)" >document3.txt

  # Create directory structure
  mkdir -p data/2024 data/2025 archives

  echo "[SUCCESS] Generated $(find . -type f | wc -l) files"
  echo "[INFO] Total size: $(du -sh . | cut -f1)"
}

# Upload files
upload_files() {
  echo "[INFO] Uploading files to S3..."

  cd "$WORK_DIR"

  # Upload root level files
  echo "[INFO] Uploading root level files..."
  for file in *.bin *.txt; do
    if [ -f "$file" ]; then
      aws s3api put-object \
        --bucket "$BUCKET_NAME" \
        --key "$file" \
        --body "$file" \
        --storage-class STANDARD \
        --tagging "project=${PROJECT_TAG}&cost-center=${COST_CENTER_TAG}" \
        --metadata "uploaded-by=migration-demo,purpose=testing,timestamp=$(date +%s)" \
        >/dev/null
      echo "[SUCCESS] Uploaded: $file"
    fi
  done

  # Organize files into folders
  echo "[INFO] Organizing files into folders..."
  mv small-file-* data/2024/ 2>/dev/null || true
  mv medium-file-* data/2025/ 2>/dev/null || true
  mv large-file-* archives/ 2>/dev/null || true

  # Upload 2024 data
  echo "[INFO] Uploading 2024 data..."
  for file in data/2024/*; do
    if [ -f "$file" ]; then
      aws s3api put-object \
        --bucket "$BUCKET_NAME" \
        --key "$file" \
        --body "$file" \
        --storage-class STANDARD \
        --tagging "project=${PROJECT_TAG}&cost-center=${COST_CENTER_TAG}&year=2024" \
        --metadata "year=2024,category=historical" \
        >/dev/null
      echo "[SUCCESS] Uploaded: $file"
    fi
  done

  # Upload 2025 data
  echo "[INFO] Uploading 2025 data..."
  for file in data/2025/*; do
    if [ -f "$file" ]; then
      aws s3api put-object \
        --bucket "$BUCKET_NAME" \
        --key "$file" \
        --body "$file" \
        --storage-class STANDARD \
        --tagging "project=${PROJECT_TAG}&cost-center=${COST_CENTER_TAG}&year=2025" \
        --metadata "year=2025,category=current" \
        >/dev/null
      echo "[SUCCESS] Uploaded: $file"
    fi
  done

  # Upload archives
  echo "[INFO] Uploading archives..."
  for file in archives/*; do
    if [ -f "$file" ]; then
      aws s3api put-object \
        --bucket "$BUCKET_NAME" \
        --key "$file" \
        --body "$file" \
        --storage-class GLACIER \
        --tagging "project=${PROJECT_TAG}&cost-center=${COST_CENTER_TAG}&type=archive" \
        --metadata "type=archive,retention=long-term" \
        >/dev/null
      echo "[SUCCESS] Uploaded: $file"
    fi
  done

  echo "[SUCCESS] All files uploaded"
  aws s3 ls "s3://${BUCKET_NAME}" --recursive --human-readable
}

# Create summary
create_summary() {
  SUMMARY_FILE="$HOME/s3-migration-demo-${TIMESTAMP}.txt"

  cat >"$SUMMARY_FILE" <<EOF
AWS S3 Migration Demo Setup
===========================
Date: $(date)

BUCKET INFORMATION
------------------
Bucket Name: ${BUCKET_NAME}
Region: ${REGION}
Tags: project=${PROJECT_TAG}, cost-center=${COST_CENTER_TAG}

NEXT STEPS
----------
  1. Extract object details for migration (CSV format):
    ./get-s3-object-details.sh ${BUCKET_NAME} csv > migration-inventory.csv

  2. Clean up when done:
    ./cleanup-s3-demo.sh ${BUCKET_NAME}

BUCKET URL
----------
https://s3.console.aws.amazon.com/s3/buckets/${BUCKET_NAME}
EOF

  echo "[SUCCESS] Summary saved: ${SUMMARY_FILE}"
  cat "$SUMMARY_FILE"
}

# Cleanup temp
cleanup_temp() {
  if [ -d "$WORK_DIR" ]; then
    rm -rf "$WORK_DIR"
  fi
}

# Main
main() {
  echo ""
  echo "╔════════════════════════════════════════════════════════════╗"
  echo "║         AWS S3 Migration Demo Setup                        ║"
  echo "╚════════════════════════════════════════════════════════════╝"
  echo ""

  check_prerequisites
  configure_environment

  echo ""
  echo "[WARNING] This will create AWS resources that incur costs."
  read -p "Continue? (yes/no): " -r
  echo ""

  if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "[INFO] Cancelled"
    exit 0
  fi

  create_bucket
  echo ""
  generate_files
  echo ""
  upload_files
  echo ""
  cleanup_temp
  echo ""
  create_summary

  echo ""
  echo "╔════════════════════════════════════════════════════════════╗"
  echo "║                    SETUP COMPLETE                          ║"
  echo "╚════════════════════════════════════════════════════════════╝"
  echo ""
  echo "[SUCCESS] Bucket created: ${BUCKET_NAME}"
  echo ""
}

main "$@"
