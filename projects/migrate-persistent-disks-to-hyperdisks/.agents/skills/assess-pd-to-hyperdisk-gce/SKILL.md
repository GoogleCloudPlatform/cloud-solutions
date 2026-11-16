---
name: assess-pd-to-hyperdisk-gce
description: >-
  Evaluates Compute Engine virtual machines and Persistent Disks for migration
  readiness to Hyperdisk volumes and fourth-generation machine series. Use when
  asked to assess, audit, size, check compatibility or quotas, or plan a Compute
  Engine Persistent Disk to Hyperdisk migration. Don't use for executing
  state-changing cutovers, rolling back migrations, or migrating Google
  Kubernetes Engine volumes.
---

# Assess Persistent Disk to Hyperdisk migration on Compute Engine

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

Run a read-only pre-flight assessment of a Google Cloud Compute Engine virtual
machine (VM) and its attached Persistent Disk (PD) volumes before migrating to
Google Cloud Hyperdisk and fourth-generation (Gen4) machine series. Do not
modify, stop, snapshot, or delete any cloud resource during this assessment.

## Prerequisites

Verify that the execution environment meets the following requirements before
running discovery commands:

1.  **Required command-line tools and documentation access:** Confirm that the
    Google Cloud CLI (`gcloud`), `jq`, and `curl` (or a built-in web-fetch tool
    capable of retrieving `https://docs.cloud.google.com` pages) are available,
    and check whether the `gcloud alpha` component is installed (if
    `gcloud alpha` is unavailable, Step 3.2 provides a `curl` REST API
    fallback):

    ```bash
    gcloud --version
    gcloud alpha --help >/dev/null 2>&1 || echo "gcloud alpha not installed; use REST fallback in Step 3.2"
    jq --version
    curl --version
    ```

2.  **Authentication and target project configuration:** Confirm an active
    authenticated principal, refresh short-lived Certificate-Based Access (CBA)
    or OAuth tokens before running non-interactive `--quiet` commands, and
    verify the target project identifier, region, and zone:

    ```bash
    gcloud auth list --quiet --filter="status:ACTIVE" --format="value(account)"
    gcloud auth print-access-token --quiet >/dev/null
    gcloud config get-value project --quiet
    ```

3.  **Required Identity and Access Management (IAM) permissions:**
    `roles/compute.viewer` grants read-only Compute Engine discovery
    permissions, and `roles/browser` or `roles/viewer` grants project metadata
    access to resolve the numeric project number.
    `roles/serviceusage.serviceUsageViewer` (or `roles/cloudquotas.viewer` when
    querying the Cloud Quotas API, plus `roles/serviceusage.serviceUsageConsumer`
    when passing `x-goog-user-project` to the REST fallback) grants access to
    quota limits for Hyperdisk and fourth-generation vCPU families.
    `roles/resourcemanager.tagViewer` or `roles/cloudasset.viewer` grants access
    to Resource Manager tag bindings on disks.

4.  **Failure handling:** If `gcloud` or `jq` is missing, if no active account
    is authenticated, if `gcloud compute instances describe` returns a
    `PERMISSION_DENIED` or `NOT_FOUND` error, or if live product limits cannot
    be fetched from `docs.cloud.google.com` (and have not been provided by the
    user), stop the assessment immediately. Report the missing tool, unreachable
    documentation URL, missing IAM permission, or unresolved resource identifier
    to the user and do not fabricate sizing or readiness findings.

## Scope boundaries

Confirm that the target workload falls within the supported scope before
proceeding:

- **Migration directionality (Persistent Disk to Hyperdisk only):** This
  workflow assesses forward upgrades from Persistent Disk to Hyperdisk, where
  capacity, IOPS, and throughput are provisioned independently, and post-cutover
  rollback reuses the retained source Gen2 VM and Persistent Disks. A reverse
  Hyperdisk-to-Persistent Disk (`HD-to-PD`) migration is out of scope and
  requires a separate assessment because Persistent Disk couples IOPS and
  throughput to disk capacity (`sizeGb`), prevents a 1-to-1 mapping, can
  introduce storage performance degradation when Hyperdisk provisioned levels
  exceed Persistent Disk maximums, and requires calculating disk capacity
  inflation (`sizeGb`) to meet target performance.
