# AlloyDB Autoscaler

![AlloyDB Autoscaler](./resources/hero-image.jpg)

Automatically increase or reduce the size of AlloyDB read pool instances.

**Home** · [Scaler component](./alloydb-autoscaler/scaler/README.md) ·
[Poller component](./alloydb-autoscaler/poller/README.md) ·
[Forwarder component](./alloydb-autoscaler/forwarder/README.md) ·
[Terraform configuration](../terraform/README.md)

## Table of Contents

-   [Table of Contents](#table-of-contents)
-   [Overview](#overview)

## Overview

This directory contains the source code for the two main components of the
autoscaler: the Poller and the Scaler:

-   [Poller](./alloydb-autoscaler/poller/README.md)
-   [Scaler](./alloydb-autoscaler/scaler/README.md)

As well as the Forwarder, which is used in the
[distributed deployment model][distributed-docs]:

-   [Forwarder](./alloydb-autoscaler/forwarder/README.md)

[distributed-docs]: ../terraform/alloydb-autoscaler/cloud-functions/distributed/README.md
