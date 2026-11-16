---
name: migrate-pd-to-hyperdisk-gce
description: >-
  Executes a side-by-side two-stage snapshot migration of Compute Engine virtual
  machines and Persistent Disks to Hyperdisk volumes and fourth-generation
  machine series. Use when asked to migrate, cut over, convert, or move a
  Compute Engine instance and its Persistent Disks to Hyperdisk and a
  fourth-generation machine series. Don't use for read-only pre-flight
  assessments, post-cutover rollbacks, or Google Kubernetes Engine storage
  migrations.
---

# Migrate Persistent Disks to Hyperdisk on Compute Engine

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

Execute a side-by-side, two-stage snapshot cutover of a Google Cloud Compute
Engine virtual machine (VM) and its attached Persistent Disk (PD) volumes to
Google Cloud Hyperdisk and a fourth-generation (Gen4) machine series. Retain the
stopped source Gen2 VM and original Persistent Disks untouched throughout the
cutover so the workload can roll back immediately if validation fails.

## Prerequisites and safety rules

Verify that the execution environment and migration plan meet the following
requirements before running any state-changing command:

1.  **Required command-line tools and documentation access:** Confirm that the
    Google Cloud CLI (`gcloud`), `jq`, and `curl` (or a built-in web-fetch tool
    capable of retrieving `https://docs.cloud.google.com` pages) are available:

    ```bash
    gcloud --version
    jq --version
    curl --version
    ```

2.  **Authentication and token refresh:** Confirm an active authenticated
    principal, refresh short-lived Certificate-Based Access (CBA) or OAuth
    tokens before running non-interactive `--quiet` commands, and confirm the
    target project, region, and zone:

    ```bash
    gcloud auth list --quiet --filter="status:ACTIVE" --format="value(account)"
    gcloud auth print-access-token --quiet >/dev/null
    gcloud config get-value project --quiet
    ```

3.  **Required Identity and Access Management (IAM) permissions:**
    - `roles/compute.instanceAdmin.v1` and `roles/compute.storageAdmin` to stop
      instances, create snapshots and Hyperdisk volumes, re-bind snapshot
      schedules, and create the target Gen4 instance.
    - `roles/iam.serviceAccountUser` on the workload service account attached to
      the source VM so the new Gen4 VM can attach the same service account.
    - `roles/resourcemanager.tagUser` when recreating Resource Manager tag
      bindings on the new Hyperdisk volumes, and `roles/browser` or
      `roles/viewer` to resolve the numeric project number.
    - `roles/cloudkms.cryptoKeyEncrypterDecrypter` held by the Compute Engine
      service agent
      (`service-<project-number>@compute-system.iam.gserviceaccount.com`) when
      migrating customer-managed encryption key (CMEK) protected volumes.

4.  **Safety guardrails:**
    - Never run `gcloud compute disks convert`, `gcloud compute instances
      delete`, or `gcloud compute disks delete` on the source Gen2 VM or source
      Persistent Disks during cutover.
    - Never pass `--strict-host-key-checking=no` or `StrictHostKeyChecking=no`
      to `gcloud compute ssh`.
    - If any snapshot creation, Hyperdisk creation, resource-policy attachment,
      instance creation, or post-cutover verification command fails, stop
      immediately and report the exact failing step and error output to the user
      rather than continuing to the next step.

## Migration workflow

Execute the following five steps in order. Load
[references/cutover-and-metadata-preservation.md](references/cutover-and-metadata-preservation.md)
before Step 4 to map captured JSON attributes to `gcloud compute disks create`
and `gcloud compute instances create` flags.

### Step 1: Capture pre-cutover manifest and verify guest readiness