- **Zonal Persistent Disks:** This workflow assesses zonal Persistent Disks,
  including `pd-standard`, `pd-balanced`, `pd-ssd`, and `pd-extreme`. If an
  attached disk is a regional Persistent Disk with a `regionalDisks` URI, note
  that regional volumes can migrate only to Hyperdisk Balanced High Availability
  (`hyperdisk-balanced-high-availability`) and flag the disk for separate
  high-availability planning.
- **Linux guest operating systems:** In-guest readiness checks in Step 2 target
  Linux instances. If the boot disk `licenses` or `guestOsFeatures` indicate a
  Windows Server guest, flag Windows Volume Shadow Copy Service (VSS) and driver
  verification for manual operator review.
- **Standalone Compute Engine instances:** If the instance belongs to a managed
  instance group (MIG) or a Google Kubernetes Engine (GKE) node pool, stop and
  inform the user that instance template recreation or GKE storage migration
  workflows apply instead of single-instance cutover.

## Assessment workflow

Execute the following five read-only steps in order. Load
[references/compatibility-and-limits.md](references/compatibility-and-limits.md)
during Steps 2 through 4 to evaluate machine series compatibility, boot disk
rules, per-disk performance bounds, and per-instance vCPU caps.

### Step 1: Inspect source instances and attached Persistent Disks

1.  Query the source VM configuration (or all target VMs when assessing a
    multi-VM migration wave) and project the attributes that must carry over to
    the target Gen4 instances:

    ```bash
    # Single-VM discovery:
    gcloud compute instances describe "<source-vm>" \
      --quiet \
      --project="<project-id>" \
      --zone="<zone>" \
      --format="json(name,machineType,status,cpuPlatform,deletionProtection,canIpForward,serviceAccounts,networkInterfaces,tags,labels,metadata,scheduling,shieldedInstanceConfig,disks,reservationAffinity,resourcePolicies)"

    # Multi-VM or wave discovery across one or more instance names or filters:
    gcloud compute instances list \
      --quiet \
      --project="<project-id>" \
      --filter="zone:(<zone>) AND name:(<vm-1> <vm-2>)" \
      --format="json(name,zone,machineType,status,cpuPlatform,deletionProtection,canIpForward,serviceAccounts,networkInterfaces,tags,labels,metadata,scheduling,shieldedInstanceConfig,disks,reservationAffinity,resourcePolicies)"
    ```

2.  For each entry in each instance's `disks` array, record the attachment
    parameters:
    - `deviceName`, `boot`, `autoDelete`, `mode`, and `interface`
    - Disk name extracted from the `source` URI

3.  Inspect all attached Persistent Disks in the target zone, including each
    disk's numeric `id`. When an instance or migration wave attaches multiple
    disks, batch the lookup with `gcloud compute disks list` in a single API
    call:

    ```bash
    gcloud compute disks list \
      --quiet \
      --project="<project-id>" \
      --filter="zone:(<zone>) AND name:(<disk-1> <disk-2>)" \
      --format="json(id,name,sizeGb,type,status,architecture,guestOsFeatures,licenses,labels,resourcePolicies,diskEncryptionKey,provisionedIops,provisionedThroughput,replicaZones,users,multiWriter)"
    ```

    Deduplicate disks by numeric `id` across all assessed VMs. If any disk lists
    more than one instance in `users`, flag it as a shared volume so it is sized
    once and coordinated across all attached VMs during cutover.

4.  Resolve the numeric project number and check for Resource Manager tag
    bindings on each unique disk. Compute Engine Resource Manager tag bindings
    require the numeric project number and numeric disk `id` in `--parent`
    rather than the project ID or disk name:

    ```bash
    PROJECT_NUMBER="$(gcloud projects describe "<project-id>" \
      --quiet \
      --format="value(projectNumber)")"
    gcloud resource-manager tags bindings list \
      --quiet \
      --parent="//compute.googleapis.com/projects/${PROJECT_NUMBER}/zones/<zone>/disks/<disk-id>" \
      --location="<zone>" \
      --format="json"
    ```

5.  Evaluate the discovered instance and disk attributes against the
    `Architectural blockers and anti-patterns` section of
    [references/compatibility-and-limits.md](references/compatibility-and-limits.md)
    and record any blockers or required pre-cutover adjustments.

### Step 2: Verify guest OS, NVMe, and gVNIC readiness

