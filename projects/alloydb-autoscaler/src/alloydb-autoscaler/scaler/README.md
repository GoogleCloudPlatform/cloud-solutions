# AlloyDB Autoscaler

![AlloyDB Autoscaler](../../../resources/hero-image.jpg)

Automatically increase or reduce the size of an AlloyDB read pool instance.

[Home](../../../README.md) ·
[Scaler component](../scaler/README.md) ·
[Poller component](../poller/README.md) ·
[Forwarder component](../forwarder/README.md) ·
[Terraform configuration](../../../terraform/README.md)

## Table of Contents

-   [Table of Contents](#table-of-contents)
-   [Overview](#overview)
-   [Scaling parameters](#scaling-parameters)
-   [Scaling profiles](#scaling-profiles)
-   [Scaling rules](#scaling-rules)
-   [Scaling methods](#scaling-methods)
-   [Scaling adjustments](#scaling-adjustments)
-   [Downstream messaging](#downstream-messaging)
-   [Troubleshooting](#troubleshooting)

## Overview

The Scaler component receives a message from the Poller component that includes
the configuration parameters and the utilization metrics for a single
AlloyDB read pool instance. It compares the metric values with the recommended
thresholds and determines whether the instance should be scaled, the number of
nodes to which it should be scaled, and adjusts the number of nodes in the read
pool accordingly.

The sequence of operations is as follows:

1.  [Scaling parameters](#scaling-parameters) are received from the Poller
    component.
1.  [Scaling rules](#scaling-rules) are evaluated with these parameters to
    establish whether scaling is needed.
1.  A calculation according to one of the [scaling methods](#scaling-methods) is
    applied to establish by how much the cluster should scale.
1.  [Scaling adjustments](#scaling-adjustments) are made to ensure the cluster
    remains within valid, configured, and/or recommended limits.
1.  Optionally, a [downstream message](#downstream-messaging) is sent via
    Pub/Sub to enable integration with other systems or platforms.

## Scaling parameters

As opposed to the Poller component, the Scaler component does not need any user
configuration. The parameters that the Scaler receives are a combination of the
[configuration parameters][autoscaler-poller-parameters] used by the Poller
component, the AlloyDB instance metrics, and a number of other characteristics
of the AlloyDB instance.

The following is an example of the message sent from the Poller to the Scaler.

```json
{
    "info": {
        "projectId": "alloydb-app-project-id",
        "regionId": "us-central1",
        "clusterId": "alloydb-cluster",
        "instanceId": "alloydb-read-pool-instance",
        "resourcePath": "projects/alloydb-app-project-id/locations/us-central1/clusters/alloydb-cluster/instances/alloydb-read-pool-instance"
    },
    "scalingConfig": {
        "units": "NODES",
        "minSize": 3,
        "maxSize": 10,
        "scalingMethod": "STEPWISE",
        "stepSize": 1,
        "scaleInCoolingMinutes": 10,
        "scaleOutCoolingMinutes": 10,
        "scalerPubSubTopic": "projects/alloydb-app-project-id/topics/scaler-topic"
    },
    "stateConfig": {
        "stateProjectId": "alloydb-app-project-id",
        "stateDatabase": {
            "name": "firestore"
        }
    },
    "metrics": {
        "cpuMaximumUtilization": 0.0407647797216877,
        "cpuAverageUtilization": 0.037610349716960284,
        "connectionsTotal": 60,
        "connectionsMax": 1000,
        "connectionsUtilization": 0.06
    },
    "metadata": {
        "currentSize": 3,
        "nodeCount": 3,
        "cpuCount": 4,
        "instanceType": "READ_POOL"
    }
}
```

Notice the `scalingProfile` parameter, which is described in more detail in the
following section, [scaling-profiles](#scaling-profiles).

## Scaling profiles

A scaling profile consists of a combination of scaling rules that, when grouped
together, define the metrics that will be evaluated to reach a scaling decsion.
One of the following scaling profiles may be provided:

-   `DEFAULT`
-   `CUSTOM` (see section [custom-scaling](#custom-scaling))

The `DEFAULT` profile includes rules for scaling on CPU as well as connection
utilization. Please see the following section for more details on how these
[scaling rules](#scaling-rules) are evaluated.

You can create a new scaling profile by copying one of the existing scaling
profiles in the
[profiles directory](./scaling-profiles/profiles.ts) and
adapting it to suit your needs. This profile will be loaded if you specify its
name using the `scalingProfile` parameter in your configuration.

### Custom scaling

You can configure custom scaling by using the scaling profile `CUSTOM`, and
supplying an array of scaling rules in the user-supplied configuration. An
example of rules supplied in JSON as part of a custom scaling profile is as
follows:

```json
[
  {
    "scalingRules": [
      {
        "name": "customCpuUtilizationScaleOut",
        "conditions": {
          "all": [
            {
              "fact": "cpuAverageUtilization",
              "operator": "greaterThan",
              "value": 70
            }
          ]
        },
        "event": {
          "type": "OUT",
          "params": {
            "message": "High average CPU utilization",
            "scalingMetrics": ["cpuAverageUtilization"]
          }
        }
      },
      {
        "name": "customCpuUtilizationScaleIn",
        "conditions": {
          "all": [
            {
              "fact": "cpuAverageUtilization",
              "operator": "lessThan",
              "value": 60
            }
          ]
        },
        "event": {
          "type": "IN",
          "params": {
            "message": "Low average CPI utilization",
            "scalingMetrics": ["cpuAverageUtilization"]
          }
        }
      },
      // Additional rules may be added here
    ]
  }
]
```

These rules will be passed from the Poller to the Scaler and evaluated to inform
scaling decisions.

These custom rules must used metrics that are already registered by the Poller.
In order to add new metrics, these must be added to the
[reader-factory](../poller/alloydb-metrics-reader-factory.ts).

## Scaling rules

The Scaler component uses a [Rules Engine][rules-engine] to evaluate a set of
parameterized rules according to a set of metrics and other parameters that it
receives from the Poller. Each rule is evaluated, and the results of these
evaluations are combined to form a scaling decision, which may be `IN`, `OUT`,
or `NONE`.

The rules are represented as JavaScript Objects within the Autoscaler codebase,
and can be found [here](./scaling-profiles/rules.ts).

The following is an annotated example of one of the included rules. This rule
triggers a scale-out if the average CPU utilization (i.e. across all read pool
nodes) is greater than 80%.

```typescript
export const CPU_HIGH_AVERAGE_UTILIZATION = {
  name: 'cpuHighAverageUtilization',
  conditions: {
    all: [
      {
        // The Cloud Monitoring metric name.
        fact: 'cpuAverageUtilization',
        // The comparison operator.
        operator: 'greaterThan',
        // The threshold for the rule to evaluate as TRUE.
        value: 0.8,
      },
    ],
  },
  event: {
    // The scaling decision should this rule evaluate as TRUE. In this case,
    // it will scale out (SCALE_OUT).
    type: AutoscalerScalingDirection.SCALE_OUT,
    params: {
      // The string to use in the Cloud Logging message when the rule fires.
      message: 'high average CPU utilization',
      // The metric(s) to use in scaling calculations.
      scalingMetrics: ['cpuAverageUtilization'],
    },
  },
};
```

The values in these files may be modified to alter the behaviour of the
Autoscaler. Thorough testing is recommended.

## Scaling methods

The Scaler component supports two scaling methods out of the box:

-   [STEPWISE](../../autoscaler-core/scaler/scaling-methods/stepwise-method.ts):
    This is the default method used by the Scaler. It suggests adding or
    removing nodes using a fixed step amount defined by the parameter
    `stepSize`.

-   [DIRECT](../../autoscaler-core/scaler/scaling-methods/direct-method.ts):
    This method suggests scaling to the number of nodes specified by the
    `maxSize` parameter. It does NOT take in account the current utilization
    metrics. It is useful to scale an instance in preparation for a batch job
    and and to scale it back after the job is finished.

-   [LINEAR](../../autoscaler-core/scaler/scaling-methods/linear-method.ts):
    This method suggests scaling to the number of nodes calculated with a simple
    linear cross-multiplication between the threshold metric and its current
    utilization. In other words, the new number of nodes divided by the current
    number of nodes is equal to the scaling metric value divided by the scaling
    metric threshold value. Using this method, the new number of nodes is
    [directly proportional][directly-proportional] to the current resource
    utilization and the threshold. The proposed change size can be limited using
    `scaleInLimit` and `scaleOutLimit`, where the variation in the node count in
    a single iteration will not exceed by these limits when scaling in or out
    respectively.

The selected scaling method will produce a suggested size to which the cluster
should be scaled. This suggested size then undergoes some final checks and may
be adjusted prior to the actual scaling request. These are detailed in the
following section.

## Scaling adjustments

Before issuing an AlloyDB API request to scale in or out, the suggested size
generated by evaluating the appropriate scaling method is checked as follows:

1.  Ensure the proposed change is withing the configured `stepSize` for
    `STEPWISE` or within `scaleInLimit` and `scaleOutLimit` for `LINEAR`.
1.  Ensure the proposed size is within the configured minimum and maximum node
    sizes.

As a result of the above checks, the suggested size may be adjusted.
Additionally, checks are done to determine whether the scaling API call can be
executed:

1.  Ensure that the last scale in or out operation is not within cooldown time.

## Downstream messaging

A downstream application is a system that receives information from the
Autoscaler.

When certain events happens, the Autoscaler can publish messages to a PubSub
topic. Downstream applications can
[create a subscription][pub-sub-create-subscription] to that topic and
[pull the messages][pub-sub-receive] to process them further.

This feature is disabled by default. To enable it, specify
`projects/${projectId}/topics/downstream-topic` as the value of the
`downstreamPubSubTopic` parameter in the
[Poller configuration](../poller/README.md#configuration-parameters). Make sure
you replace the placeholder `${projectId}` with your actual project ID.

The topic is created at deployment time as specified in the
[base module Terraform config](../../../terraform/autoscaler-core/modules/autoscaler-base/main.tf).

### Message structure

The following is an example of a message published by the Autoscaler.

```json
[
  {
    "ackId": "U0RQBhYsXUZIUTcZCGhRDk9eIz81IChFEQMIFAV8fXFDRXVeXhoHUQ0ZcnxpfT5TQlUBEVN-VVsRDXptXG3VzfqNRF9BfW5ZFAgGQ1V7Vl0dDmFeWF3SjJ3whoivS3BmK9OessdIf77en9luZiA9XxJLLD5-LSNFQV5AEkwmFkRJUytDCypYEU4EISE-MD5F",
    "ackStatus": "SUCCESS",
    "message": {
      "attributes": {
        "event": "SCALING",
        "googclient_schemaencoding": "JSON",
        "googclient_schemaname": "projects/alloydb-app-project/schemas/downstream-schema",
        "googclient_schemarevisionid": "207c0c97"
      },
      "data": "ewogICAgImluZm8iOiB7CiAgICAgICAgInByb2plY3RJZCI6ICJhbGxveWRiLWF1dG9zY2FsZXIiLAogICAgICAgICJyZWdpb25JZCI6ICJ1cy1jZW50cmFsMSIsCiAgICAgICAgInJlc291cmNlUGF0aCI6ICJwcm9qZWN0cy9hbGxveWRiLWF1dG9zY2FsZXIvbG9jYXRpb25zL3VzLWNlbnRyYWwxL2NsdXN0ZXJzL2F1dG9zY2FsZXItdGFyZ2V0LWFsbG95ZGItY2x1c3Rlci9pbnN0YW5jZXMvYXV0b3NjYWxlci10YXJnZXQtYWxsb3lkYi1yZWFkLXBvb2wiLAogICAgICAgICJjbHVzdGVySWQiOiAiYXV0b3NjYWxlci10YXJnZXQtYWxsb3lkYi1jbHVzdGVyIiwKICAgICAgICAiaW5zdGFuY2VJZCI6ICJhdXRvc2NhbGVyLXRhcmdldC1hbGxveWRiLXJlYWQtcG9vbCIKICAgIH0sCiAgICAic2NhbGluZ0NvbmZpZyI6IHsKICAgICAgICAidW5pdHMiOiAiTk9ERVMiLAogICAgICAgICJtaW5TaXplIjogMywKICAgICAgICAibWF4U2l6ZSI6IDEwLAogICAgICAgICJzY2FsaW5nTWV0aG9kIjogIlNURVBXSVNFIiwKICAgICAgICAic3RlcFNpemUiOiAxLAogICAgICAgICJzY2FsZUluQ29vbGluZ01pbnV0ZXMiOiAxMCwKICAgICAgICAic2NhbGVPdXRDb29saW5nTWludXRlcyI6IDEwLAogICAgICAgICJzY2FsZXJQdWJTdWJUb3BpYyI6ICJwcm9qZWN0cy9hbGxveWRiLWF1dG9zY2FsZXIvdG9waWNzL3NjYWxlci10b3BpYyIKICAgIH0sCiAgICAic3RhdGVDb25maWciOiB7CiAgICAgICAgInN0YXRlUHJvamVjdElkIjogImFsbG95ZGItYXV0b3NjYWxlciIsCiAgICAgICAgInN0YXRlRGF0YWJhc2UiOiB7CiAgICAgICAgICAgICJuYW1lIjogImZpcmVzdG9yZSIKICAgICAgICB9CiAgICB9LAogICAgIm1ldHJpY3MiOiB7CiAgICAgICAgImNwdU1heGltdW1VdGlsaXphdGlvbiI6IDAuMDQwNzY0Nzc5NzIxNjg3NywKICAgICAgICAiY3B1QXZlcmFnZVV0aWxpemF0aW9uIjogMC4wMzc2MTAzNDk3MTY5NjAyODQsCiAgICAgICAgImNvbm5lY3Rpb25zVG90YWwiOiA2MCwKICAgICAgICAiY29ubmVjdGlvbnNNYXgiOiAxMDAwLAogICAgICAgICJjb25uZWN0aW9uc1V0aWxpemF0aW9uIjogMC4wNgogICAgfSwKICAgICJtZXRhZGF0YSI6IHsKICAgICAgICAiY3VycmVudFNpemUiOiAzLAogICAgICAgICJub2RlQ291bnQiOiAzLAogICAgICAgICJjcHVDb3VudCI6IDQsCiAgICAgICAgImluc3RhbmNlVHlwZSI6ICJSRUFEX1BPT0wiCiAgICB9Cn0",
      "messageId": "8437946659663924",
      "publishTime": "2024-02-16T16:39:49.252Z"
    }
  }
]
```

Notable attributes are:

-   **message.attributes.event:** the name of the event for which this message
    was triggered. The Autoscaler publishes a message when it scales a
    AlloyDB read pool. The name of that event is `'SCALING'`. You can define
    [custom messages](#custom-messages) for your own event types.
-   **message.attributes.googclient_schemaname:** the
    [Pub/Sub schema][pub-sub-schema] defining the format that the data field
    must follow. The schema represents the contract between the message producer
    (Autoscaler) and the message consumers (downstream applications). Pub/Sub
    enforces the format. The default schema is defined as a Protocol Buffer in
    the file [downstream.schema.proto](../schema/downstream_event.proto).
-   **message.attributes.googclient_schemaencoding:** consumers will receive the
    data in the messages encoded as Base64 containing JSON.
-   **message.publishTime:** timestamp when the message was published
-   **message.data:** the message payload encoded as Base64 containing a JSON
    string. In the example, the [decoded][base-64-decode] string contains the
    following data:

```json
{
  "projectId": "alloydb-app-project-id",
  "regionId": "us-central1",
  "clusterId": "alloydb-cluster",
  "instanceId": "alloydb-read-pool-instance",
  "resourcePath": "projects/alloydb-app-project-id/locations/us-central1/clusters/alloydb-cluster/instances/alloydb-read-pool-instance",

  "currentSize": 5,
  "suggestedSize": 6,
  "units": "NODES",

  "metrics": [
    {
      "name": "cpuMaximumUtilization",
      "value": 0.22514979024681617
    },
    {
      "name": "cpuAverageUtilization",
      "value": 0.17459131709152276
    },
    {
      "name": "connectionsTotal",
      "value": 60
    },
    {
      "name": "connectionsMax",
      "value": 1000
    },
    {
      "name": "connectionsUtilization",
      "value": 0.06
    }
  ]
}
```

### Custom messages

Before defining a custom message, consider if your use case can be solved by
[log-based metrics][log-based-metrics].

The AlloyDB Autoscaler produces verbose structured logging for all its actions.
These logs can be used through log-based metrics to create
[charts and alerts in Cloud Monitoring][charts-and-alerts]. In turn, alerts can
be notified through several different [channels][notification-channels]
including Pub/Sub, and managed through [incidents][alert-incidents].

If your use case can be better solved by a custom downstream message, then this
section explains how to define one, which implies modifying the Scaler code.

To publish a new event as a downstream message:

-   Choose a unique name for your event. The convention is an all-caps
    alphanumeric + underscores ID with a verb. e.g. `'SCALING'`
-   Call the Scaler function `publishDownstreamEvent`. For an example, look at
    the [Scaler](../../autoscaler-core/scaler/scaler-builder.ts)
    `ScalerFunctionBuilder` class method.

In case you need to add fields to the message payload:

1.  Add your custom fields to the
    [Pub/Sub schema protobuf](../schema/downstream_event.proto). Your custom
    fields must use [field numbers][proto-field-numbers] over 1000. Field
    numbers from 1 to 1000 are [reserved][proto-reserved] for future Autoscaler
    enhancements. Make sure field numbers are unique within your org and not
    reused if previously deleted.

1.  Run `terraform apply` to update the downstream Pub/Sub topic with the new
    schema.

1.  Create and call a function similar to the
    [Scaler](../../autoscaler-core/scaler/scaler-builder.ts)
    `publishDownstreamEvent()`. In this function you populate the message
    payload with the default fields and your new custom fields.

### Consuming messages

The payload of messages sent downstream from the Autoscaler is plain JSON
encoded with Base64, so you do not need to use the protobuf library for
receiving messages. See [this article][pub-sub-receive] for an example.

However, if you want to validate the received message against the Protobuf
schema, you can follow [this example][pub-sub-receive-proto].

## Troubleshooting

### Poller can't read metrics

For example:

```none
Unable to retrieve metrics for projects/[PROJECT_ID]/locations/us-central1/clusters/[ALLOYDB_CLUSTER_ID]/instances/[ALLOYDB_INSTANCE_ID]:
Error: 7 PERMISSION_DENIED: Permission monitoring.timeSeries.list denied (or the resource may not exist).
```

-   Service account is missing permissions
    -   `poller-sa@{PROJECT_ID}.gserviceaccount.com` for Cloud Run functions, or
    -   `scaler-sa@{PROJECT_ID}.gserviceaccount.com` for Kubernetes deployment
        requires
        -   `alloydb.instances.get`,
        -   `alloydb.instances.list`,
        -   `monitoring.timeSeries.list`
-   [GKE Workload Identity](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity)
    is not correctly configured
-   Incorrectly configured AlloyDB project, cluster or instance ID

### Scaler cannot access state database

For example:

```none
Failed to read from Spanner State storage:
projects/[PROJECT_ID]/instances/alloydb-autoscaler-state/databases/alloydb-autoscaler-state/tables/alloyDbAutoscaler:
Error: 7 PERMISSION_DENIED:
Caller is missing IAM permission spanner.sessions.create on resource projects/[PROJECT_ID]/instances/[SPANNER_STATE_INSTANCE]/databases/alloydb-autoscaler-state.
```

-   Scaler service account is missing permissions to Spanner or Firestore.
    -   `scaler-sa@{PROJECT_ID}.gserviceaccount.com`
-   Incorrect Spanner or Firestore details in configuration file.
-   [GKE Workload Identity](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity)
    is not correctly configured.

### Spanner state store results in an error

For example:

```none
Error: 5 NOT_FOUND: Database not found: projects/[PROJECT_ID]/instances/[SPANNER_STATE_INSTANCE]/databases/alloydb-autoscaler-state
```

-   State database is missing from Spanner state instance.

### Scaler cannot scale AlloyDB read pool instance(s)

```none
Unsuccessful scaling attempt: Error: 7 PERMISSION_DENIED:
Permission 'alloydb.instances.update' denied on 'projects/[PROJECT_ID]/locations/us-central1/clusters/[ALLOYDB_CLUSTER_ID]/instances/[ALLOYDB_INSTANCE_ID]'.
```

-   Scaler service account is missing `alloydb.instances.update` permissions to
    the AlloyDB instance.
    -   `scaler-sa@{PROJECT_ID}.gserviceaccount.com`
-   Incorrect AlloyDB instance specified in configuration file.
-   [GKE Workload Identity](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity)
    is not correctly configured

### Latency Spikes when Scaling in

-   The amount of compute capacity removed from the instance might be too large.
    -   Use the `scaleInLimit` parameter, when using `LINEAR` scaling method.
    -   Use the `stepSize` parameter, when using `STEPWISE` scaling method.
    -   Increase the `scaleInCoolingMinutes.`
    -   Set a larger `minSize` for the instance.

See the documentation on the [Poller parameters][autoscaler-poller-parameters]
for further details.

### Autoscaler is too reactive or not reactive enough

-   The "sweet spot" between thresholds is too narrow or too wide.
    -   Adjust the `thresholds` for the scaling profile.

<!-- LINKS: https://www.markdownguide.org/basic-syntax/#reference-style-links -->

[alert-incidents]:
    https://cloud.google.com/monitoring/alerts/log-based-incidents
[autoscaler-poller-parameters]: ../poller/README.md#configuration-parameters
[base-64-decode]: https://www.base64decode.org/
[charts-and-alerts]:
    https://cloud.google.com/logging/docs/logs-based-metrics#monitoring
[directly-proportional]:
    https://en.wikipedia.org/wiki/Proportionality_(mathematics)#Direct_proportionality
[log-based-metrics]: https://cloud.google.com/logging/docs/logs-based-metrics
[notification-channels]:
    https://cloud.google.com/monitoring/support/notification-options
[proto-field-numbers]: https://protobuf.dev/programming-guides/proto3/#assigning
[proto-reserved]: https://protobuf.dev/programming-guides/proto3/#fieldreserved
[pub-sub-create-subscription]:
    https://cloud.google.com/pubsub/docs/create-subscription#pubsub_create_push_subscription-nodejs
[pub-sub-receive-proto]:
    https://cloud.google.com/pubsub/docs/samples/pubsub-subscribe-proto-messages#pubsub_subscribe_proto_messages-nodejs_javascript
[pub-sub-receive]:
    https://cloud.google.com/pubsub/docs/publish-receive-messages-client-library#receive_messages
[pub-sub-schema]: https://cloud.google.com/pubsub/docs/schemas
[rules-engine]: https://github.com/CacheControl/json-rules-engine
