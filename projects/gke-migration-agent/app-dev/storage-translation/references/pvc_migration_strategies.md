# Persistent Volume Claim (PVC) data migration strategies

This document details data synchronization strategies for migrating persistent
data from Amazon Elastic Kubernetes Service (EKS) PersistentVolumeClaims (PVCs)
to Google Kubernetes Engine (GKE) volumes.

## Strategy A: Velero cold backup & restore (offline)

Best for workloads that can tolerate a maintenance window.

1.  Stop the application pods on EKS (scale down replicas to 0).
1.  Take a Velero backup of the namespace including PersistentVolume (PV)
    snapshots.
1.  Perform a Velero restore on GKE using a custom `storageClass` mapping config
    to point EKS classes to GKE classes.
1.  Verify data and scale up workloads on GKE.

## Strategy B: Rsync over inter-cloud Virtual Private Network (VPN) (online synchronization)

Best for larger ReadWriteMany (RWX) file shares (Elastic File System / EFS to
Filestore) with low downtime requirements.

1.  Establish a Cloud Virtual Private Network (VPN) or Interconnect connecting
    AWS VPC and Google Cloud VPC.
1.  Deploy a temporary migration Pod (rsync agent) on GKE attached to the new
    GKE Filestore share.
1.  Deploy a similar replication Pod on EKS attached to the EFS volume.
1.  Run a background rsync job from EKS to GKE to copy the bulk of the data.
1.  Cutover phase: Scale down EKS app, run a final fast rsync pass to copy delta
    changes, switch traffic to GKE.

## Strategy C: Application-level DB replication

Best for relational and transactional databases (e.g. running MySQL/PostgreSQL
on top of PVs).

1.  Deploy a replica database on GKE.
1.  Establish network routing and set up database master-slave replication.
1.  Verify the replica has caught up.
1.  Promote the replica to master, disconnect source, and point GKE workloads to
    the local DB.

## Strategy D: Workstation-mediated synchronization via Google Cloud Storage (GCS)

Best for block storage volumes when Cloud VPN/Interconnect is not available.
Uses local workstation credentials (`aws` and `gcloud`) to pipe data directly
through Google Cloud Storage (GCS) without exhausting local disk space.

1.  **Create a Cloud Storage Bucket (if it doesn't exist):**

    ```bash
    gcloud storage buckets create gs://<your-migration-bucket> --project=<your-target-project> --location=<region>
    ```

1.  **Deploy temporary helper pods:**
    - Deploy a temporary helper pod in EKS (`eks-exporter`) mounting the source
      volume (e.g., at `/data`).
    - Deploy a temporary helper pod in GKE (`gke-importer`) mounting the target
      volume (e.g., at `/data`).
1.  **Stream data from EKS to GCS:** Execute on your local workstation:

    ```bash
    kubectl --context=eks-context exec -n <namespace> eks-exporter -- tar -cf - -C /data . | \
      gcloud storage cp - gs://<your-migration-bucket>/volume-backup.tar
    ```

1.  **Stream data from GCS to GKE:** Execute on your local workstation:

    ```bash
    gcloud storage cp gs://<your-migration-bucket>/volume-backup.tar - | \
      kubectl --context=gke-context exec -i -n <namespace> gke-importer -- tar -xf - -C /data
    ```

1.  **Cleanup:** Remove the temporary helper pods.