Gen4 machine series require the Google Virtual NIC (gVNIC) network interface,
Unified Extensible Firmware Interface (UEFI) boot, and Non-Volatile Memory
Express (NVMe) storage drivers. Gen2 instances commonly use VirtIO Ethernet and
Small Computer System Interface (SCSI) disk device nodes such as `/dev/sda` and
`/dev/disk/by-id/scsi-0Google_PersistentDisk_<device-name>`. On Gen4 instances,
disks appear as `/dev/nvme*n*` and `/dev/disk/by-id/google-<device-name>`.

1.  **Verify boot disk metadata features and CPU architecture:**
    - Confirm that the boot disk `guestOsFeatures` array includes both
      `GVNIC` and `UEFI_COMPATIBLE`.
    - Compare the boot disk `architecture` field (`X86_64` or `ARM64`) against
      the target Gen4 series processor architecture documented in the grounding
      links of
      [references/compatibility-and-limits.md](references/compatibility-and-limits.md).

2.  **Inspect in-guest storage and driver configuration:** When SSH access
    through Identity-Aware Proxy (IAP) to the running source VM is permitted,
    run the following read-only checks inside the guest or ask the user to
    provide the output. When the instance metadata sets
    `enable-guest-attributes=TRUE`, `gcloud compute ssh` fetches `hostkeys/`
    from the Compute Engine control plane and populates
    `~/.ssh/google_compute_known_hosts` before connecting. If the instance omits
    `enable-guest-attributes=TRUE` and `~/.ssh/google_compute_known_hosts` lacks
    the host alias, connect once with `StrictHostKeyChecking=accept-new` on a
    user-confirmed instance and never pass `StrictHostKeyChecking=no`:

    ```bash
    gcloud compute ssh "<source-vm>" \
      --quiet \
      --project="<project-id>" \
      --zone="<zone>" \
      --tunnel-through-iap \
      --strict-host-key-checking=yes \
      --command="cat /etc/fstab; test -f /etc/crypttab && cat /etc/crypttab; test -f /etc/mdadm/mdadm.conf && cat /etc/mdadm/mdadm.conf; test -f /proc/mdstat && cat /proc/mdstat; test -f /etc/lvm/devices/system.devices && sudo cat /etc/lvm/devices/system.devices; ls -l /dev/disk/by-id/; (grep -E 'CONFIG_(BLK_DEV_NVME|NVME_CORE|GVE)=' /boot/config-\$(uname -r) 2>/dev/null || zgrep -E 'CONFIG_(BLK_DEV_NVME|NVME_CORE|GVE)=' /proc/config.gz 2>/dev/null || true); (sudo lsinitramfs /boot/initrd.img-\$(uname -r) 2>/dev/null || sudo lsinitrd /boot/initramfs-\$(uname -r).img 2>/dev/null || sudo lsinitrd 2>/dev/null || true) | grep -E 'nvme|gve' || true; systemctl is-active google-guest-agent || systemctl is-active google-guest-agent-manager"
    ```

3.  **Flag device-naming and boot hazards:**
    - Flag any `/etc/fstab`, `/etc/crypttab`, Logical Volume Manager (LVM)
      `/etc/lvm/lvm.conf` filter, `/etc/lvm/devices/system.devices` entry
      pinning `IDTYPE=devname` or SCSI `sys_wwid`, `mdadm.conf`, or systemd
      `.mount` entry that references `/dev/sd*` or `/dev/disk/by-id/scsi-*`.
      Recommend converting mount entries to a filesystem universally unique
      identifier (`UUID=`), filesystem label (`LABEL=`), or
      `/dev/disk/by-id/google-<device-name>`, adding the `nofail` mount option
      on non-boot data disks, and clearing or updating SCSI-pinned LVM device
      files before cutover.
    - Inspect the instance `metadata.items` for any `startup-script` or
      `startup-script-url`. Compute Engine executes the startup script on every
      boot, including the first boot of the migrated Gen4 VM. Flag any startup
      script that references `/dev/sd*` or runs `mkfs` without first checking
      `blkid` for an existing filesystem.
    - Verify that `/boot/config-$(uname -r)` or `/proc/config.gz` builds NVMe
      (`CONFIG_BLK_DEV_NVME=y`) and gVNIC (`CONFIG_GVE=y`) into the kernel or
      that the boot `initramfs` or `initrd` image (inspected with `lsinitramfs`
      or `lsinitrd`) packages them as loadable modules (`=m`). Do not rely on
      `lsmod` alone on a Gen2 instance because `gve` loads only on gVNIC
      hardware and cloud kernels commonly compile PCIe NVMe directly into
      `vmlinuz`. Confirm that `google-guest-agent` or
      `google-guest-agent-manager` is active so udev rules remain installed for
      `/dev/disk/by-id/google-<device-name>` symlinks on NVMe devices.

