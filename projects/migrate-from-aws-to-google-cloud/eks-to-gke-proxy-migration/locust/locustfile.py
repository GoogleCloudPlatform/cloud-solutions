# Copyright 2026 Google LLC
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

"""Locust load test script during EKS to GKE migration."""

from locust import HttpUser, between, task


class PingUser(HttpUser):
    """Simulates a user pinging the k8s service's index and health endpoints."""

    wait_time = between(1, 3)

    @task(4)
    def index(self):
        """Pings the root endpoint of the k8s service."""
        self.client.get("/")

    @task(1)
    def health(self):
        """Pings the health check endpoint of the k8s service."""
        self.client.get("/health")
