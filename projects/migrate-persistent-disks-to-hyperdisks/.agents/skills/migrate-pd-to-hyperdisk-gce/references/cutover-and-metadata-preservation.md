# Cutover flag mapping, metadata preservation, and IP reassignment

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

Use this reference during Step 4 and Step 5 of a Compute Engine Persistent Disk
to Hyperdisk cutover to map captured source JSON attributes to `gcloud` creation
flags, transfer snapshot schedules and Resource Manager tags, and reassign
internal IP addresses.

## Contents

- [Fetching live Hyperdisk creation rules](#fetching-live-hyperdisk-creation-rules)
- [Disk attribute preservation and policy transfer](#disk-attribute-preservation-and-policy-transfer)
- [Per-Hyperdisk-type provisioning flag rules](#per-hyperdisk-type-provisioning-flag-rules)
- [Instance attribute preservation and flag mapping](#instance-attribute-preservation-and-flag-mapping)
- [Internal IP address cutover procedures](#internal-ip-address-cutover-procedures)

## Fetching live Hyperdisk creation rules

Confirm current Hyperdisk provisioning bounds, supported creation flags, and
snapshot-restore guidance from the official Compute Engine documentation before
creating target volumes:

```bash
curl --fail -sS -H "Accept: text/markdown" -L "<docs-url>"
gcloud compute disks create --help
gcloud compute instances create --help
```

Grounding sources:

- [Create a Hyperdisk volume](https://docs.cloud.google.com/compute/docs/disks/add-hyperdisk)
- [Change the type, placement, or location of a disk](https://docs.cloud.google.com/compute/docs/disks/migrate-to-hyperdisk)
- [Hyperdisk performance limits](https://docs.cloud.google.com/compute/docs/disks/hyperdisk-perf-limits)

## Disk attribute preservation and policy transfer

When creating a Hyperdisk from `--source-snapshot`, Compute Engine copies the
block data, boot disk `architecture`, `licenses`, and `guestOsFeatures` from the
snapshot, but does **not** copy disk labels, snapshot schedule
`resourcePolicies`, or Resource Manager tag bindings. Preserve each disk
attribute from the Step 1 `gcloud compute disks list` JSON manifest using the
mappings in the table below:

| Source disk JSON path | Target command or flag | Preservation rule |
| :--- | :--- | :--- |
| `sizeGb` | `gcloud compute disks create --size="<sizeGb>GB"` | Must be greater than or equal to the snapshot's `diskSizeGb` and the target Hyperdisk type's minimum capacity floor. |
| `labels` | `gcloud compute disks create --labels="k1=v1,k2=v2"` | Serialize `.labels \| to_entries \| map("\(.key)=\(.value)") \| join(",")` and pass to `--labels`. Omit `--labels` when `labels` is null. |
| `diskEncryptionKey.kmsKeyName` | `gcloud compute disks create --kms-key="<kms-key-uri>"` | Required when the source disk uses a customer-managed encryption key (CMEK). Ensure `service-<project-number>@compute-system.iam.gserviceaccount.com` holds `roles/cloudkms.cryptoKeyEncrypterDecrypter`. |
| `resourcePolicies[]` | `gcloud compute disks add-resource-policies` and `remove-resource-policies` | Extract the policy basename (`${policy_uri##*/}`), attach it to the new Hyperdisk with `add-resource-policies`, and remove it from the stopped source Persistent Disk with `remove-resource-policies` so the retained rollback disk does not accumulate duplicate scheduled snapshots. |
| Resource Manager tag bindings | `gcloud resource-manager tags bindings create` | Query the new Hyperdisk's numeric `id` (`gcloud compute disks describe --format="value(id)"`) and recreate each `tagValue` binding on `//compute.googleapis.com/projects/${PROJECT_NUMBER}/zones/<zone>/disks/${NEW_DISK_ID}`. |

Grounding sources:

- [gcloud compute disks create reference](https://docs.cloud.google.com/sdk/gcloud/reference/compute/disks/create)
- [gcloud compute disks add-resource-policies reference](https://docs.cloud.google.com/sdk/gcloud/reference/compute/disks/add-resource-policies)

## Per-Hyperdisk-type provisioning flag rules

Supply only the performance and placement flags supported by the target
Hyperdisk type during `gcloud compute disks create`:

| Target Hyperdisk type | Allowed performance and topology flags | Disallowed performance flags |
| :--- | :--- | :--- |
| `hyperdisk-balanced` | `--provisioned-iops`, `--provisioned-throughput` (both optional when default baseline suffices) | `--replica-zones` |
| `hyperdisk-balanced-high-availability` | `--provisioned-iops`, `--provisioned-throughput`, `--replica-zones="<zone-a>,<zone-b>"` | None |
| `hyperdisk-extreme` | `--provisioned-iops` | `--provisioned-throughput` (throughput scales with provisioned IOPS) |
| `hyperdisk-throughput` | `--provisioned-throughput` | `--provisioned-iops` (IOPS scale with provisioned throughput and Compute Engine does not support boot on this type) |
| `hyperdisk-ml` | `--provisioned-throughput` | `--provisioned-iops` (Compute Engine does not support boot on this type) |

Grounding sources:

- [About Hyperdisk Balanced](https://docs.cloud.google.com/compute/docs/disks/hd-types/hyperdisk-balanced)
- [About Hyperdisk Extreme](https://docs.cloud.google.com/compute/docs/disks/hd-types/hyperdisk-extreme)
- [About Hyperdisk Throughput](https://docs.cloud.google.com/compute/docs/disks/hd-types/hyperdisk-throughput)

## Instance attribute preservation and flag mapping

Map the source Gen2 VM's `gcloud compute instances describe` JSON manifest to
`gcloud compute instances create` flags for the target Gen4 VM:

| Source VM JSON path | Target `gcloud compute instances create` flag | Preservation rule |
| :--- | :--- | :--- |
| `disks[]` (`boot`, `deviceName`, `autoDelete`, `mode`) | `--disk="name=<target-hd>,boot=<yes\|no>,device-name=<deviceName>,auto-delete=<yes\|no>,mode=<rw\|ro>"` | Preserve `device-name` on every disk so `/dev/disk/by-id/google-<device-name>` symlinks match `/etc/fstab` and startup scripts. Map boolean `boot` and `autoDelete` (`true` to `yes`, `false` to `no`) and `mode` (`READ_WRITE` to `rw`, `READ_ONLY` to `ro`). |
| `networkInterfaces[0].subnetwork` | `--network-interface="subnet=<subnet-name>,nic-type=GVNIC,..."` | Extract the subnet basename (`${subnetwork_uri##*/}`) and always set `nic-type=GVNIC` on Gen4 machine series. Include `no-address` when the source VM has no external `accessConfigs`. |
| `serviceAccounts[0].email` and `scopes[]` | `--service-account="<email>"` and `--scopes="<s1>,<s2>"` | Preserve the attached workload service account and comma-joined OAuth scope URIs. |
| `tags.items[]` | `--tags="<tag1>,<tag2>"` | Preserve network firewall tags such as `allow-iap-ssh`. Omit `--tags` if `tags.items` is empty. |
| `labels` | `--labels="k1=v1,k2=v2"` | Preserve instance labels such as `environment`, `workload`, and cost-allocation keys, and update any generation-specific label value if appropriate. |
| `metadata.items[]` | `--metadata="k1=v1,..."` and `--metadata-from-file="startup-script=<path>"` | Preserve `enable-guest-attributes=TRUE` and `enable-oslogin=TRUE`. Write any multi-line `startup-script` value to a temporary file (`jq -r '.metadata.items[] \| select(.key=="startup-script") \| .value'`) and pass it with `--metadata-from-file` to preserve newlines. Omit `--metadata-from-file` when the source VM has no `startup-script`. |
| `shieldedInstanceConfig` | `--shielded-secure-boot` / `--no-shielded-secure-boot`, `--shielded-vtpm`, `--shielded-integrity-monitoring` | Match the source VM's `enableSecureBoot`, `enableVtpm`, and `enableIntegrityMonitoring` booleans. |
| `canIpForward` | `--can-ip-forward` | Include when `canIpForward` is `true`. |
| `deletionProtection` | `--deletion-protection` | Include when `deletionProtection` is `true`. |
| `scheduling` (`onHostMaintenance`, `automaticRestart`, `provisioningModel`) | `--maintenance-policy`, `--restart-on-failure`, `--provisioning-model` | Preserve non-default scheduling settings and omit Gen2-specific `nodeAffinities`. |

Grounding sources:

- [gcloud compute instances create reference](https://docs.cloud.google.com/sdk/gcloud/reference/compute/instances/create)
- [Use gVNIC](https://docs.cloud.google.com/compute/docs/networking/using-gvnic)

## Internal IP address cutover procedures

Choose the network identity strategy approved in the migration plan:

1.  **Option A — Side-by-side internal IP and DNS cutover (default for
    side-by-side rollback):**
    - Leave the stopped source Gen2 VM holding its original internal IP address
      (`networkInterfaces[0].networkIP`).
    - Create the target Gen4 VM on the same subnet (`subnet=<subnet-name>`)
      without `private-network-ip`, allowing Compute Engine to allocate a new
      internal IP address.
    - Validate the Gen4 VM over IAP SSH and switch traffic by updating Cloud DNS
      records or load-balancer backend groups.

2.  **Option B — Preserve the source internal IP address on the Gen4 VM:**
    - Before or after stopping the source Gen2 VM, promote its ephemeral
      internal IP address (`<source-ip>`) to a reserved static internal address
      in the same region and subnetwork:

      ```bash
      gcloud compute addresses create "<source-vm>-internal-ip" \
        --quiet \
        --project="<project-id>" \
        --region="<region>" \
        --subnet="<subnet-name>" \
        --addresses="<source-ip>"
      ```

    - Because a stopped Compute Engine instance continues to hold its assigned
      `networkIP` and Compute Engine does not permit changing `networkIP` within
      the same subnetwork, release `<source-ip>` without deleting the stopped
      Gen2 VM by moving its network interface (`nic0`) to a temporary holding
      subnetwork (`<holding-subnet-name>`) in the same VPC network and region.
      Ensure that `<holding-subnet-name>` already exists in the target VPC
      network and region before beginning cutover, then move `nic0` and create
      the Gen4 VM with the reserved static internal IP address:

      ```bash
      gcloud compute instances network-interfaces update "<source-vm>" \
        --quiet \
        --project="<project-id>" \
        --zone="<zone>" \
        --network-interface="nic0" \
        --subnetwork="<holding-subnet-name>"

      # When creating the Gen4 VM with the released static internal IP:
      --network-interface="subnet=<subnet-name>,nic-type=GVNIC,private-network-ip=<source-vm>-internal-ip,no-address"
      ```

Grounding sources:

- [Reserve a static internal IP address](https://docs.cloud.google.com/compute/docs/ip-addresses/reserve-static-internal-ip-address)
