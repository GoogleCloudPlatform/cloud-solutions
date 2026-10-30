---
name: storage-translation
description: >-
  Translates Amazon Elastic Kubernetes Service (EKS) PersistentVolumeClaim (PVC)
  and StorageClass specifications into Google Kubernetes Engine (GKE) compatible
  PersistentVolume (PV) / PersistentVolumeClaim (PVC) resources and GKE StorageClasses.
  Use when remapping block-level GP2/GP3 to Persistent Disks and EFS to GKE Filestore.
  Don't use for cluster-level infrastructure provisioning or Workload Identity mapping.
---

# Storage translation

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

## Purpose

Automate the mapping and translation of Amazon Elastic Kubernetes Service (EKS)
StorageClass specifications to Google Kubernetes Engine (GKE), adapting standard
block storage to Persistent Disk classes and ReadWriteMany (RWX) file storage
(EFS) to GKE Filestore.

> [!IMPORTANT]
>
> This skill ONLY translates Kubernetes resource configurations and manifest
> specs. It DOES NOT copy, sync, or migrate underlying data stored on physical
> disks or volumes. Data migration (e.g. via VolSync, AWS DataSync, or snapshot
> transfer) must be performed out-of-band prior to or during cluster cutover.
> Inform the user of this requirement when invoking this skill.

## When to use this skill

Trigger on:

- "Translate EKS StorageClasses to GKE StorageClasses"
- "Map EKS PVCs to standard-rwo or filestore-rwx"
- "Generate GKE-compatible PersistentVolumeClaims"

## Prerequisites

- `python3` version 3.10 or later
- Install dependencies listed in `scripts/requirements.txt`:
  `pip install --require-hashes -r scripts/requirements.txt`
- Path to handoff directory containing `workload-handoff.json` (or
  `workload-handoff-namespace.json`) and `storage-map.json`
- Path to directory containing raw EKS manifests (`--raw-manifests-dir`)

## Assets & references

The following schema files under `assets/schemas/` define the JSON contracts
used by this skill:

- `storage-map.schema.json`: Schema for validating StorageClass mappings.
- `workload-handoff.schema.json`: Schema for cluster-level workload handoff
  specifications.
- `workload-handoff-namespace.schema.json`: Schema for namespace-level workload
  handoff specifications.

The following reference documents under `references/` provide translation
guidance:

- [references/storage_class_mapping.md](references/storage_class_mapping.md):
  Mappings between AWS StorageClasses and GCP StorageClasses.
- [references/provisioner_mappings.md](references/provisioner_mappings.md):
  Provisioner mappings between AWS CSI drivers and GKE CSI drivers.
- [references/pvc_migration_strategies.md](references/pvc_migration_strategies.md):
  Migration strategies for persistent volume data.

The following dependency files under `scripts/` are used by this skill:

- `scripts/requirements.in`: Input dependencies for python validation scripts.
- `scripts/requirements.txt`: Hashed dependency lockfile for python validation
  scripts.

## Procedure

### Step 1 — Validate storage mapping completeness

Verify that every PersistentVolumeClaim (PVC) referenced by active workloads in
the handoff has a target StorageClass mapping entry in `storage-map.json`:

```bash
python3 scripts/validate_storage_map.py \
  --handoff-dir "${HANDOFF_DIR:-.}" \
  --raw-manifests-dir "${RAW_MANIFESTS_DIR:-./raw-manifests}"
```

### Step 2 — Translate storage resources

While automated tools update PVC `storageClassName` properties using
`storage-map.json`, custom cluster-level StorageClass manifests must be
translated manually when custom storage configurations are required on GKE:

1.  **Translate Custom StorageClass Manifests (Cluster-Level Infrastructure):**
    - When the migration requires deploying custom GKE `StorageClass` resources
      (e.g. for specialized IOPS, performance tiers, or Filestore
      configurations), locate the source AWS `StorageClass` manifests.
    - Refer to
      [references/provisioner_mappings.md](references/provisioner_mappings.md)
      to map the AWS storage provisioner (e.g. `kubernetes.io/aws-ebs` or
      `ebs.csi.aws.com`) to the corresponding GKE CSI driver (e.g.
      `pd.csi.storage.gke.io` or `filestore.csi.storage.gke.io`).
    - Update `provisioner` and the parameter `type` accordingly.
    - Plan the persistent data replication/synchronization strategy using the
      options in
      [references/pvc_migration_strategies.md](references/pvc_migration_strategies.md).
2.  **Translate PersistentVolumeClaims (PVCs):**
    - Identify any `PersistentVolumeClaim` (PVC) resource.
    - Strip EKS/AWS-specific annotations (e.g.
      `volume.beta.kubernetes.io/storage-provisioner`).
    - Look up the PVC's current `storageClassName` in `storage-map.json` and
      remap it to the GKE target StorageClass name.
    - If `storageClassName` is omitted or empty on a PVC, treat it as using the
      cluster's default StorageClass. Remap omitted or empty StorageClasses to
      GKE's default `standard-rwo` unless specified otherwise in
      `storage-map.json`.
3.  **GKE Autopilot and Storage Constraint Validation:**
    - Consult the **GKE volume constraints and minimum sizes** section in
      [references/storage_class_mapping.md](references/storage_class_mapping.md)
      and
      [references/pvc_migration_strategies.md](references/pvc_migration_strategies.md)
      to verify target GKE storage constraints.
    - Check dynamic PVC storage requests against GKE driver thresholds detailed
      in `references/storage_class_mapping.md` (e.g. Filestore requires at least
      1TiB for Basic HDD/SSD, while PD-standard/SSD requires at least 1GiB; see
      official Google Cloud
      [Persistent Disk CSI](https://cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/pd-csi)
      and
      [Filestore CSI](https://cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/filestore-csi-driver)
      documentation).
    - Add `volumeBindingMode: WaitForFirstConsumer` to custom StorageClasses if
      generated.
