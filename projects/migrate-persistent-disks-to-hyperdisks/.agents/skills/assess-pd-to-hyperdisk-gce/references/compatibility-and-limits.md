# Hyperdisk compatibility, sizing, and machine series limits

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

Use this reference when assessing or executing a migration from Google Cloud
Compute Engine Persistent Disk (PD) volumes to Google Cloud Hyperdisk on
fourth-generation (Gen4) virtual machines (VMs).

## Contents

- [Fetching live product limits](#fetching-live-product-limits)
- [Machine series generations and Hyperdisk support](#machine-series-generations-and-hyperdisk-support)
- [Source Persistent Disk performance evaluation](#source-persistent-disk-performance-evaluation)
- [Target Hyperdisk limits and provisioning flags](#target-hyperdisk-limits-and-provisioning-flags)
- [Per-instance Gen4 vCPU performance caps](#per-instance-gen4-vcpu-performance-caps)
- [Architectural blockers and anti-patterns](#architectural-blockers-and-anti-patterns)
- [Comparison with gcloud compute disks convert](#comparison-with-gcloud-compute-disks-convert)

## Fetching live product limits

Compute Engine regularly adds machine series, expands regional availability, and
raises Hyperdisk capacity, input/output operations per second (IOPS), and
throughput limits. Fetch current numeric bounds, scaling formulas, and
machine-series support tables directly from the grounding links in each section
below instead of relying on memorized values.

1.  **Fetch Markdown documentation pages:** `docs.cloud.google.com` supports
    Markdown content negotiation when `-H "Accept: text/markdown"` is passed.
    Save the Markdown response to a file before searching so a non-matching or
    early-exiting `grep` pipeline does not discard the page or trigger a
    fallback to raw HTML:

    ```bash
    curl --fail -sS -H "Accept: text/markdown" -L "<docs-url>"
    ```

2.  **Query live zonal disk-type metadata and CLI flags:** Confirm zonal
    availability and default disk sizes using
    `gcloud compute disk-types describe` and verify supported creation flags
    with `--help`:

    ```bash
    gcloud compute disk-types describe "<hyperdisk-type>" \
      --project="<project-id>" \
      --zone="<zone>"
    gcloud compute disks create --help
    ```

3.  **Fail closed when offline:** If outbound access to `docs.cloud.google.com`
    fails and the user has not provided the relevant documentation excerpt, stop
    and ask the user rather than guessing numeric limits or compatibility rules.

Grounding sources:

- [About Hyperdisk](https://docs.cloud.google.com/compute/docs/disks/hyperdisks)
- [gcloud compute disk-types describe reference](https://docs.cloud.google.com/sdk/gcloud/reference/compute/disk-types/describe)

## Machine series generations and Hyperdisk support

Evaluate machine-series and disk compatibility against the following structural
rules and live documentation matrices:

1.  **Persistent Disk exclusion on Gen4 and newer series:** Fourth-generation
    and newer Compute Engine machine series do not support Persistent Disks for
    either boot or data volumes. Every attached block volume on a Gen4 VM must
    be a Hyperdisk. Check the live machine-series matrix when evaluating
    transitional third-generation series that support both Persistent Disks and
    Hyperdisks.
2.  **Boot disk eligibility:** Fetch the `Limitations for Hyperdisk` section of
    `About Hyperdisk` to verify which Hyperdisk types cannot be used as boot
    disks, such as `hyperdisk-extreme`, `hyperdisk-ml`, and
    `hyperdisk-throughput`, and map boot volumes to a boot-supported type such
    as `hyperdisk-balanced`.
3.  **CPU architecture parity:** Compare the source boot disk `architecture`
    field (`X86_64` or `ARM64`) against the target machine series processor
    architecture in the machine family documentation. A snapshot taken from an
    `X86_64` boot disk cannot boot on an `ARM64` Axion instance, and an `ARM64`
    boot disk cannot boot on an `X86_64` instance.
4.  **Machine series and minimum vCPU restrictions:** Fetch the `Machine series
    support for Hyperdisk` and `Restrictions for machine series support`
    sections of `About Hyperdisk` to confirm that the target machine series
    supports every planned Hyperdisk type and meets any minimum vCPU count or
    bare-metal restriction, such as minimum vCPU thresholds required to attach
    `hyperdisk-extreme`.
5.  **Hyperdisk Throughput generation lock-in:** Once a `hyperdisk-throughput`
    volume is attached to a Gen4 instance, Compute Engine permanently restricts
    that volume to Gen4 instances. Conversely, a `hyperdisk-throughput` volume
    previously attached to a first-, second-, or third-generation instance
    cannot attach to a Gen4 instance without recreating the volume from a
    snapshot.
6.  **In-place machine type edits blocked:** You cannot run
    `gcloud compute instances set-machine-type` to convert a stopped Gen2 VM to
    a Gen4 machine type while any Persistent Disk remains attached. Cutover
    requires creating a new Gen4 instance with a Hyperdisk boot volume created
    from the cutover snapshot.

Grounding sources:

- [About Hyperdisk](https://docs.cloud.google.com/compute/docs/disks/hyperdisks)
- [Machine families resource and comparison guide](https://docs.cloud.google.com/compute/docs/machine-resource)
- [About Hyperdisk Throughput](https://docs.cloud.google.com/compute/docs/disks/hd-types/hyperdisk-throughput)

## Source Persistent Disk performance evaluation

Before sizing target Hyperdisk volumes, determine the effective performance of
each attached Persistent Disk so the migrated volume meets or exceeds the
existing baseline:

1.  **Capacity-coupled scaling model:** Zonal Persistent Disk (`pd-standard`,
    `pd-balanced`, and `pd-ssd`) IOPS and throughput scale linearly with disk
    capacity (`sizeGb`), shared baseline performance across same-type disks on
    the instance, and the source VM's machine-series limits. Extreme Persistent
    Disk (`pd-extreme`) uses explicitly provisioned IOPS (`provisionedIops`).
2.  **Shared baseline across same-type disks on one VM:** For `pd-balanced` and
    `pd-ssd`, Compute Engine adds the free baseline performance (`3,000` IOPS
    and `140` MiB/s) **once per Persistent Disk type per instance**, not once
    per individual disk. When an instance attaches multiple `pd-ssd` or multiple
    `pd-balanced` volumes, calculate the aggregate pool for that disk type on
    the instance (`baseline + per_gib_rate * sum(size_gib)`) or apportion the
    shared baseline across those volumes so the assessment does not over-state
    the source baseline of each individual disk.
3.  **Baseline calculation:** Fetch `Configure disks to meet performance
    requirements` to obtain the current baseline performance, per-GiB IOPS and
    throughput rates, per-disk maximums, and source machine-type caps for each
    source Persistent Disk type, then compute each volume's effective read/write
    IOPS and throughput.

Grounding sources:

- [Configure disks to meet performance requirements](https://docs.cloud.google.com/compute/docs/disks/performance)

## Target Hyperdisk limits and provisioning flags

Hyperdisk decouples IOPS and throughput from volume size, subject to per-type
capacity bounds and provisioning ratios. Fetch `Create a Hyperdisk volume` and
the per-type documentation page for each selected Hyperdisk type to determine
exact sizing parameters:

1.  **Volume size bounds and capacity floors:** Verify the minimum, maximum, and
    default capacity for each target Hyperdisk type. When a source Persistent
    Disk is smaller than the minimum capacity of the desired Hyperdisk type,
    such as `hyperdisk-extreme` or `hyperdisk-throughput`, either map the volume
    to `hyperdisk-balanced` or pass `--size` at or above the target type's
    minimum capacity and expand the guest partition and filesystem after
    cutover.
2.  **Provisioned IOPS and throughput formulas:** Retrieve the minimum, maximum,
    per-GiB or per-TiB scaling formulas, and default performance values from the
    target Hyperdisk type's `Size and performance limits` section. Clamp
    requested `--provisioned-iops` and `--provisioned-throughput` values within
    those bounds for the chosen disk size.
3.  **Allowed `gcloud compute disks create` flags:** Supply only the performance
    and topology flags supported by the target Hyperdisk type:
    - Types with independently configurable IOPS and throughput, such as
      `hyperdisk-balanced` and `hyperdisk-balanced-high-availability`, accept
      both `--provisioned-iops` and `--provisioned-throughput`. Regional
      high-availability volumes also require `--replica-zones`.
    - IOPS-driven types, such as `hyperdisk-extreme`, accept
      `--provisioned-iops` and derive throughput from IOPS. Passing
      `--provisioned-throughput` fails.
    - Throughput-driven types, such as `hyperdisk-throughput`, accept
      `--provisioned-throughput` and derive IOPS from throughput. Passing
      `--provisioned-iops` fails.
4.  **Default performance on small boot disks:** Compare the source boot disk's
    effective performance against the default baseline performance of
    `hyperdisk-balanced`. Omit explicit `--provisioned-iops` and
    `--provisioned-throughput` flags on small boot disks when the default
    baseline already satisfies the workload.

Grounding sources:

- [Create a Hyperdisk volume](https://docs.cloud.google.com/compute/docs/disks/add-hyperdisk)
- [About Hyperdisk Balanced](https://docs.cloud.google.com/compute/docs/disks/hd-types/hyperdisk-balanced)
- [About Hyperdisk Balanced High Availability](https://docs.cloud.google.com/compute/docs/disks/hd-types/hyperdisk-balanced-ha)
- [About Hyperdisk Extreme](https://docs.cloud.google.com/compute/docs/disks/hd-types/hyperdisk-extreme)
- [About Hyperdisk Throughput](https://docs.cloud.google.com/compute/docs/disks/hd-types/hyperdisk-throughput)

## Per-instance Gen4 vCPU performance caps

Even when individual Hyperdisk volumes are provisioned with high IOPS or
throughput, the attached Compute Engine instance enforces aggregate performance
and attachment limits determined by its machine series and vCPU count:

1.  **Shape-specific ceilings and half-duplex sharing:** Fetch `Hyperdisk
    performance limits` and look up the target machine type row across the
    overall machine-type table, the steady-state performance table (where
    applicable), and the per-Hyperdisk-type tables. In `Hyperdisk performance
    limits`, tables write machine shapes using `<series>-*-<vcpus>` wildcard
    patterns such as `n4-*-2`, `c4-*-2`, or `m4-*-2` rather than
    `n4-standard-2`. Remember that Hyperdisk IOPS and throughput limits are
    half-duplex (shared across combined read and write operations) and apply
    across all attached Hyperdisks on the VM, along with per-instance disk count
    and total capacity caps.
2.  **Right-sizing capacity-inflated Persistent Disks:** If a source Gen2 VM
    attached an oversized Persistent Disk solely to obtain higher IOPS under
    Persistent Disk's capacity-coupled model, check whether the target Gen4
    machine shape caps aggregate performance below the summed per-disk values.
    Recommend either lowering per-disk provisioned performance to match the VM
    ceiling or selecting a larger Gen4 shape so the operator does not pay for
    unreachable provisioned IOPS or throughput.

Grounding sources:

- [Hyperdisk performance limits](https://docs.cloud.google.com/compute/docs/disks/hyperdisk-perf-limits)
- [About Hyperdisk performance](https://docs.cloud.google.com/compute/docs/disks/hyperdisk-performance)

## Architectural blockers and anti-patterns

Flag the following conditions during assessment:

1.  **Shared multi-writer or multi-instance block storage:** If the source
    Persistent Disk uses multi-writer mode (`multiWriter: true`) or read-only
    sharing across multiple VMs (`users` contains more than one instance),
    check `Share a disk between VMs` to verify whether the target Hyperdisk type
    and Gen4 series support the required access mode and instance count, or
    whether the workload should migrate to Filestore or Google Cloud NetApp
    Volumes.
2.  **Cold archival or backup blobs:** Do not migrate cold archival Persistent
    Disks to Hyperdisk. Recommend offloading cold archival data to Cloud Storage
    buckets (`NEARLINE`, `COLDLINE`, or `ARCHIVE` storage classes).
3.  **Hardcoded SCSI device paths or missing NVMe and gVNIC support:** Gen4
    instances require Google Virtual NIC (`GVNIC`), Unified Extensible Firmware
    Interface (`UEFI_COMPATIBLE`) boot, and Non-Volatile Memory Express (NVMe)
    storage (`/dev/nvme*n*`). Any `/etc/fstab`, `/etc/crypttab`, Logical Volume
    Manager (LVM) `/etc/lvm/lvm.conf` filter, `/etc/lvm/devices/system.devices`
    file pinning `IDTYPE=devname` or SCSI `sys_wwid`, `mdadm.conf`, or
    `startup-script` referencing `/dev/sd*` or `/dev/disk/by-id/scsi-*` fails on
    first boot and can drop the instance into emergency mode. Migrate mount
    configurations to `UUID=`, `LABEL=`, or
    `/dev/disk/by-id/google-<device-name>` symlinks and refresh or remove
    SCSI-pinned LVM device entries before cutover.
4.  **Attached Local SSDs or accelerators:** If the source Gen2 VM attaches
    Local SSD scratch disks (`type: SCRATCH`) or GPUs, verify in the machine
    family documentation and `gcloud compute machine-types describe` that the
    target Gen4 shape supports equivalent bundled Local SSD capacity or
    accelerator attachments.
5.  **Gen2-pinned sole-tenant or reservation affinities:** Inspect
    `scheduling.nodeAffinities` and `reservationAffinity`. Affinities or
    reservations targeting Gen2 hardware or specific Gen2 machine shapes block
    Gen4 instance creation unless updated or removed.
6.  **Instance deletion protection:** An active `deletionProtection: true` flag
    on the source Gen2 VM does not block creating the new Gen4 VM, but it blocks
    deleting the decommissioned Gen2 VM during post-cutover cleanup until
    disabled.

Grounding sources:

- [Share a disk between VMs](https://docs.cloud.google.com/compute/docs/disks/sharing-disks-between-vms)
- [Set up persistent device names using udev symlinks](https://docs.cloud.google.com/compute/docs/disks/disk-symlinks)
- [Use gVNIC](https://docs.cloud.google.com/compute/docs/networking/using-gvnic)

## Comparison with gcloud compute disks convert

Compute Engine provides `gcloud compute disks convert` for single-disk in-place
conversions, but it does not perform a side-by-side Gen2-to-Gen4 VM cutover:

- **Deletes the original Persistent Disk in place:** `gcloud compute disks
  convert` snapshots the source disk, deletes the original Persistent Disk, and
  recreates a Hyperdisk under the original disk name. Deleting the original
  Persistent Disk eliminates instant side-by-side rollback to the untouched Gen2
  instance and disks.
- **No custom performance flags during conversion:** Its command synopsis
  accepts `--target-disk-type`, Cloud KMS flags, and location flags, but does
  not accept `--provisioned-iops` or `--provisioned-throughput` at conversion
  time.
- **No VM recreation or policy re-binding:** It requires the disk to be detached
  first and does not create the Gen4 VM with `nic-type=GVNIC`, reattach volumes
  with preserved `boot`, `device-name`, and `auto-delete` attributes, or restore
  snapshot schedule `resourcePolicies` and Resource Manager tag bindings.

Grounding sources:

- [Change the type, placement, or location of a disk](https://docs.cloud.google.com/compute/docs/disks/migrate-to-hyperdisk)
- [gcloud compute disks convert reference](https://docs.cloud.google.com/sdk/gcloud/reference/compute/disks/convert)
