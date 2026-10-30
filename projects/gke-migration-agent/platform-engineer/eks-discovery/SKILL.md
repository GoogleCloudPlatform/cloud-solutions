---
name: eks-discovery
description: >-
  Inventories an Amazon EKS estate end-to-end. Use when starting an Amazon EKS to Google Kubernetes Engine (GKE) migration, or when generating a pre-migration inventory. Don't use for general AWS account discovery or non-Amazon EKS workloads.
---

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

# Amazon EKS discovery

<!--
  Disabling markdownlint MD029 to provide explicit ordering to avoid
  confusing the LLM.
-->
<!-- markdownlint-disable MD029 -->

<!--
    Disabling markdownlint MD030 to allow the list overflowing to numbers
    >=10.
-->
<!-- markdownlint-disable MD030 -->

You are an Amazon EKS inventory specialist. Read the source Amazon Web Services
(AWS) environment with read-only credentials. Produce a complete,
machine-readable inventory of everything a migration requires. You write nothing
back to AWS.

## Purpose

Provide a complete, structured ground truth of the target AWS/Amazon EKS
environment. Every downstream skill consumes the artifacts this process
generates.

### Architecture

This skill uses a hybrid approach to script languages:

- **Python** serves as the core discovery engine. It queries the AWS and
  Kubernetes APIs for structured cluster and node data.
- **Bash scripts** orchestrate the pipeline. They execute supplementary
  `kubectl` and AWS Command Line Interface (CLI) queries to fetch raw YAML
  manifests, Amazon EKS Addons, and Custom Resource Definitions (CRDs) not
  covered by the Python tool.

## When to use this skill

Use this skill when preparing for an Amazon EKS to GKE migration. Trigger this
skill when:

- The orchestrator invokes this in Phase 1.
- The user requests a pre-migration inventory of their Amazon EKS clusters.

**Constraints:**

- Do not use this skill for general AWS account discovery.
- Do not use this skill for non-Amazon EKS workloads.

## Prerequisites

- Read-only AWS credentials configured for the `eks-migration-readonly` profile
  in `~/.aws/credentials`.
- Install `aws` CLI v2, `kubectl`, `jq`, `yq`, and Python 3.9+.

### Missing prerequisites

If you cannot meet any prerequisite, stop immediately. Tell the user the exact
missing requirement and instruct them to resolve it.

## Error handling and resilience

Every error, failure, or anomaly encountered during execution **must** be
recorded in `01-discovery/escalations.md`. Handle issues according to the
following rules:

- **Fatal Errors**: Halt on IAM or runtime crashes. Summarize `stderr` for the
  user.
- **Graceful Degradation**: Use fallbacks for external APIs. Record non-critical
  failures in an escalation file and proceed.
- **Extraction Logs**: The `extract_manifests.sh` script logs API and
  authentication failures to `01-discovery/raw/extraction_errors.log`. Always
  review this log and incorporate its contents into `escalations.md`.
- **Service Mesh**: A service mesh, such as Istio, Linkerd, Consul, AWS App
  Mesh, or Kuma, is a migration blocker, not a script failure. Do not stop
  discovery when you find one. Detect it in Step 4, record it under a
  `## Migration blockers` heading in `01-discovery/escalations.md`, and continue
  producing the full inventory so downstream skills can grade it.
- **Architectural Risks**: Do not treat risks, such as `hostNetwork: true`, as
  script failures.

## Procedure

### Step 1 — Verify AWS credentials

**CRITICAL:** You must use the `eks-migration-readonly` AWS CLI profile for all
operations. Do not prompt the user for credentials.

1.  Export `AWS_PROFILE="eks-migration-readonly"`.
2.  Run `aws sts get-caller-identity` to verify the profile exists.
3.  Run `aws eks list-clusters` to verify read-only access.
4.  If any command fails, stop immediately. Tell the user they must configure
    the `eks-migration-readonly` profile according to the instructions in the
    project `README.md`.
5.  Verify the installation of other required tools (`kubectl`, `jq`, `yq`, and
    `python3`).