### Step 3: Check target machine series availability and regional quotas

1.  Read the machine series and Hyperdisk compatibility rules in
    [references/compatibility-and-limits.md](references/compatibility-and-limits.md).
    Verify that the requested target machine type exists in `<zone>`:

    ```bash
    gcloud compute machine-types describe "<target-machine-type>" \
      --quiet \
      --project="<project-id>" \
      --zone="<zone>" \
      --format="json(name,guestCpus,memoryMb,BundledLocalSsds)"
    ```

2.  Inspect regional Compute Engine and Service Usage quotas in `<region>`.
    `gcloud compute regions describe` reports regional `CPUS` and `SNAPSHOTS`
    usage and limits. Service Usage exposes Hyperdisk regional limits under
    `hyperdisk_*` and fourth-generation vCPU limits under `cpus_per_vm_family`
    with `region` and `vm_family` dimensions, such as `N4`, `C4`, `C4A`, `C4D`,
    and `M4`, where an `effectiveLimit` of `-1` denotes an unlimited quota:

    ```bash
    gcloud compute regions describe "<region>" \
      --quiet \
      --project="<project-id>" \
      --format="json(quotas)" | \
      jq '[.quotas[] | select(.metric | test("^(CPUS|SNAPSHOTS)$"))]'

    gcloud alpha services quota list \
      --quiet \
      --service="compute.googleapis.com" \
      --consumer="projects/<project-id>" \
      --format="json" | \
      jq --arg region "<region>" '[.[] | select(.metric | test("hyperdisk|cpus_per_vm_family")) | {metric, displayName, buckets: [.consumerQuotaLimits[]? | select(.unit | contains("{region}")) | .quotaBuckets[]? | select((.dimensions == null) or (.dimensions.region == $region))]}]'

    # Fallback when the gcloud alpha component is not installed (queries the
    # Service Usage v1beta1 REST API directly with curl, or the Cloud Quotas v1
    # REST API at
    # https://cloudquotas.googleapis.com/v1/projects/<project-id>/locations/global/services/compute.googleapis.com/quotaInfos
    # when cloudquotas.googleapis.com is enabled on the project):
    ACCESS_TOKEN="$(gcloud auth print-access-token --quiet)"
    PAGE_TOKEN=""
    while :; do
      RESPONSE="$(curl --silent --show-error --fail \
        -H "Authorization: Bearer ${ACCESS_TOKEN}" \
        -H "x-goog-user-project: <project-id>" \
        "https://serviceusage.googleapis.com/v1beta1/projects/<project-id>/services/compute.googleapis.com/consumerQuotaMetrics?pageSize=500${PAGE_TOKEN:+&pageToken=${PAGE_TOKEN}}")"
      printf '%s\n' "${RESPONSE}" | \
        jq --arg region "<region>" '[.metrics[]? | select(.metric | test("hyperdisk|cpus_per_vm_family")) | {metric, displayName, buckets: [.consumerQuotaLimits[]? | select(.unit | contains("{region}")) | .quotaBuckets[]? | select((.dimensions == null) or (.dimensions.region == $region))]}]'
      PAGE_TOKEN="$(printf '%s\n' "${RESPONSE}" | jq -r '.nextPageToken // empty')"
      [[ -n "${PAGE_TOKEN}" ]] || break
    done

    gcloud compute disks list \
      --quiet \
      --project="<project-id>" \
      --filter="zone ~ ^<region>- AND type ~ hyperdisk" \
      --format="json(name,sizeGb,type,provisionedIops,provisionedThroughput)"

    gcloud compute instances list \
      --quiet \
      --project="<project-id>" \
      --filter="zone ~ ^<region>- AND status!=TERMINATED" \
      --format="json(name,machineType,status)"
    ```

3.  Treat an `effectiveLimit` of `-1` as unlimited. When assessing multiple VMs
    in the same region, run the regional quota queries once per region and sum
    the target requirements across all VMs and unique disks in the migration
    wave. For finite limits, compute current regional Hyperdisk capacity,
    billable provisioned input/output operations per second (IOPS) and
    throughput above the free per-disk baseline, and target-family vCPU usage
    from the regional `disks list` and `instances list` outputs. Compare
    `limit - usage` against the cumulative required capacity, billable IOPS,
    billable throughput, snapshot count (two snapshots per unique migrated
    disk), and vCPU count while the source Gen2 VMs and Persistent Disks remain
    allocated during side-by-side cutover. Flag any quota where `limit - usage`
    is less than the single-VM or cumulative wave requirement as a blocker.

