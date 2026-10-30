# EKS to GKE storage provisioner mappings

Use this reference when translating StorageClass manifests or provisioning
Google Kubernetes Engine (GKE) storage infrastructure to map Amazon Elastic
Kubernetes Service (EKS) storage provisioners to GKE CSI drivers:

| EKS Storage Provisioner | GKE CSI Driver                 |
| ----------------------- | ------------------------------ |
| `kubernetes.io/aws-ebs` | `pd.csi.storage.gke.io`        |
| `ebs.csi.aws.com`       | `pd.csi.storage.gke.io`        |
| `efs.csi.aws.com`       | `filestore.csi.storage.gke.io` |
