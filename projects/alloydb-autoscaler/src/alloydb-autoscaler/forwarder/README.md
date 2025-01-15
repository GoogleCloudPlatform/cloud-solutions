# AlloyDB Autoscaler

![AlloyDB Autoscaler](../../../resources/hero-image.jpg)

Forward messages from Cloud Scheduler to the Poller function topic.

[Home](../../../README.md) · [Scaler component](../scaler/README.md) ·
[Poller component](../poller/README.md) · **Forwarder component** ·
[Terraform configuration](../../../terraform/README.md)

## Table of Contents

-   [Table of Contents](#table-of-contents)
-   [Overview](#overview)
-   [Architecture](#architecture)
-   [Configuration parameters](#configuration-parameters)
    -   [Required](#required)

## Overview

The Forwarder function takes messages published to PubSub from Cloud Scheduler,
checks their JSON syntax and forwards them to the Poller PubSub topic. The topic
can belong to a different project from the Scheduler.

## Architecture

![architecture-forwarder](../../../resources/architecture-forwarder.png)

The AlloyDB instances reside in a given application project.

1.  Cloud Scheduler lives in the same project as the AlloyDB instances.

1.  Cloud Scheduler publishes its messages to the Forwarder topic in the same
    project.

1.  The Forwarder Cloud Function reads messages from the Forwarder topic, and

1.  Forwards them to the Polling topic. The Polling topic resides in a different
    project.

1.  The Poller function reads the messages from the polling topic and further
    continues the process as described in the
    [main architecture section](../../../terraform/alloydb-autoscaler/cloud-functions/README.md#architecture).

It is important to note that Autoscaler infrastructure is now distributed across
several projects. _The core components reside in the Autoscaler project_ An
instance of Cloud Scheduler, the Forwarder topic and the Forwarder Function
reside in each of the application projects.

## Configuration parameters

Using the Forward function forwards to the PubSub specified in the environment
variable `POLLER_TOPIC`.

### Required

| Key            | Description                                 |
| -------------- | ------------------------------------------- |
| `POLLER_TOPIC` | PubSub topic the Poller function listens on |