1.  Set a UTC timestamp (`RUN_TS`) for snapshot naming and capture the complete
    source instance and disk manifests to restore every attribute on the target
    Gen4 resources and reference the manifests during rollback:

    ```bash
    RUN_TS="$(date -u +%Y%m%d-%H%M%S)"
    PROJECT_NUMBER="$(gcloud projects describe "<project-id>" \
      --quiet \
      --format="value(projectNumber)")"

    # Single-VM manifest capture (use gcloud compute instances list with a
    # name filter when migrating a multi-VM wave):
    gcloud compute instances describe "<source-vm>" \
      --quiet \
      --project="<project-id>" \
      --zone="<zone>" \
      --format="json(name,machineType,status,cpuPlatform,deletionProtection,canIpForward,serviceAccounts,networkInterfaces,tags,labels,metadata,scheduling,shieldedInstanceConfig,disks,reservationAffinity,resourcePolicies)"

    gcloud compute disks list \
      --quiet \
      --project="<project-id>" \
      --filter="zone:(<zone>) AND name:(<boot-disk> <data-disk-1> <data-disk-2>)" \
      --format="json(id,name,sizeGb,type,status,architecture,guestOsFeatures,licenses,labels,resourcePolicies,diskEncryptionKey,provisionedIops,provisionedThroughput,replicaZones,users,multiWriter)"
    ```

2.  For each attached disk, inspect Resource Manager tag bindings using the
    numeric `PROJECT_NUMBER` and numeric disk `id`:

    ```bash
    gcloud resource-manager tags bindings list \
      --quiet \
      --parent="//compute.googleapis.com/projects/${PROJECT_NUMBER}/zones/<zone>/disks/<disk-id>" \
      --location="<zone>" \
      --format="json"
    ```

3.  Verify that the boot disk `guestOsFeatures` includes `GVNIC` and
    `UEFI_COMPATIBLE`, and connect to the running source Gen2 VM over
    Identity-Aware Proxy (IAP) SSH to verify pre-cutover guest readiness and
    record baseline application data checksums. Confirm that `/etc/fstab` and
    `/etc/lvm/devices/system.devices` do not pin `/dev/sd*` or `scsi-*` paths,
    that `/boot/config-$(uname -r)` or `/proc/config.gz` (or the `initramfs` or
    `initrd` image inspected with `lsinitramfs` or `lsinitrd`) includes `nvme`
    and `gve`, and that any workload data integrity check or optional
    `checksums.sha256` manifest on attached data volumes verifies cleanly before
    taking snapshots:

    ```bash
    gcloud compute ssh "<source-vm>" \
      --quiet \
      --project="<project-id>" \
      --zone="<zone>" \
      --tunnel-through-iap \
      --strict-host-key-checking=yes \
      --command="cat /etc/fstab; test -f /etc/lvm/devices/system.devices && sudo cat /etc/lvm/devices/system.devices; (grep -E 'CONFIG_(BLK_DEV_NVME|NVME_CORE|GVE)=' /boot/config-\$(uname -r) 2>/dev/null || zgrep -E 'CONFIG_(BLK_DEV_NVME|NVME_CORE|GVE)=' /proc/config.gz 2>/dev/null || true); (sudo lsinitramfs /boot/initrd.img-\$(uname -r) 2>/dev/null || sudo lsinitrd /boot/initramfs-\$(uname -r).img 2>/dev/null || sudo lsinitrd 2>/dev/null || true) | grep -E 'nvme|gve' || true; findmnt --real -o TARGET,SOURCE,FSTYPE,OPTIONS; for f in /mnt/*/checksums.sha256; do if [ -f \"\$f\" ]; then (cd \"\$(dirname \"\$f\")\" && sha256sum -c checksums.sha256); fi; done"
    ```

    If `/etc/fstab` or `/etc/lvm/devices/system.devices` still references
    `/dev/sd*` or `/dev/disk/by-id/scsi-*`, remediate those files to use `UUID=`
    or `/dev/disk/by-id/google-<device-name>` with `nofail` on non-boot data
    mounts before proceeding to Step 2.

### Step 2: Create Stage-1 baseline snapshots while the source VM is online

