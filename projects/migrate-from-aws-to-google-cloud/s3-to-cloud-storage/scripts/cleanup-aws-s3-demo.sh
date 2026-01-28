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

set -o errexit
set -o nounset
set -o pipefail

# Usage
if [ -z "$1" ]; then
  echo "Usage: $0 <bucket-name>"
  echo ""
  echo "Example:"
  echo "  $0 s3-migration-demo-1234567890"
  echo ""
  echo "To list buckets:"
  echo "  aws s3 ls"
  exit 1
fi

BUCKET_NAME=$1

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║          AWS S3 Migration Demo Cleanup                     ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check if bucket exists
echo "[INFO] Checking bucket: $BUCKET_NAME"

if ! aws s3api head-bucket --bucket "$BUCKET_NAME" 2>/dev/null; then
  echo "[ERROR] Bucket does not exist or is Not configured"
  exit 1
fi

echo "[SUCCESS] Bucket found"

# Count objects
OBJECT_COUNT=$(aws s3 ls "s3://${BUCKET_NAME}" --recursive | wc -l)
echo "[INFO] Found $OBJECT_COUNT objects in bucket"

# Confirm deletion
echo ""
echo "[WARNING] This will DELETE the bucket and all $OBJECT_COUNT objects!"
echo "[WARNING] Bucket: $BUCKET_NAME"
echo ""
read -p "Are you sure? Type 'DELETE' to confirm: " -r
echo ""

if [ "$REPLY" != "DELETE" ]; then
  echo "[INFO] Cleanup cancelled"
  exit 0
fi

# Delete all objects and versions
echo "[INFO] Deleting all objects and versions..."

# Delete object versions
if aws s3api get-bucket-versioning --bucket "$BUCKET_NAME" | grep -q "Enabled"; then
  echo "[INFO] Versioning is enabled, deleting all versions..."

  aws s3api delete-objects --bucket "$BUCKET_NAME" \
    --delete "$(aws s3api list-object-versions --bucket "$BUCKET_NAME" --output json \
      --query '{Objects: Versions[].{Key:Key,VersionId:VersionId}}')" 2>/dev/null || true

  aws s3api delete-objects --bucket "$BUCKET_NAME" \
    --delete "$(aws s3api list-object-versions --bucket "$BUCKET_NAME" --output json \
      --query '{Objects: DeleteMarkers[].{Key:Key,VersionId:VersionId}}')" 2>/dev/null || true
fi

# Delete regular objects
aws s3 rm "s3://${BUCKET_NAME}" --recursive --quiet

echo "[SUCCESS] Objects deleted"

# Delete bucket
echo "[INFO] Deleting bucket..."
aws s3 rb "s3://${BUCKET_NAME}"

echo "[SUCCESS] Bucket deleted"

# Cleanup local files
echo "[INFO] Cleaning up local files..."
rm -f "$HOME"/s3-migration-demo-*.txt 2>/dev/null || true
echo "[SUCCESS] Local files cleaned"

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                 CLEANUP COMPLETE                           ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "[SUCCESS] Bucket $BUCKET_NAME has been deleted"
echo ""
