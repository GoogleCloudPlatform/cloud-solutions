# Persistent Disk to Hyperdisk migration assessment report

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

## Summary and readiness verdict

- **Assessment timestamp (UTC):** `<timestamp-utc>`
- **Google Cloud project ID:** `<project-id>`
- **Region and zone:** `<region>` / `<zone>`
- **Source virtual machine (VM) name:** `<source-vm>`
- **Source machine type and generation:**
  `<source-machine-type>` (`<source-gen>`)
- **Target machine type and generation:** `<target-machine-type>` (`Gen4`)
- **Overall readiness verdict:**
  `<READY or READY_WITH_PRE_CUTOVER_ACTIONS or BLOCKED>`

### Fleet summary (include when assessing multiple VMs)

| Source VM name | Source machine type | Target Gen4 machine type | Attached disk count | Total target capacity (GiB) | Total target IOPS / throughput (MiB/s) | Readiness verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `<source-vm-1>` | `<source-machine-type>` | `<target-machine-type>` | `<disk-count>` | `<total-gib>` | `<total-iops>` / `<total-mibps>` | `<READY or READY_WITH_PRE_CUTOVER_ACTIONS or BLOCKED>` |
| `<source-vm-2>` | `<source-machine-type>` | `<target-machine-type>` | `<disk-count>` | `<total-gib>` | `<total-iops>` / `<total-mibps>` | `<READY or READY_WITH_PRE_CUTOVER_ACTIONS or BLOCKED>` |

## Source instance configuration summary

- **Current instance status:** `<RUNNING or TERMINATED>`
- **CPU architecture:** `<X86_64 or ARM64>`
- **Service account and access scopes:** `<service-account-email>` (`<scopes>`)
- **Network and subnetwork:** `<network>` / `<subnetwork>`
- **Internal and external IP addresses:**
  `<internal-ip>` / `<external-ip-or-none>`
- **Network tags and instance labels:** `<tags>` / `<labels>`
- **Shielded VM configuration:** `<secure-boot, vtpm, integrity-monitoring>`
- **Deletion protection enabled:** `<true or false>`
- **Startup script present in metadata:** `<true or false>`

## Guest OS, NVMe, and gVNIC compatibility checks

| Check | Observed state | Verdict | Required remediation |
| :--- | :--- | :--- | :--- |
| Boot disk `guestOsFeatures` includes `GVNIC` | `<present or missing>` | `<PASS or FAIL>` | `<none or recreate boot image with GVNIC>` |
| Boot disk `guestOsFeatures` includes `UEFI_COMPATIBLE` | `<present or missing>` | `<PASS or FAIL>` | `<none or enable UEFI boot support>` |
| Boot disk CPU architecture matches target Gen4 series | `<source-arch vs target-arch>` | `<PASS or FAIL>` | `<none or select matching X86_64 or ARM64 series>` |
| `nvme` and `gve` drivers built-in (`=y`) or in guest `initramfs` (`=m`) | `<verified or unverified or missing>` | `<PASS or WARN or FAIL>` | `<none or rebuild initramfs with nvme and gve>` |
| `/etc/fstab`, LVM `system.devices`, and mount configs free of `/dev/sd*` and `scsi-*` | `<clean or contains-scsi-paths>` | `<PASS or FAIL>` | `<none or update to UUID= or google-<device-name> with nofail>` |
| Startup script free of unguarded `mkfs` and `/dev/sd*` paths | `<clean or hazard-found>` | `<PASS or FAIL>` | `<none or guard mkfs with blkid and use google-<device-name>>` |

## Regional quota headroom

| Quota metric | Region | Current usage | Quota limit | Available headroom | Required for cutover | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `<hyperdisk_balanced_total_storage>` | `<region>` | `<usage>` | `<limit>` | `<available>` | `<required>` | `<PASS or FAIL>` |
| `<hyperdisk_balanced_total_provisioned_iops>` | `<region>` | `<usage>` | `<limit or unlimited (-1)>` | `<available>` | `<required>` | `<PASS or FAIL>` |
| `<hyperdisk_balanced_total_provisioned_throughput>` | `<region>` | `<usage>` | `<limit or unlimited (-1)>` | `<available>` | `<required>` | `<PASS or FAIL>` |
| `cpus_per_vm_family (<vm-family>)` | `<region>` | `<usage>` | `<limit>` | `<available>` | `<required>` | `<PASS or FAIL>` |
| `CPUS` | `<region>` | `<usage>` | `<limit>` | `<available>` | `<required>` | `<PASS or FAIL>` |
| `SNAPSHOTS` | `<region>` | `<usage>` | `<limit>` | `<available>` | `<required>` | `<PASS or FAIL>` |

## Attached Persistent Disks and target Hyperdisk sizing

| Source disk name | Role and `deviceName` | Source PD type and size (GiB) | Source effective IOPS / throughput (MiB/s) | Target Hyperdisk name and type | Target size (GiB) | Target `--provisioned-iops` | Target `--provisioned-throughput` (MiB/s) | Preserved attributes (`autoDelete`, CMEK, labels, tags, schedules) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `<boot-disk-name>` | `boot=yes`, `<device-name>` | `<pd-type>`, `<size-gib>` | `<src-iops>` / `<src-mibps>` | `<target-boot-hd>`, `hyperdisk-balanced` | `<target-size-gib>` | `<iops-or-default>` | `<mibps-or-default>` | `<auto-delete, kms-key, labels, tags, policies>` |
| `<data-disk-name>` | `boot=no`, `<device-name>` | `<pd-type>`, `<size-gib>` | `<src-iops>` / `<src-mibps>` | `<target-data-hd>`, `<hyperdisk-type>` | `<target-size-gib>` | `<iops-or-n/a>` | `<mibps-or-n/a>` | `<auto-delete, kms-key, labels, tags, policies>` |

### Per-instance vCPU ceiling check

- **Attached target Hyperdisk count vs. instance limit:**
  `<disk-count>` / `<vm-max-disks>`
- **Summed provisioned IOPS across all target Hyperdisks:**
  `<total-provisioned-iops>`
- **Target Gen4 instance vCPU IOPS ceiling:** `<vm-max-iops>`
- **Summed provisioned throughput across all target Hyperdisks (MiB/s):**
  `<total-provisioned-mibps>`
- **Target Gen4 instance vCPU throughput ceiling (MiB/s):** `<vm-max-mibps>`
- **Alignment notes:**
  `<confirm whether disk count and per-disk values fit within vCPU ceilings>`

## Recommended cutover and consistency strategy

- **Cutover pattern:**
  `<Offline two-stage snapshot VM cutover or Online data-disk-only cutover>`
- **Snapshot consistency method:**
  `<Stop app and VM before snapshot2 or In-guest fsfreeze>`
- **Snapshot storage location:** `<region>`
- **Instance naming and IP cutover strategy:**
  `<Promote and reassign static IP or New instance name and DNS update>`
- **Customer-managed encryption key (CMEK) readiness:**
  `<Not used or Verified Cloud KMS role on Compute Engine service agent>`

## Pre-cutover action items

1.  `<Action item 1, or "None — ready to proceed to cutover">`
2.  `<Action item 2>`
