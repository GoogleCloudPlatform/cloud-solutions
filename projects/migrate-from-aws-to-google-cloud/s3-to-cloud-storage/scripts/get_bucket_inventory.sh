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

if [ -z "$1" ]; then
  echo "Usage: $0 <bucket-name>"
  exit 1
fi

BUCKET_NAME=$1
OUTPUT_FILE="${BUCKET_NAME}_inventory.csv"

# Function to safely get bucket config
get_bucket_config() {
  local cmd="$1"
  local result
  # Run the command and capture output inside the if condition
  if result=$(eval "$cmd" 2>/dev/null); then
    echo "$result" | jq -c '.'
  else
    echo "Not Configured"
  fi
}

echo "Gathering Bucket Configuration for $BUCKET_NAME..."

# Fetch Bucket Level Configs
CREATION_DATE=$(aws s3api list-buckets --query "Buckets[?Name=='$BUCKET_NAME'].CreationDate" --output text)
REGION=$(aws s3api get-bucket-location --bucket "$BUCKET_NAME" --output text)
ENCRYPTION=$(get_bucket_config "aws s3api get-bucket-encryption --bucket $BUCKET_NAME")
POLICY=$(get_bucket_config "aws s3api get-bucket-policy --bucket $BUCKET_NAME --output text")
PAB=$(get_bucket_config "aws s3api get-public-access-block --bucket $BUCKET_NAME")
TAGS=$(get_bucket_config "aws s3api get-bucket-tagging --bucket $BUCKET_NAME")
OBJ_LOCK=$(get_bucket_config "aws s3api get-object-lock-configuration --bucket $BUCKET_NAME")
REQ_PAYS=$(get_bucket_config "aws s3api get-bucket-request-payment --bucket $BUCKET_NAME")
VERSIONING=$(get_bucket_config "aws s3api get-bucket-versioning --bucket $BUCKET_NAME")
INT_TIER=$(get_bucket_config "aws s3api get-bucket-intelligent-tiering-configuration --bucket $BUCKET_NAME")
REPLICATION=$(get_bucket_config "aws s3api get-bucket-replication --bucket $BUCKET_NAME")
LIFECYCLE=$(get_bucket_config "aws s3api get-bucket-lifecycle-configuration --bucket $BUCKET_NAME")

# Write CSV Header
echo "Bucket Name,Creation Date,Region,Encryption,Policy,Public Access Block,Tags,Object Lock,Requester Pays,Versioning,Intelligent Tiering,Replication,Lifecycle,Key,VersionId,Size,Last Modified,Metadata,Storage Class,Tags" >"$OUTPUT_FILE"

echo "Listing objects..."

escape_csv() {
  local input="$1"
  echo "${input//\"/\"\"}"
}

# Loop through objects
aws s3api list-object-versions --bucket "$BUCKET_NAME" --output json | jq -c '.Versions[]' | while read -r obj; do
  KEY=$(echo "$obj" | jq -r '.Key')
  VERSION_ID=$(echo "$obj" | jq -r '.VersionId // "null"')
  SIZE=$(echo "$obj" | jq -r '.Size')
  LAST_MOD=$(echo "$obj" | jq -r '.LastModified')
  STORAGE_CLASS=$(echo "$obj" | jq -r '.StorageClass')

  METADATA_JSON=$(aws s3api head-object --bucket "$BUCKET_NAME" --key "$KEY" --version-id "$VERSION_ID" 2>/dev/null | jq -c '.Metadata' || echo "{}")
  OBJ_TAGS_JSON=$(aws s3api get-object-tagging --bucket "$BUCKET_NAME" --key "$KEY" --version-id "$VERSION_ID" 2>/dev/null | jq -c '.TagSet' || echo "[]")

  echo "\"$BUCKET_NAME\",\"$CREATION_DATE\",\"$REGION\",\"$(escape_csv "$ENCRYPTION")\",\"$(escape_csv "$POLICY")\",\"$(escape_csv "$PAB")\",\"$(escape_csv "$TAGS")\",\"$(escape_csv "$OBJ_LOCK")\",\"$(escape_csv "$REQ_PAYS")\",\"$(escape_csv "$VERSIONING")\",\"$(escape_csv "$INT_TIER")\",\"$(escape_csv "$REPLICATION")\",\"$(escape_csv "$LIFECYCLE")\",\"$KEY\",\"$VERSION_ID\",\"$SIZE\",\"$LAST_MOD\",\"$(escape_csv "$METADATA_JSON")\",\"$STORAGE_CLASS\",\"$(escape_csv "$OBJ_TAGS_JSON")\"" >>"$OUTPUT_FILE"
done

echo "Report saved to $OUTPUT_FILE"
