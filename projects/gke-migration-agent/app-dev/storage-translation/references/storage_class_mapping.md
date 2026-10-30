# StorageClass mapping reference

This document maps common AWS EKS StorageClasses to GKE StorageClasses.

## StorageClass core matches

| AWS StorageClass / Provisioner     | GKE StorageClass / Provisioner                   | Use Case / Target GKE Class                  |
| :--------------------------------- | :----------------------------------------------- | :------------------------------------------- |
| `gp2` / `kubernetes.io/aws-ebs`    | `standard-rwo` / `pd.csi.storage.gke.io`         | Dynamic Balanced Persistent Disk             |
| `gp3` / `ebs.csi.aws.com`          | `standard-rwo` / `pd.csi.storage.gke.io`         | Dynamic Balanced Persistent Disk             |
| `io1` or `io2` / `ebs.csi.aws.com` | `premium-rwo` / `pd.csi.storage.gke.io`          | High-performance SSD Persistent Disk         |
| `io2` / `ebs.csi.aws.com`          | `hyperdisk-balanced` / `pd.csi.storage.gke.io`   | Ultra IOPS/throughput (C3/N4 machine series) |
| `efs.csi.aws.com`                  | `filestore-rwx` / `filestore.csi.storage.gke.io` | Shared ReadWriteMany file shares (Filestore) |

## GKE volume binding mode

For custom dynamic StorageClasses, always configure:

```yaml
volumeBindingMode: WaitForFirstConsumer
```

This ensures that GKE provisions the Persistent Disk in the specific zone where
the scheduled pod is assigned.

## GKE volume constraints and minimum sizes

When translating PVC `resources.requests.storage` specs, ensure requested sizes
meet GKE CSI driver minimum thresholds:

- **Persistent Disk (`standard-rwo` / `pd-balanced` / `pd-ssd` via
  `pd.csi.storage.gke.io`)**:
    - Minimum size: **1GiB**.
    - Official documentation:
      [GKE Persistent Disk CSI Driver](https://cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/pd-csi)
- **Filestore (`filestore-rwx` via `filestore.csi.storage.gke.io`)**:
    - `BASIC_HDD`: Minimum size **1TiB** (`1024Gi`).
    - `BASIC_SSD`: Minimum size **2.5TiB** (`2560Gi`).
    - `HIGH_SCALE_SSD` / `ENTERPRISE`: Minimum size **1TiB** (`1024Gi`).
    - Official documentation:
      [GKE Filestore CSI Driver](https://cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/filestore-csi-driver)

## Dynamic PVC translation example

### EKS PVC

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: data-volume
  namespace: production-app
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: gp2
  resources:
    requests:
      storage: 10Gi
```

### Translated GKE PVC

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: data-volume
  namespace: production-app
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: standard-rwo
  resources:
    requests:
      storage: 10Gi
```