### Step 4: Map disks to Hyperdisk types and calculate sizing

Fetch the live Compute Engine product documentation pages linked in
[references/compatibility-and-limits.md](references/compatibility-and-limits.md)
once per assessment and compute the target Hyperdisk configuration for every
attached disk on each assessed VM:

1.  **Select the target Hyperdisk type:** Map the boot disk and each data disk
    to a compatible Hyperdisk type for the target Gen4 machine series, checking
    boot disk eligibility, machine series support, minimum vCPU thresholds,
    minimum capacity floors, and generation lock-in rules using the
    `Machine series generations and Hyperdisk support` and
    `Target Hyperdisk limits and provisioning flags` sections of
    [references/compatibility-and-limits.md](references/compatibility-and-limits.md).

2.  **Compute baseline performance and target Hyperdisk flags:** Calculate each
    source Persistent Disk's effective IOPS and throughput from its type,
    `sizeGb`, and any same-type sibling disks on the same instance using the
    live formulas linked in the
    `Source Persistent Disk performance evaluation` section of
    [references/compatibility-and-limits.md](references/compatibility-and-limits.md).
    Determine the target Hyperdisk capacity, clamp `--provisioned-iops` and
    `--provisioned-throughput` to the target type's live bounds, and record
    which provisioning flags the target type accepts.

3.  **Check aggregate per-instance vCPU and attachment ceilings:** For each VM,
    sum the attached disk count, total disk capacity, target IOPS, and target
    throughput across all disks attached to that VM and compare the totals
    against the exact target machine shape row fetched from the
    `Per-instance Gen4 vCPU performance caps` section of
    [references/compatibility-and-limits.md](references/compatibility-and-limits.md).
    Warn the user if the chosen machine shape caps aggregate disk performance
    below the summed per-disk provisioned values or if the disk count or total
    capacity exceeds the machine shape's attachment limits.

### Step 5: Define cutover strategy and generate assessment report

1.  **Define the network identity and naming strategy:** While the stopped
    source Gen2 VM is retained for fast rollback, it continues to hold its
    instance name and any assigned internal or external IP addresses. Recommend
    one of two cutover approaches:
    - **IP preservation:** Promote the source Gen2 VM's ephemeral internal IP
      address to a reserved static internal IP address, unassign it from the
      stopped Gen2 VM during cutover, and assign it to the new Gen4 VM.
    - **Side-by-side IP and Domain Name System (DNS) cutover:** Create the Gen4
      VM with a new instance name and new internal IP address, validate the
      workload, and switch traffic through DNS or load-balancer backend updates.

2.  **Define the snapshot consistency strategy:**
    - For the standard **offline two-stage VM cutover**, instruct the operator
      to take the baseline `snapshot1` while the Gen2 VM is online without
      freezing the filesystem, then cleanly stop the application or database and
      stop the Gen2 VM (`TERMINATED`) before taking incremental `snapshot2`.
      Because target Hyperdisks are created from `snapshot2`, stopping the
      application and instance before `snapshot2` makes the cutover snapshot
      application-consistent and crash-consistent without stalling live traffic
      during `snapshot1`.
    - For an **online data-disk-only cutover** where the instance is not
      stopped, document application quiescing and `fsfreeze` requirements before
      the final snapshot.

3.  **Verify customer-managed encryption key (CMEK) prerequisites:** If any
    source disk uses a CMEK (`diskEncryptionKey.kmsKeyName`), note that the
    Compute Engine service agent
    (`service-<project-number>@compute-system.iam.gserviceaccount.com`) must
    hold `roles/cloudkms.cryptoKeyEncrypterDecrypter` on that Cloud Key
    Management Service (Cloud KMS) key, and `--kms-key` must be supplied when
    creating the target Hyperdisk from `snapshot2`.

4.  **Render the assessment report:** Load
    [assets/assessment-report-template.md](assets/assessment-report-template.md)
    and populate every section with the discovered inventory, compatibility
    verdicts, quota headroom, per-disk sizing table, and recommended cutover
    parameters. Present the completed report to the user as the readiness gate
    before any migration execution.