Create the Stage-1 baseline snapshot (`<disk-name>-s1-${RUN_TS}`) for the boot
disk and every attached data disk in the regional `--storage-location` while the
source Gen2 VM remains online and serving traffic. Do not run `fsfreeze` during
Stage-1 baseline snapshots. Stage 1 transfers the bulk volume blocks into the
Compute Engine snapshot chain so the subsequent offline cutover snapshot copies
only incremental changed blocks:

```bash
for DISK_NAME in <boot-disk> <data-disk-1> <data-disk-2>; do
  gcloud compute snapshots create "${DISK_NAME}-s1-${RUN_TS}" \
    --quiet \
    --project="<project-id>" \
    --source-disk="${DISK_NAME}" \
    --source-disk-zone="<zone>" \
    --storage-location="<region>" \
    --labels="migration_stage=stage-1-baseline,source_vm=<source-vm>"
done
```

Verify that every Stage-1 snapshot reaches `status: READY`:

```bash
gcloud compute snapshots list \
  --quiet \
  --project="<project-id>" \
  --filter="name ~ -s1-${RUN_TS}$" \
  --format="table(name,status,diskSizeGb,storageBytes,creationTimestamp)"
```

### Step 3: Quiesce the workload, stop the VM, and create Stage-2 snapshots

1.  **Offline two-stage VM cutover (default for full Gen2-to-Gen4 VM
    migration):** Cleanly stop the application or database service inside the
    guest if needed, then stop the source Gen2 VM so the operating system
    flushes all filesystem buffers and unmounts volumes cleanly:

    ```bash
    gcloud compute instances stop "<source-vm>" \
      --quiet \
      --project="<project-id>" \
      --zone="<zone>"

    gcloud compute instances describe "<source-vm>" \
      --quiet \
      --project="<project-id>" \
      --zone="<zone>" \
      --format="value(status)"
    ```

    Confirm that the instance status is `TERMINATED` before creating Stage-2
    snapshots.

2.  **Online data-disk-only cutover variant (only when migrating a non-boot data
    disk without recreating the VM):** Quiesce the application, freeze the
    mounted filesystem with `sudo fsfreeze -f <mount-point>`, take the Stage-2
    snapshot of the data disk, and immediately unfreeze the filesystem inside an
    `EXIT` trap (`sudo fsfreeze -u <mount-point>`) before detaching the source
    data disk.

3.  **Create Stage-2 incremental snapshots:** Create `<disk-name>-s2-${RUN_TS}`
    for each disk in the same `--storage-location="<region>"`:

    ```bash
    for DISK_NAME in <boot-disk> <data-disk-1> <data-disk-2>; do
      gcloud compute snapshots create "${DISK_NAME}-s2-${RUN_TS}" \
        --quiet \
        --project="<project-id>" \
        --source-disk="${DISK_NAME}" \
        --source-disk-zone="<zone>" \
        --storage-location="<region>" \
        --labels="migration_stage=stage-2-cutover,source_vm=<source-vm>"
    done
    ```

    Confirm that every Stage-2 snapshot reaches `status: READY`:

    ```bash
    gcloud compute snapshots list \
      --quiet \
      --project="<project-id>" \
      --filter="name ~ -s2-${RUN_TS}$" \
      --format="table(name,status,diskSizeGb,storageBytes,creationTimestamp)"
    ```

### Step 4: Create target Hyperdisk volumes and transfer disk policies

Load
[references/cutover-and-metadata-preservation.md](references/cutover-and-metadata-preservation.md)
and create each target Hyperdisk volume from its corresponding Stage-2 snapshot
(`<disk-name>-s2-${RUN_TS}`):