```bash
export AWS_PROFILE="eks-migration-readonly"
aws sts get-caller-identity
aws eks list-clusters
kubectl version --client
jq --version
yq --version
python3 --version
```

### Step 2 — Cluster-level facts

Extract all cluster-level facts using the upstream
[`k8s-discovery` tool](https://github.com/GoogleCloudPlatform/professional-services/blob/main/tools/k8s-discovery/README.md).
This external tool extracts cluster architecture, node pools, and add-on data
directly from the AWS API.

Do the following:

1.  Clone the Kubernetes discovery tool, run it against the target region, and
    verify the output:

    ```bash
    # Sparse checkout the Kubernetes discovery tool
    git clone --depth 1 --filter=blob:none --sparse https://github.com/GoogleCloudPlatform/professional-services.git
    git -C professional-services sparse-checkout set tools/k8s-discovery

    # Create venv and install dependencies
    python3 -m venv professional-services/tools/k8s-discovery/venv
    source professional-services/tools/k8s-discovery/venv/bin/activate
    python3 -m pip install --index-url https://pypi.org/simple -r professional-services/tools/k8s-discovery/requirements.txt --require-hashes

    # Run discovery tool
    python3 professional-services/tools/k8s-discovery/main.py aws --output-dir 01-discovery/raw

    # Move output to root and verify
    mv 01-discovery/raw/eks_data.json 01-discovery/inventory.json
    ```

2.  Verify that `01-discovery/inventory.json` and the CSVs in
    `01-discovery/raw/` were successfully generated and are not empty:

    ```bash
    ls -la 01-discovery/inventory.json
    ```

    The generated files must include:
    - `crds.csv`: Custom Resource Definitions installed in the cluster, with API
      group and scope.
    - `eks_clusters.csv`: High-level cluster summary.
    - `inventory.json`: Complete hierarchical JSON dump of the raw discovery
      data.
    - `namespaces.csv`: Namespaces with their labels and annotations.
    - `nodepools.csv`: Details about node groups.
    - `nodes.csv`: Node details including CPU/Memory capacity, Kernel version,
      OS Image.
    - `persistent_volume_claims.csv`: Storage requests and binding status.
    - `pods.csv`: Individual Pod statuses, IPs, and Node assignment.
    - `services.csv`: Network services, ClusterIPs, and Ports.
    - `workloads.csv`: Flattened list of Deployments, StatefulSets, DaemonSets
      with resource requests/limits.

    If `inventory.json` is missing or has a size of 0 bytes, document this fatal
    failure in `01-discovery/escalations.md`, stop immediately, and inform the
    user that the discovery tool failed to extract the cluster data.

### Step 3 — Workloads and identity mapping (per cluster)

You **must** execute the manifest extraction script for **every single cluster**
discovered in the `inventory.json` file. Do not stop after the first cluster.

1.  Read `inventory.json` and explicitly list out every cluster name you
    discovered so the user can verify your scope.
2.  For each cluster, extract its name and AWS region from `inventory.json`, and
    run:

    ```bash
    ./scripts/extract_manifests.sh <cluster_name> <region> [aws_profile] [output_dir]
    ```

This script dumps Kubernetes manifests separated by namespace into subfolders
(`manifests/<cluster>/<namespace>/<kind>.yaml` and cluster-scoped resources
under `manifests/<cluster>/_cluster_scoped/<kind>.yaml`), acting as a raw audit
trail. It also maps Identity and Access Management (IAM) Roles for Service
Accounts (IRSA) annotations to IAM roles.

### Step 4 — Generate structured artifacts and summary

You **must** synthesize the data from the CSV files in `01-discovery/raw/` into
the final structured artifacts yourself. When constructing these outputs, you
**must read and adhere strictly** to the corresponding schemas located in the
`assets/` directory:

1.  **Structure Workloads:** You can organize workloads in two ways. Ask the
    user for their preference if not specified:
    - **By Cluster (Default):** Read `assets/workload-handoff.schema.json` to
      structure a single `workload-handoff.json` file containing all clusters
      and their workloads.
    - **By Namespace:** Read `assets/workload-handoff-namespace.schema.json` to
      structure multiple `workload-handoff.json` files, one per namespace under
      `workload-handoffs/<cluster>/<namespace>/`. Extract these workloads
      directly from `01-discovery/raw/workloads.csv` and the raw manifests.
      **Important:** Ignore and skip all reserved Kubernetes namespaces (any
      namespace starting with `kube-`). Also omit namespaces with zero workloads
      (such as an unutilized `default` namespace containing only
      cluster-internal resources) from `workload-handoff.json`.

    When populating workload objects in `workload-handoff.json`, follow these
    strict extraction rules:
    - **`name`**: Set to the exact Kubernetes resource `metadata.name` of the
      top-level workload object (`Deployment`, `StatefulSet`, `DaemonSet`,
      `Job`, `CronJob`). Do not use container names, image names, or label
      values.
    - **`dependencies.storage.pvc_names`**: Set to the exact
      PersistentVolumeClaim `metadata.name` referenced under
      `spec.template.spec.volumes[*].persistentVolumeClaim.claimName`.
    - **`dependencies.storage.volume_claim_templates`**: Set to the exact
      PersistentVolumeClaim `metadata.name` referenced under
      `volumeClaimTemplates[*].metadata.name`.
    - **`dependencies.http_routes`**: Set to the exact Gateway API HTTPRoute
      references in `namespace/name` format targeting the workload backend.
    - **`dependencies.services`**: Set to the exact Kubernetes Service
      `metadata.name` targeting the workload via label selector matching.
    - **`dependencies.configmaps`**: Set to the exact ConfigMap `metadata.name`
      referenced in `envFrom`, `valueFrom`, or `volumes`.
    - **`observability_scrapes`**: Inspect pod template scrape annotations
      directly so that they properly link each scraped workload name to its
      corresponding GMP target in `observability-map.json` (rather than
      incorrectly associating it with `cloudwatch-agent`).
    - **`dependencies.secrets`**: Set to the exact Secret `metadata.name`
      referenced in `envFrom`, `valueFrom`, `volumes`, or `imagePullSecrets`.

2.  **Read** `assets/irsa-map.schema.md` to structure the `irsa-map.tsv` file.
3.  **Check** if `01-discovery/raw/extraction_errors.log` exists. If so, append
    its contents into `escalations.md` as a simple bulleted list. Also add any
    other anomalies (like custom CNIs) to this file as plain markdown.
4.  **Detect service mesh:** Read `references/service-mesh-detection.md`
    (relative to this skill's directory) and run its commands against
    `01-discovery/raw/`. It lists the Istio, Linkerd, Consul, AWS App Mesh, and
    Kuma signals, the cases that are not a service mesh, and the decision rules.
    Do not stop discovery when you find a service mesh. Append one entry per
    affected cluster and provider under a `## Migration blockers` heading in
    `escalations.md`, record non-mesh look-alikes as anomalies, and add a bold
    **Service mesh detected** line to section 5 of `inventory-summary.md` in the
    next step.

5.  **Read** `assets/inventory-summary.schema.md` to structure the
    `inventory-summary.md` file. It must provide a comprehensive view of the
    environment to evaluate migration complexity based on the extracted data.

The final directory structure you must produce is:

```text
01-discovery/
├── inventory.json             # Machine-readable, the input for downstream skills.
├── inventory-summary.md       # Human-readable: clusters, workload counts, key risks.
├── raw/                       # Every file from the procedure above, untouched.
├── irsa-map.tsv               # IRSA SA → IAM role index.
├── escalations.md             # Anything weird, such as custom Container Network Interface (CNI) or hostNetwork DaemonSets.
├── workload-handoff.json      # IF organized by cluster (Default).
└── workload-handoffs/         # IF organized by namespace. Contains JSON handoff files and raw YAML manifests organized by cluster and namespace.
    └── <cluster-name>/
        └── <namespace-1>/
            ├── workload-handoff.json
            └── yaml/
                └── ...
```
