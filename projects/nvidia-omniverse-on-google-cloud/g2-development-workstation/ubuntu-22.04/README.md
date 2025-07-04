# NVIDIA RTX Virtual Workstation: G2 machine family (L4 GPUs), Ubuntu 22.04

This NVIDIA RTX Virtual Workstation is based on the
[Google Cloud Compute Engine G2 machine family](https://cloud.google.com/compute/docs/gpus#l4-gpus).
A VM based on the G2 machine family includes one to eigth NVIDIA L4 GPUs.

_G2 machine are not officially supported by NVIDIA for NVIDIA Omniverse
development_

To deploy a NVIDIA RTX Virtual Workstation on Google Cloud, you do the
following:

1.  Deploy an NVIDIA RTX Virtual Workstation (Ubuntu 22.04) in your project from
    the
    [Google Cloud Marketplace](https://cloud.google.com/marketplace/product/nvidia/nvidia-rtx-virtual-workstation-ubuntu-22).

1.  Connect to the NVIDIA RTX Virtual Workstation using SSH. For more
    information about connecting to a Compute Engine virtual machine (VM), see
    [Connect to Linux VMs](https://cloud.google.com/compute/docs/connect/standard-ssh).

1.  Clone this repository:

    ```bash
    git clone https://github.com/GoogleCloudPlatform/cloud-solutions && \
    cd cloud-solutions
    ```

1.  Run the `setup-workstation.sh` script on the NVIDIA RTX Virtual Workstation:

    ```bash
    projects/nvidia-omniverse-on-google-cloud/g2-development-workstation/ubuntu-22.04/setup-workstation.sh/setup-workstation.sh
    ```

    The `setup-workstation.sh` script does the following to the workstation for
    NVIDIA Omniverse application development:

    -   Verify that NVIDIA drivers are installed
    -   Install dependencies
    -   Install Docker
    -   Install NVIDIA Container Toolkit
    -   Install the desktop environment

## Connect to the NVIDIA RTX Virtual Workstation remote desktop

To connect to the NVIDIA RTX Virtual Workstation remote desktop, follow the
instructions in
[Create a virtual Windows workstation](https://cloud.google.com/compute/docs/virtual-workstation/linux#install_hp_anyware_software)
starting from the _Install HP Anyware software_ section. Ignore the steps prior
to the _Install HP Anyware software_ section because they guide you in creating
a VM, and you already created one.

Note: If you use Chrome Remote Desktop (CRD) to connect to the development
workstation remote desktop, you might experience suboptimal performance because
CRD doesn't support hardware acceleration.

## What's next

-   [Deploy NVIDIA Omniverse Kit Streaming applications on Google Cloud](../../kit-app-streaming/README.md).