1.  **Create each target Hyperdisk volume:** Pass only the performance flags
    supported by the target Hyperdisk type, such as `--provisioned-iops` and
    `--provisioned-throughput` for `hyperdisk-balanced`, `--provisioned-iops`
    only for `hyperdisk-extreme`, and `--provisioned-throughput` only for
    `hyperdisk-throughput`, along with preserved `--labels` and `--kms-key` when
    present on the source Persistent Disk:

    ```bash
    # Boot Hyperdisk example (hyperdisk-balanced using default baseline IOPS and
    # throughput):
    gcloud compute disks create "<target-boot-hd>" \
      --quiet \
      --project="<project-id>" \
      --zone="<zone>" \
      --type="hyperdisk-balanced" \
      --size="<boot-size-gib>GB" \
      --source-snapshot="<boot-disk>-s2-${RUN_TS}" \
      --labels="<preserved-boot-disk-labels>"

    # Data Hyperdisk example (hyperdisk-balanced with explicit provisioned IOPS
    # and throughput):
    gcloud compute disks create "<target-data-hd>" \
      --quiet \
      --project="<project-id>" \
      --zone="<zone>" \
      --type="<target-hyperdisk-type>" \
      --size="<data-size-gib>GB" \
      --source-snapshot="<data-disk>-s2-${RUN_TS}" \
      --provisioned-iops="<target-iops>" \
      --provisioned-throughput="<target-throughput-mibps>" \
      --labels="<preserved-data-disk-labels>"
    ```

2.  **Transfer snapshot schedule `resourcePolicies`:** `gcloud compute disks
    create --source-snapshot` does not copy `resourcePolicies` from the source
    Persistent Disk. For each disk whose Step 1 manifest recorded one or more
    regional snapshot schedule policies, attach each policy name to the new
    Hyperdisk and detach it from the stopped source Persistent Disk so only the
    active production volume runs scheduled snapshots:

    ```bash
    gcloud compute disks add-resource-policies "<target-data-hd>" \
      --quiet \
      --project="<project-id>" \
      --zone="<zone>" \
      --resource-policies="<policy-name>"

    gcloud compute disks remove-resource-policies "<source-data-disk>" \
      --quiet \
      --project="<project-id>" \
      --zone="<zone>" \
      --resource-policies="<policy-name>"
    ```

3.  **Recreate Resource Manager tag bindings:** If Step 1 discovered Resource
    Manager tag bindings on a source Persistent Disk, resolve the new
    Hyperdisk's numeric `id` and bind each `tagValue` to the new Hyperdisk:

    ```bash
    NEW_DISK_ID="$(gcloud compute disks describe "<target-data-hd>" \
      --quiet \
      --project="<project-id>" \
      --zone="<zone>" \
      --format="value(id)")"

    gcloud resource-manager tags bindings create \
      --quiet \
      --tag-value="<tagValues/1234567890>" \
      --parent="//compute.googleapis.com/projects/${PROJECT_NUMBER}/zones/<zone>/disks/${NEW_DISK_ID}" \
      --location="<zone>"
    ```

### Step 5: Create the target Gen4 VM and verify NVMe, gVNIC, and data integrity

