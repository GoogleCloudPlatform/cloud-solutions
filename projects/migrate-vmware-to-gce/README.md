# Migrate VMware workloads to Compute Engine

This project contains Terraform configurations and guides for migrating
enterprise VMware vSphere workloads to
[Compute Engine](https://cloud.google.com/compute/docs) using
[Google Cloud VMware Engine](https://cloud.google.com/vmware-engine/docs) (GCVE)
and
[Migrate to Virtual Machines](https://cloud.google.com/migrate/virtual-machines/docs/5.0).

## Guides

Follow these step-by-step guides to provision the mock source data center and
execute the cutover migration to Google Cloud:

- [Set up the source environment (mock on-premises data center)](source/README.md)
- [Migrate VMware workload to Compute Engine using Cloud DNS cutover](dns-cutover/README.md)
