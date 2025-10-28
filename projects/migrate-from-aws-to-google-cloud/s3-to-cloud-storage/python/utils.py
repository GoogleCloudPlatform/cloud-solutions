# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""This module provides utility functions for interacting with AWS S3."""

import logging
import os

import boto3
import pandas as pd
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def get_report_file_path():
    """
    Retrieves the file path for reports from the REPORT_FILE_PATH environment
    variable.

    If the environment variable is not set, the current directory is used.
    If the specified directory does not exist, a message is printed.
    """
    file_path = os.environ.get("REPORT_FILE_PATH")
    if file_path:
        if not os.path.exists(file_path):
            logging.warning("The directory '%s' does not exist.", file_path)
        return file_path
    return os.getcwd()


def get_bucket_inventory(save_csv=False):
    """
    Retrieves a detailed inventory of all S3 buckets and returns them as a
    pandas DataFrame.
    """
    s3_client = boto3.client("s3")
    try:
        response = s3_client.list_buckets()
        buckets = []
        for bucket in response.get("Buckets", []):
            bucket_name = bucket["Name"]
            bucket_info = {
                "Bucket Name": bucket_name,
                "Creation Date": bucket["CreationDate"],
            }

            # Get bucket location
            try:
                location = s3_client.get_bucket_location(Bucket=bucket_name)
                bucket_info["Region"] = (
                    location.get("LocationConstraint") or "us-east-1"
                )
            except ClientError:
                bucket_info["Region"] = "unknown"

            # Get server-side encryption
            try:
                encryption = s3_client.get_bucket_encryption(Bucket=bucket_name)
                bucket_info["Encryption"] = encryption.get(
                    "ServerSideEncryptionConfiguration", "Not Configured"
                )
            except ClientError:
                bucket_info["Encryption"] = "Not configured"

            # Get bucket policy
            try:
                policy = s3_client.get_bucket_policy(Bucket=bucket_name)
                bucket_info["Policy"] = policy.get("Policy", "No Policy")
            except ClientError:
                bucket_info["Policy"] = "Not configured"

            # Get public access block
            try:
                public_access = s3_client.get_public_access_block(
                    Bucket=bucket_name
                )
                bucket_info["Public Access Block"] = public_access.get(
                    "PublicAccessBlockConfiguration", "Not Configured"
                )
            except ClientError:
                bucket_info["Public Access Block"] = "Not Configured"

            # Get bucket tagging
            try:
                tagging = s3_client.get_bucket_tagging(Bucket=bucket_name)
                bucket_info["Tags"] = tagging.get("TagSet", "No Tags")
            except ClientError:
                bucket_info["Tags"] = "Not configured"

            # Get object lock configuration
            try:
                object_lock = s3_client.get_object_lock_configuration(
                    Bucket=bucket_name
                )
                bucket_info["Object Lock"] = object_lock.get(
                    "ObjectLockConfiguration", "Not Configured"
                )
            except ClientError:
                bucket_info["Object Lock"] = "Not Configured"

            # Get requester pays configuration
            try:
                request_payment = s3_client.get_bucket_request_payment(
                    Bucket=bucket_name
                )
                bucket_info["Requester Pays"] = request_payment.get(
                    "Payer", "BucketOwner"
                )
            except ClientError:
                bucket_info["Requester Pays"] = "Not configured"

            # Get versioning configuration
            try:
                versioning = s3_client.get_bucket_versioning(Bucket=bucket_name)
                bucket_info["Versioning"] = versioning.get("Status", "Disabled")
            except ClientError:
                bucket_info["Versioning"] = "Not configured"

            # Get intelligent tiering configuration
            try:
                tiering_configs = (
                    s3_client.list_bucket_intelligent_tiering_configurations(
                        Bucket=bucket_name
                    ).get("IntelligentTieringConfigurationList", [])
                )
                if tiering_configs:
                    bucket_info["Intelligent Tiering"] = "Enabled"
                else:
                    bucket_info["Intelligent Tiering"] = "Disabled"
            except ClientError:
                bucket_info["Intelligent Tiering"] = "Not configured"

            # Get replication configuration
            try:
                replication = s3_client.get_bucket_replication(
                    Bucket=bucket_name
                )
                bucket_info["Replication"] = replication.get(
                    "ReplicationConfiguration", "Not Configured"
                )
            except ClientError:
                bucket_info["Replication"] = "Not Configured"

            # Get lifecycle configuration
            try:
                lifecycle = s3_client.get_bucket_lifecycle_configuration(
                    Bucket=bucket_name
                )
                bucket_info["Lifecycle"] = lifecycle.get("Rules", "No Rules")
            except ClientError:
                bucket_info["Lifecycle"] = "Not Configured"

            buckets.append(bucket_info)
        df = pd.DataFrame(buckets)
        if save_csv:
            file_path = get_report_file_path()
            df.to_csv(
                os.path.join(file_path, "bucket_inventory.csv"), index=False
            )
            logging.info(
                "Bucket inventory saved to %s",
                os.path.join(file_path, "bucket_inventory.csv"),
            )
        return df
    except ClientError as e:
        logging.error("Error listing buckets: %s", e)
        return pd.DataFrame()