1.  **Apply the internal IP cutover strategy:** Follow the network identity
    option selected in the migration plan (see the `Internal IP address cutover
    procedures` section of
    [references/cutover-and-metadata-preservation.md](references/cutover-and-metadata-preservation.md)
    when promoting and reassigning the source Gen2 VM's internal IP address). In
    side-by-side IP mode, create the Gen4 VM on the same `--subnet` with a new
    ephemeral internal IP address while the stopped Gen2 VM retains its original
    IP address for instant rollback.

2.  **Extract any multi-line startup script and create the target Gen4 VM:** If
    the source VM's `metadata.items` contains a `startup-script`, write it to a
    temporary file outside the repository working tree and pass it with
    `--metadata-from-file="startup-script=<temp-path>"` to preserve newlines and
    shell quoting. Attach the boot Hyperdisk and every data Hyperdisk with their
    original `device-name`, `auto-delete`, and `mode` settings, set
    `nic-type=GVNIC`, and carry over the service account, scopes, network tags,
    labels, metadata keys such as `enable-guest-attributes=TRUE` and
    `enable-oslogin=TRUE`, Shielded VM flags, and scheduling settings documented
    in
    [references/cutover-and-metadata-preservation.md](references/cutover-and-metadata-preservation.md):

    ```bash
    gcloud compute instances create "<target-gen4-vm>" \
      --quiet \
      --project="<project-id>" \
      --zone="<zone>" \
      --machine-type="<target-machine-type>" \
      --network-interface="subnet=<subnet-name>,nic-type=GVNIC,no-address" \
      --service-account="<service-account-email>" \
      --scopes="<comma-separated-scopes>" \
      --tags="<comma-separated-tags>" \
      --labels="<comma-separated-labels>" \
      --metadata="enable-guest-attributes=TRUE,enable-oslogin=TRUE" \
      --metadata-from-file="startup-script=<temp-startup-script-path>" \
      --disk="name=<target-boot-hd>,boot=yes,device-name=<boot-device-name>,auto-delete=<yes-or-no>,mode=rw" \
      --disk="name=<target-data-hd-1>,boot=no,device-name=<data-device-name-1>,auto-delete=<yes-or-no>,mode=rw" \
      --shielded-secure-boot \
      --shielded-vtpm \
      --shielded-integrity-monitoring
    ```

    Omit `--metadata-from-file="startup-script=<temp-startup-script-path>"` when
    the source VM does not define a `startup-script` metadata key. Omit
    `--shielded-secure-boot` when the source VM's
    `shieldedInstanceConfig.enableSecureBoot` is `false`. Add additional
    `--disk` flags for each remaining data Hyperdisk on multi-disk instances.

3.  **Verify guest host keys, NVMe block devices, gVNIC driver, mounts, and file
    checksums:** Wait until `google-guest-agent` publishes the new Gen4 VM's
    host keys to Compute Engine guest attributes, then connect over IAP SSH with
    `--strict-host-key-checking=yes` and verify that:
    - All disks attach as NVMe namespaces (`/dev/nvme*n*`) and expose matching
      `/dev/disk/by-id/google-<device-name>` symlinks.
    - The primary network interface binds the `gvnic` (`gve`) PCI driver.
    - `findmnt --real` reports every expected data mount point mounted cleanly.
    - Workload data integrity checks and any optional `checksums.sha256`
      manifests on the mounted Hyperdisk volumes pass verification.

    ```bash
    # Poll until guest attributes publish hostkeys/ on first boot (up to 60s):
    HOSTKEYS_READY=false
    for ATTEMPT in $(seq 1 30); do
      if gcloud compute instances get-guest-attributes "<target-gen4-vm>" \
        --quiet \
        --project="<project-id>" \
        --zone="<zone>" \
        --query-path="hostkeys/" >/dev/null 2>&1; then
        HOSTKEYS_READY=true
        break
      fi
      sleep 2
    done
    [[ "${HOSTKEYS_READY}" == "true" ]] || {
      echo "Timed out waiting for hostkeys/ guest attributes on <target-gen4-vm>" >&2
      exit 1
    }

    gcloud compute ssh "<target-gen4-vm>" \
      --quiet \
      --project="<project-id>" \
      --zone="<zone>" \
      --tunnel-through-iap \
      --strict-host-key-checking=yes \
      --command="uname -r; lsblk -o NAME,MODEL,SIZE,TYPE,FSTYPE,UUID,MOUNTPOINTS; ls -l /dev/disk/by-id/; basename \"\$(readlink -f /sys/class/net/\$(ip -o -4 route show to default | awk '{print \$5}')/device/driver)\"; findmnt --real -o TARGET,SOURCE,FSTYPE,OPTIONS; for f in /mnt/*/checksums.sha256; do if [ -f \"\$f\" ]; then (cd \"\$(dirname \"\$f\")\" && sha256sum -c checksums.sha256); fi; done"
    ```

4.  **Render the migration summary report:** Load
    [assets/migration-summary-template.md](assets/migration-summary-template.md)
    and populate every section with the Stage-1 and Stage-2 snapshot metrics,
    target Hyperdisk configuration and policy transfers, Gen4 instance details,
    and post-cutover verification output. Remind the user that the stopped Gen2
    VM and source Persistent Disks remain intact for instant rollback until the
    post-cutover validation window completes.
