# StorageClass mapping reference

| Source provisioner / params                    | Target GKE StorageClass Name | Description / Notes                                                                          |
| ---------------------------------------------- | ---------------------------- | -------------------------------------------------------------------------------------------- |
| `ebs.csi.aws.com` + `type: gp3`                | `standard-rwo`               | Built-in GKE, uses `pd-balanced`. (Alternative: Custom class for `hyperdisk` if needed)      |
| `ebs.csi.aws.com` + `type: gp2` (legacy)       | `standard-rwo`               | Built-in GKE default, uses `standard-rwo`.                                                   |
| `ebs.csi.aws.com` + `type: io2`                | `premium-rwo`                | Built-in GKE, uses `pd-ssd` (Hyperdisk Extreme for extreme IOPS requires custom class).      |
| `ebs.csi.aws.com` + `type: st1`                | `pd-standard` (Custom)       | Requires custom StorageClass definition in GKE using `pd-standard` disk type.                |
| `efs.csi.aws.com` + `provisioningMode: efs-ap` | `filestore-rwx` (Custom)     | Custom class using `filestore.csi.storage.gke.io`. Requires Filestore instance provisioning. |
| `fsx.csi.aws.com` (Lustre)                     | `parallelstore-rwx`          | Built-in GKE in recent versions, or requires custom class with Parallelstore CSI.            |
| `fsx-netapp-ontap.csi.aws.com`                 | Custom NetApp Class          | Requires custom class using `netapp.csi.storage.gke.io` (NetApp Volumes).                    |