def get_object_inventory(bucket_name, save_csv=False):
    """
    Retrieves a detailed list of all objects in a given S3 bucket and
    returns them as a pandas DataFrame.
    """
    s3_client = boto3.client("s3")
    objects = []
    try:
        # Handling versioning
        try:
            versioning_status = s3_client.get_bucket_versioning(
                Bucket=bucket_name
            ).get("Status")
        except ClientError:
            versioning_status = "Disabled"

        if versioning_status == "Enabled":
            paginator = s3_client.get_paginator("list_object_versions")
            page_iterator = paginator.paginate(Bucket=bucket_name)
            for page in page_iterator:
                for version in page.get("Versions", []):
                    obj_info = get_object_details(
                        s3_client,
                        bucket_name,
                        version["Key"],
                        version_id=version["VersionId"],
                    )
                    objects.append(obj_info)
        else:
            paginator = s3_client.get_paginator("list_objects_v2")
            page_iterator = paginator.paginate(Bucket=bucket_name)
            for page in page_iterator:
                for obj in page.get("Contents", []):
                    obj_info = get_object_details(
                        s3_client, bucket_name, obj["Key"]
                    )
                    objects.append(obj_info)

        df = pd.DataFrame(objects)
        if save_csv:
            file_path = get_report_file_path()
            df.to_csv(
                os.path.join(file_path, f"object_inventory_{bucket_name}.csv"),
                index=False,
            )
            logging.info(
                "Object inventory for bucket %s saved to %s",
                bucket_name,
                os.path.join(file_path, f"object_inventory_{bucket_name}.csv"),
            )
        return df
    except ClientError as e:
        logging.error("Error listing objects in bucket %s: %s", bucket_name, e)
        return pd.DataFrame()


def get_object_details(s3_client, bucket_name, key, version_id=None):
    """
    Helper function to get detailed information for a single object.
    """
    obj_info = {"Key": key}
    try:
        head_args = {"Bucket": bucket_name, "Key": key}
        if version_id:
            head_args["VersionId"] = version_id
            obj_info["VersionId"] = version_id

        head = s3_client.head_object(**head_args)
        obj_info["Size"] = head.get("ContentLength")
        obj_info["Last Modified"] = head.get("LastModified")
        obj_info["Metadata"] = head.get("Metadata", {})
        obj_info["Storage Class"] = head.get("StorageClass", "STANDARD")

        # Get object tags
        try:
            tags = s3_client.get_object_tagging(**head_args)
            obj_info["Tags"] = tags.get("TagSet", [])
        except ClientError:
            obj_info["Tags"] = "Not configured"

    except ClientError as e:
        logging.error("Could not get details for object %s: %s", key, e)
    return obj_info
