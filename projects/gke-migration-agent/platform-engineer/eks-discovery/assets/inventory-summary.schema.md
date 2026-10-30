<!--
 Copyright 2026 Google LLC

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

      https://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
-->

# Amazon EKS to Google Kubernetes Engine (GKE) inventory summary template

This template defines the structure for the `inventory-summary.md` generated
during the Amazon EKS discovery phase. A good assessment must provide a
comprehensive view of the environment to evaluate migration complexity.

## Structure

### 1. Executive summary

- Total Amazon EKS Clusters
- Total Namespaces
- Total Workloads
- Total Node Pools / Nodes

### 2. Infrastructure footprint

- **Kubernetes Versions**: List versions in use
- **Node Provisioning**: Such as Managed Node Groups, Karpenter, or Fargate
- **Node Instance Types**: Brief summary of EC2 families used

### 3. Workload topologies

- **Stateless Workloads**: Deployments, ReplicaSets
- **Stateful Workloads**: StatefulSets, PVC usage
- **Batch Processing**: Jobs, CronJobs
- **Platform/Node Workloads**: DaemonSets

### 4. Cloud integrations and dependencies

- **Identity (IRSA)**: Summary of IAM roles attached to workloads
- **Storage**: Usage of aws-ebs-csi-driver, aws-efs-csi-driver, etc.
- **Networking/Ingress**: Usage of AWS Load Balancer Controller, external-dns,
  VPC CNI

### 5. Security and architectural risks (escalations)

- Workloads using `hostNetwork` or `hostPID`
- Privileged containers or non-standard `runtimeClassName`
- Custom CNIs or platform-level DaemonSets that may not map 1:1 to GKE Autopilot
  or Standard defaults

## Guidelines for the agent

- Extract this data entirely from the CSV files in `01-discovery/raw/` including
  `eks_clusters.csv`, `namespaces.csv`, and `workloads.csv`.
- Use bullet points for readability.
- Highlight any immediate migration blockers or high-complexity items in bold.
