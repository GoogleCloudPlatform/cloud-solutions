# AlloyDB Autoscaler

![AlloyDB Autoscaler](../../../resources/hero-image.jpg)

Retrieve metrics for one or more AlloyDB instances.

[Home](../../../README.md) · [Scaler component](../scaler/README.md) ·
**Poller component** · [Forwarder component](../forwarder/README.md) ·
[Terraform configuration](../../../terraform/README.md)

## Table of Contents

-   [Table of Contents](#table-of-contents)
-   [Overview](#overview)
-   [Configuration parameters](#configuration-parameters)
    -   [Required](#required)
    -   [Optional](#optional)
-   [State Database](#state-database)
-   [Example JSON configuration for Cloud Run functions](#example-json-configuration-for-cloud-run-functions)
-   [Example YAML ConfigMap for Kubernetes deployment](#example-yaml-configmap-for-kubernetes-deployment)

## Overview

The Poller component takes an array of AlloyDB instances and obtains load
metrics for each of them from [Cloud Monitoring][cloud-monitoring]. This
array may come from the payload of a Cloud PubSub message or from configuration
held in a [Kubernetes ConfigMap][configmap], depending on configuration.

Then for each AlloyDB instance it publishes a message via the specified Cloud
PubSub topic or via API call (in a Kubernetes configuration), which includes the
metrics and part of the configuration for the scaling operation.

The Scaler component receives the message, compares the metric values with the
recommended thresholds. If any of the values fall outside this range, the Scaler
component will adjust the number of nodes in the AlloyDB read pool instance
accordingly.

## Configuration parameters

The following are the configuration parameters consumed by the Poller component.
Some of these parameters are forwarded to the Scaler component as well.

In the case of the
[Cloud Run functions](../../../terraform/alloydb-autoscaler/cloud-functions/README.md#configuration)
deployment, the parameters are defined using the JSON payload of the PubSub
message that is published by the Cloud Scheduler job.

In the case of the
[Kubernetes deployment](../../../terraform/alloydb-autoscaler/gke/README.md#configuration),
the parameters are defined using a [Kubernetes ConfigMap][configmap] that is
loaded by the Kubernetes Cron job.

### Required

| Key          | Description                                                            |
| ------------ | ---------------------------------------------------------------------- |
| `projectId`  | Project ID of the AlloyDB read pool to be monitored by the Autoscaler  |
| `regionId`   | Region ID of the AlloyDB read pool to be monitored by the Autoscaler   |
| `clusterId`  | Cluster ID of the AlloyDB read pool to be monitored by the Autoscaler  |
| `instanceId` | Instance ID of the AlloyDB read pool to be monitored by the Autoscaler |

### Required for a Cloud Run functions deployment

| Key                 | Description                                                                                                                                               |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `scalerPubSubTopic` | PubSub topic for the Poller function to publish messages for the Scaler function. The topic must be in the format `projects/{projects}/topics/{topicId}`. |

### Optional

| Key                      | Default Value    | Description                                                                                                                                                                                                                                                        |
| ------------------------ | ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `units`                  | `NODES`         | Specifies the units for capacity. Currently `NODES` is the only valid unit.                                                                                                                                                                                       |
| `minSize`                | 1                | Minimum number of nodes to which the instance can be scaled IN.                                                                                                                                                                                |
| `maxSize`                | 10               | Maximum number of nodes to which the instance can be scaled OUT.                                                                                                                                                                               |
| `scalingMethod`          | `STEPWISE`       | Scaling method that should be used. Options are: `STEPWISE`, `DIRECT` and `LINEAR`. See the [scaling methods section][autoscaler-scaler-methods] in the Scaler component page for more information.                                                                |
| `scalingProfile`         | `DEFAULT` | Scaling profiles that should be used. Options are: `DEFAULT` or `CUSTOM`. See the [scaling profiles section][autoscaler-scaling-profiles] in the Scaler component page for more information.                                              |
| `scalingRules`           | `undefined`      | Scaling rules to be used when the `CUSTOM` scaling profile is supplied. See the [scaling profiles section][autoscaler-scaling-profiles] in the Scaler component page for more information.                                                                         |
| `stepSize`               | 1                | Number of nodes that should be added or removed when scaling with the `STEPWISE` method.                                                                                                                                                                          |
| `scaleInLimit`           | `undefined`      | Maximum number of nodes that can be removed on a single step when scaling with the `LINEAR` method. If `undefined` or `0`, it will not limit the number of nodes.                                                                                                |
| `scaleOutLimit`          | `undefined`      | Maximum number of nodes that can be added on a single step when scaling with the `LINEAR` method. If `undefined` or `0`, it will not limit the number of nodes.                                                                                                  |
| `scaleOutCoolingMinutes` | 10               | Minutes to wait after scaling IN or OUT before a scale OUT event can be processed.                                                                                                                                                                                 |
| `scaleInCoolingMinutes`  | 20               | Minutes to wait after scaling IN or OUT before a scale IN event can be processed.                                                                                                                                                                                  |
| `stateProjectId`         | `${projectId}`   | The project ID where the Autoscaler state will be persisted. By default it is persisted using [Cloud Firestore][cloud-firestore] in the same project as the AlloyDB instance.                                                                          |
| `stateDatabase`          | Object           | An Object that can override the database for managing the state of the Autoscaler. The default database is Firestore. Refer to the [state database](#state-database) for details.                                                                                  |
| `downstreamPubSubTopic`  | `undefined`      | Set this parameter to `projects/${projectId}/topics/downstream-topic` if you want the the Autoscaler to publish events that can be consumed by downstream applications. See [Downstream messaging](../scaler/README.md#downstream-messaging) for more information. |

## Metrics

The Autoscaler determines the number of nodes to be added to or subtracted from
an instance based on best practices for CPU and connection utilization metrics,
and includes rules for scaling based on these.

The Autoscaler monitors the workload of an instance by polling the time series
of the following:

-   `alloydb.googleapis.com/instance/cpu/maximum_utilization`
-   `alloydb.googleapis.com/instance/cpu/average_utilization`
-   `alloydb.googleapis.com/instance/postgres/total_connections / alloydb.googleapis.com/instance/postgres/connections_limit`

Google recommends initially using the provided metrics and rules unchanged.
However, in some cases you may want to define custom rules based on metrics in
addition to the default metrics listed above.

## State Database

The table describes the objects used to specify the database for managing the
state of the Autoscaler.

| Key    | Default     | Description                                                                                                                                                 |
| ------ | ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name` | `firestore` | Name of the database for managing the state of the Autoscaler. By default, Firestore is used. The currently supported values are `firestore` and `spanner`. |

### State Management in Firestore

If the value of `name` is `firestore`, the following values are optional.

| Key          | Description                                                                                                                                                                              |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `databaseId` | The database ID of the Firestore database you want to use to store the autoscaler state. If omitted, the default (`(default)`) database will be used. Note that the database must exist. |

### State Management in Cloud Spanner

If the value of `name` is `spanner`, the following values are required.

| Key          | Description                                                    |
| ------------ | -------------------------------------------------------------- |
| `instanceId` | The instance id of Spanner which you want to manage the state. |
| `databaseId` | The database id of Spanner which you want to manage the state. |

When using Cloud Spanner to manage the state, a table with the following DDL is
created at runtime.

```sql
CREATE TABLE alloyDbAutoscaler (
  id STRING(MAX),
  lastScalingTimestamp TIMESTAMP,
  createdOn TIMESTAMP,
  updatedOn TIMESTAMP,
  lastScalingCompleteTimestamp TIMESTAMP,
  scalingOperationId STRING(MAX),
  scalingRequestedSize INT64,
  scalingPreviousSize INT64,
  scalingMethod STRING(MAX),
) PRIMARY KEY (id)
```

## Example JSON configuration for Cloud Run functions

```json
[
  {
    "projectId": "alloydb-app-project-id",
    "regionId": "us-central1",
    "clusterId": "alloydb-cluster",
    "instanceId": "alloydb-read-pool-instance",
    "scalingMethod": "STEPWISE",
    "minSize": 3,
    "maxSize": 10,
    "scalerPubSubTopic": "projects/alloydb-app-project-id/topics/scaler-topic",
    "stateDatabase": {
      "name": "firestore"
    }
  }
]
```

By default, the JSON configuration is managed by Terraform, in the
[autoscaler-scheduler][autoscaler-scheduler-tf] module. If you would like to
manage this configuration directly (i.e. outside Terraform), then you will need
to configure the Terraform lifecycle `ignore_changes` meta-argument by
uncommenting the appropriate line as described in the above file. This is so
that subsequent Terraform operations do not reset your configuration to the
supplied defaults.

## Example YAML ConfigMap for Kubernetes deployment

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: autoscaler-config
  namespace: alloydb-autoscaler
data:
  autoscaler-config.yaml: |
    ---
    - projectId: alloydb-app-project-id
      regionId: us-central1
      clusterId: alloydb-cluster
      instanceId: alloydb-read-pool-instance
      scalingMethod: STEPWISE
      units: NODES
      minSize: 3
      maxSize: 10
      stateDatabase:
        name: firestore
```

<!-- LINKS: https://www.markdownguide.org/basic-syntax/#reference-style-links -->

[autoscaler-scaler-methods]: ../scaler/README.md#scaling-methods
[autoscaler-scaling-profiles]: ../scaler/README.md#scaling-profiles
[autoscaler-scheduler-tf]: ../../terraform/modules/autoscaler-scheduler/main.tf
[cloud-firestore]: https://cloud.google.com/firestore
[cloud-monitoring]: https://cloud.google.com/monitoring
[configmap]: https://kubernetes.io/docs/concepts/configuration/configmap
