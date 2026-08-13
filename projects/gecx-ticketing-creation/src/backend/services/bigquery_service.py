# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


# pylint: disable=line-too-long
"""Module containing GECX bigquery service logic."""

import os
import uuid
from datetime import datetime, timezone

from google.cloud import bigquery


class BigQueryService:
    """Service class for BigQuery operations."""

    def __init__(self):
        self._client = None
        self._project = None
        self._table_ref = None
        self.dataset_id = "cymbal_demo"
        self.table_id = "support_tickets"

    def _ensure_init(self):
        if self._client is None:
            self._project = (
                os.getenv("GCP_PROJECT_ID")
                or os.getenv("GOOGLE_CLOUD_PROJECT")
            )
            if not self._project:
                raise ValueError(
                    "GCP_PROJECT_ID or GOOGLE_CLOUD_PROJECT environment"
                    " variable is required."
                )
            self._client = bigquery.Client(project=self._project)
            self._table_ref = (
                f"{self._project}.{self.dataset_id}.{self.table_id}"
            )

    @property
    def client(self):
        self._ensure_init()
        return self._client

    @property
    def table_ref(self):
        self._ensure_init()
        return self._table_ref

    def insert_ticket(
        self, account: str, isin: str, reference_id: str, description: str
    ) -> dict:
        """
        Inserts a new support ticket row into the BigQuery table support_tickets using DML INSERT
        to bypass the streaming buffer and allow immediate UPDATE queries.
        """
        ticket_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()

        query = f"""
            INSERT INTO `{self.table_ref}` (ticket_id, account, isin, reference_id, description, status, created_at, resolution)
            VALUES (@ticket_id, @account, @isin, @reference_id, @description, @status, @created_at, @resolution)
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("ticket_id", "STRING", ticket_id),
                bigquery.ScalarQueryParameter("account", "STRING", account),
                bigquery.ScalarQueryParameter("isin", "STRING", isin),
                bigquery.ScalarQueryParameter(
                    "reference_id", "STRING", reference_id
                ),
                bigquery.ScalarQueryParameter(
                    "description", "STRING", description
                ),
                bigquery.ScalarQueryParameter("status", "STRING", "open"),
                bigquery.ScalarQueryParameter(
                    "created_at", "STRING", created_at
                ),
                bigquery.ScalarQueryParameter("resolution", "STRING", ""),
            ]
        )

        query_job = self.client.query(query, job_config=job_config)
        query_job.result()  # Wait for DML query execution to complete

        return {
            "ticket_id": ticket_id,
            "status": "open",
            "created_at": created_at,
        }

    def resolve_ticket(self, ticket_id: str, resolution_summary: str) -> None:
        """
        Updates the support ticket status to resolved and commits the resolution summary in BigQuery using DML UPDATE.
        """
        query = f"""
            UPDATE `{self.table_ref}`
            SET status = 'resolved', resolution = @resolution
            WHERE ticket_id = @ticket_id
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter(
                    "resolution", "STRING", resolution_summary
                ),
                bigquery.ScalarQueryParameter("ticket_id", "STRING", ticket_id),
            ]
        )

        query_job = self.client.query(query, job_config=job_config)
        query_job.result()  # Wait for DML update to complete
