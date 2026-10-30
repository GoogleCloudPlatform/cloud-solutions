# Environment sandbox pre-flight validation

Before executing any Python scripts or orchestrating the migration, you **must**
sequentially verify and initialize the local environment:

## Pre-requisite step 1: Virtual environment and pip enforcement

1.  Verify that `python3` (>=3.10) is available on the host workstation.
1.  Initialize or activate the localized `venv` (located at `scripts/.venv`
    relative to the skill root directory).
1.  **Mandatory Pip Enforcement Logic:**
    - You **must** explicitly call the bootstrapping command:
      `python3 -m ensurepip --default-pip` directly against the environment to
      guarantee a pip binary exists.
1.  Install dependencies using the virtual environment's pip binary:

    ```bash
    scripts/.venv/bin/pip install -r scripts/requirements.txt --require-hashes
    ```

    All Python execution must happen exclusively using this virtual environment
    binary invocation.

## Pre-requisite step 2: Host tools and kubectl connection

1.  Check for local presence of `gcloud` (>=480.0.0) and `kubectl` (>=1.33).
1.  Verify the active kubectl context maps to the target Google Kubernetes
    Engine (GKE) cluster specified in `platform-handoff.json`.
1.  Verify accessibility to the target Google Cloud project and target GKE
    clusters using `gcloud`.

## Pre-requisite step 3: Handoff artifacts and manifest validation

The validation script automatically performs the following validation checks:

1.  Verifies the presence of:
    - **Required Input Files:**
        - `platform-handoff.json` (contains GKE landing zone details).
        - `image-map.json` (contains container image registry mappings).
        - `workload-handoff.json` (for cluster-level scope) OR
          `workload-handoff-namespace.json` (for namespace-level scope).
        - `identity-map.json` (maps Kubernetes ServiceAccounts to Google Service
          Accounts).
        - `storage-map.json` (maps StorageClasses).
        - `network-map.json` (maps ingress classes, domains, certificates, and
          subnets).
        - `observability-map.json` (maps Prometheus scrapers).
        - Path to raw EKS manifests/YAMLs (if provided locally).
1.  Confirms these files conform to their respective JSON schemas.
1.  Verifies that all EKS workload image references have valid target mapping
    entries in `image-map.json` and are present in the target Artifact Registry.
1.  Verifies that the raw EKS manifests contain resource definitions matching
    all workloads listed in the handoff.

> [!TIP]
>
> For offline verification or mock testing (where target Google Cloud
> project/clusters and Artifact Registry targets do not exist yet), run the
> validation script with the `--skip-cloud-checks` flag.

## Pre-requisite step 4: Stop execution here

1.  **Mandatory Hold:** Do not proceed to task execution or migration phase
    mapping before completing the validation check steps above.
1.  Present a status summary of the verified environment to the console and
    explicitly **ask the user for approval to proceed to Phase 1: Discover**.
