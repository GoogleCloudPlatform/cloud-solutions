# Persistent Disk to Hyperdisk migration summary report

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

## Cutover summary and status

- **Migration timestamp (`RUN_TS`, UTC):** `<run-ts-utc>`
- **Google Cloud project ID:** `<project-id>`
- **Region and zone:** `<region>` / `<zone>`
- **Source Gen2 VM name and status:** `<source-vm>` (`TERMINATED`)
- **Target Gen4 VM name and status:** `<target-gen4-vm>` (`RUNNING`)
- **Source and target machine types:**
  `<source-machine-type>` (`Gen2`) to `<target-machine-type>` (`Gen4`)
- **Source and target internal IP addresses:**
  `<source-internal-ip>` to `<target-internal-ip>`
- **Overall cutover verdict:** `<SUCCESS or FAILED_NEEDS_ROLLBACK>`

### Fleet cutover summary (include when migrating multiple VMs)

| Source Gen2 VM | Source status and IP | Target Gen4 VM | Target machine type | Target status and IP | Migrated disk count | Cutover verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `<source-vm-1>` | `TERMINATED` (`<src-ip-1>`) | `<target-gen4-vm-1>` | `<target-machine-type>` | `RUNNING` (`<tgt-ip-1>`) | `<disk-count>` | `<SUCCESS or FAILED_NEEDS_ROLLBACK>` |
| `<source-vm-2>` | `TERMINATED` (`<src-ip-2>`) | `<target-gen4-vm-2>` | `<target-machine-type>` | `RUNNING` (`<tgt-ip-2>`) | `<disk-count>` | `<SUCCESS or FAILED_NEEDS_ROLLBACK>` |

## Two-stage snapshot inventory

| Source Persistent Disk | Stage-1 baseline snapshot | Stage-1 status and storage bytes | Stage-2 cutover snapshot | Stage-2 status and storage bytes | Snapshot storage location |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `<boot-disk-name>` | `<boot-disk>-s1-<run-ts>` | `READY` (`<s1-bytes>`) | `<boot-disk>-s2-<run-ts>` | `READY` (`<s2-bytes>`) | `<region>` |
| `<data-disk-name>` | `<data-disk>-s1-<run-ts>` | `READY` (`<s1-bytes>`) | `<data-disk>-s2-<run-ts>` | `READY` (`<s2-bytes>`) | `<region>` |

## Target Hyperdisk volumes and policy transfer

| Target Hyperdisk name | Source snapshot | Role and `deviceName` | Hyperdisk type and size (GiB) | Provisioned IOPS | Provisioned throughput (MiB/s) | Preserved `autoDelete`, labels, CMEK, tags | Snapshot schedule `resourcePolicies` transfer |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `<target-boot-hd>` | `<boot-disk>-s2-<run-ts>` | `boot=yes`, `<device-name>` | `hyperdisk-balanced`, `<size-gib>` | `<iops>` | `<mibps>` | `<auto-delete, labels, kms, tags>` | `<none or transferred>` |
| `<target-data-hd>` | `<data-disk>-s2-<run-ts>` | `boot=no`, `<device-name>` | `<hyperdisk-type>`, `<size-gib>` | `<iops>` | `<mibps>` | `<auto-delete, labels, kms, tags>` | `<attached to Hyperdisk and removed from source PD>` |

## Post-cutover Gen4 verification

| Verification check | Observed state on target Gen4 VM | Verdict |
| :--- | :--- | :--- |
| Instance status and machine type | `<RUNNING, target-machine-type>` | `<PASS or FAIL>` |
| Network interface driver (`/sys/class/net/.../device/driver`) | `gvnic` (`nic-type=GVNIC`) | `<PASS or FAIL>` |
| Block device nodes (`lsblk`) | `/dev/nvme*n*` (`nvme_card-pd`) | `<PASS or FAIL>` |
| Persistent udev symlinks (`/dev/disk/by-id/google-*`) | `<all expected google-<device-name> symlinks present>` | `<PASS or FAIL>` |
| Mounted filesystems (`findmnt --real`) | `<all expected mount points mounted with UUID= and nofail>` | `<PASS or FAIL>` |
| Application data integrity (`sha256sum -c` or workload check) | `<all files or workload checks OK>` | `<PASS or FAIL>` |

## Retained rollback state and next steps

- **Retained source Gen2 VMs:** `<source-vm>` (`TERMINATED`, untouched)
- **Retained source Persistent Disks:** `<boot-disk>`, `<data-disk>`
  (attached to stopped Gen2 VM, snapshot schedules moved to target Hyperdisks)
- **Retained Stage-1 and Stage-2 snapshots:** `*-s1-<run-ts>`, `*-s2-<run-ts>`
- **Rollback readiness:** If post-cutover validation fails during the
  observation window, roll back the migration by stopping the Gen4 VM, restoring
  snapshot schedule `resourcePolicies` to the original Persistent Disks, and
  restarting the source Gen2 VM. If the cutover used Option B (internal IP
  preservation), also release `<source-internal-ip>` from the stopped Gen4 VM
  (by moving its `nic0` to `<holding-subnet-name>` or deleting the failed Gen4
  VM) and move the source Gen2 VM's `nic0` back to `<subnet-name>` with
  `--private-network-ip="<source-vm>-internal-ip"` before starting the source
  Gen2 VM.
