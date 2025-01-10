# Hybrid NEG controller for Kubernetes

`k8s-hybrid-neg-controller` is a
[Kubernetes controller](https://kubernetes.io/docs/concepts/architecture/controller/)
that creates and manages
[hybrid connectivity network endpoint groups (NEGs)](https://cloud.google.com/load-balancing/docs/negs/hybrid-neg-concepts),
also known as "hybrid NEGs" or `NON_GCP_PRIVATE_IP_PORT` NEGs, based on the
[Compute Engine API](https://cloud.google.com/compute/docs/reference/rest/v1/networkEndpointGroups)
and annotations on
[Kubernetes Services](https://kubernetes.io/docs/concepts/services-networking/service/)
and the state of their
[EndpointSlices](https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/).

[Hybrid connectivity NEGs](https://cloud.google.com/load-balancing/docs/negs#hybrid-neg)
enable workloads running on-prem and on other clouds to be used with
[Cloud Load Balancing](https://cloud.google.com/load-balancing/docs/load-balancing-overview)
and [Cloud Service Mesh](https://cloud.google.com/service-mesh/docs/overview)
(managed Traffic Director control plane).

This controller works in a similar manner to the
[NEG controller provided by Google Kubernetes Engine (GKE)](https://cloud.google.com/kubernetes-engine/docs/how-to/standalone-neg),
but instead of creating zonal
[`GCE_VM_IP_PORT` NEGs](https://cloud.google.com/load-balancing/docs/negs#zonal-neg),
`k8s-hybrid-neg-controller` creates zonal
[`NON_GCP_PRIVATE_IP_PORT` NEGs](https://cloud.google.com/load-balancing/docs/negs#hybrid-neg).

## Use case highlights

Example use cases for this controller include the following:

-   Use an external or internal layer 7
    [Application Load Balancer](https://cloud.google.com/load-balancing/docs/application-load-balancer)
    or layer 4
    [proxy Network Load Balancer](https://cloud.google.com/load-balancing/docs/proxy-network-load-balancer)
    on Google Cloud to load balance traffic across backends running in
    Kubernetes clusters on both Google Cloud and on-prem or on other clouds.

-   Enable client-side traffic splitting, routing, and load balancing of
    internal (east-west) traffic across backends running in Kubernetes clusters
    on both Google Cloud and on-prem or on other clouds, with direct Pod-to-Pod
    communication.
    This is made possible by using the managed control plane of
    [Cloud Service Mesh](https://cloud.google.com/service-mesh/docs/overview),
    configured using the
    [service routing APIs](https://cloud.google.com/service-mesh/docs/service-routing/service-routing-overview).
    The Kubernetes clusters do _not_ need to run an in-cluster service mesh
    control plane for the workloads to be part of the service mesh.

For further details on these and other use cases, see the document on
[use cases](use-cases.md).

## Where can this controller run?

This controller can run on any CNCF conformant Kubernetes cluster - on-prem, on
Google Cloud, and on other clouds.

The controller must have network connectivity to the
[Compute Engine API](https://cloud.google.com/compute/docs/reference/rest/v1)
endpoint (`compute.googleapis.com:443`), via either
[Private Google Access](https://cloud.google.com/vpc/docs/private-google-access-hybrid)
or the public internet.

The Kubernetes cluster can optionally be attached to Google Cloud
[Fleet management](https://cloud.google.com/kubernetes-engine/docs/fleets-overview).
This controller is not a replacement for Fleet management and attached
Kubernetes clusters, it provides complementary functionality.

For integration with Cloud Load Balancing, and with other workloads running on
Google Cloud, the Pod IP addresses of the Kubernetes cluster must be routable
from a Virtual Private Cloud (VPC) network on Google Cloud via
[Cloud VPN](https://cloud.google.com/network-connectivity/docs/vpn/concepts/overview)
and/or
[Cloud Interconnect](https://cloud.google.com/network-connectivity/docs/interconnect/concepts/overview)
with a VLAN attachment.

## Required configuration

When running off-Google Cloud, the following configuration values must be set.

### Google Cloud project ID

Set the
[project ID](https://cloud.google.com/resource-manager/docs/creating-managing-projects)
of the Google Cloud project where the controller creates network endpoint
groups (NEGs) either as an environment variable (`env`) called
`PROJECT_ID`, or by adding the `project-id` flag as a container argument
(`args`) in the Pod spec of the controller manager.

If both the `project-id` flag and the `PROJECT_ID` environment variable are set,
the flag value takes precedence.

### VPC network name

Set the name of the
[Virtual Private Cloud (VPC) network](https://cloud.google.com/vpc/docs/vpc)
on Google Cloud where the controller creates network endpoint groups (NEGs),
either as an environment variable (`env`) called
`NETWORK`, or by adding the `network` flag as a container argument
(`args`) in the Pod spec of the controller manager.

If both the `network` flag and the `NETWORK` environment variable are set,
the flag value takes precedence.

If you do not provide a VPC network name, the controller uses the name
`default`.

### Zone mappings

The controller requires zone mappings from the
[Kubernetes cluster Node zones](https://kubernetes.io/docs/reference/labels-annotations-taints/#topologykubernetesiozone)
to
[Compute Engine zones](https://cloud.google.com/compute/docs/regions-zones/).

When the controller discovers an endpoint, the zone of the endpoint's
cluster Node is mapped to a Compute Engine zone before the endpoint is
attached to a NEG.

Set the zone mapping by doing one of the following:

1.  Add the `zone-mapping` flag as a container argument (`args`) in the
    Pod spec of the controller manager.

1.  Add the `ZONE_MAPPING` environment variable (`env`) in the Pod spec of
    the controller manager. See
    `../k8s/components/zone-mapping-flag-kind.yaml`
    for an example on how to do this.

For example, if you run the controller on a Kubernetes cluster in another
cloud provider with Nodes in zones of the `eu-west-2` region, you can map
the Kubernetes cluster's Node zones to Compute Engine zones in the
`europe-west2` region by adding this zone mapping as a flag or environment
variable:

```shell
eu-west-2a=europe-west2-a,eu-west-2b=europe-west2-b,eu-west-2c=europe-west2-c
```

These configuration values are not required when the controller runs in a
Kubernetes cluster on Google Cloud, as the controller can look up the values
from the Compute Engine or Google Kubernetes Engine (GKE)
[metadata server](https://cloud.google.com/compute/docs/metadata/overview).

For detailed instructions on how to set the `PROJECT_ID` and `ZONE_MAPPING`
environment variables, see the section below on
[deploying the controller](#deploying-the-controller).

Additional configuration flags and environment variables are available, see the
[Additional configuration](#additional-configuration) section below.

## Deploying the controller

The following deployment documents are available:

-   [Deploying to an Amazon Elastic Kubernetes Service (EKS) cluster](deploy-eks.md).
    This document also covers how to build and push the container image to an
    Amazon Elastic Container Registry (ECR) repository.

-   [Deploying to an Azure Kubernetes Service (AKS) cluster](deploy-aks.md).
    This document also covers how to build and push the container image to a
    private container registry in Azure Container Registry.

-   [Deploying to a GKE cluster](deploy-gke.md). Some use cases, such as
    client-side cross-cloud load balancing using Cloud Service Mesh, specify
    that `k8s-hybrid-neg-controller` is deployed on GKE clusters on Google
    Cloud.

-   [Deploying to a local `kind` Kubernetes cluster](deploy-kind.md). A local
    `kind` Kubernetes cluster can be used for development and to experiment with
    the controller.

## Using the controller

After you have deployed the controller, you can start annotating your Kubernetes
Services to create hybrid NEGs.

For details on how to use the controller to create and manage hybrid NEGs for
your Kubernetes Services, see the [user guide](user-guide.md).

## Limitations

See [Limitations](limitations.md).

## Additional configuration

Additional flags and environment variables are available to configure the
controller's behavior.

In cases where a value can be set either as a flag or as an environment
variable, the flag value takes precedence if both are set.

```shell
$ ./k8s-hybrid-neg-controller --help
Usage of ./k8s-hybrid-neg-controller:
      --add_dir_header                         If true, adds the file directory to the header of the log messages
      --alsologtostderr                        log to standard error as well as files (no effect when -logtostderr=true)
      --cluster-id string                      The Kubernetes cluster ID to use when dynamically creating names for network endpoint groups (NEGs). If unspecified, the controller manager will look up a value from the environment. Can also be set using the environment variable CLUSTER_ID.
      --context string                         The name of the kubeconfig context to use, if using a kubeconfig file. If unset, the current context will be used. See also the 'kubeconfig' flag. Can also be set using the environment variable CONTEXT.
      --default-neg-zone string                The default Compute Engine zone to use when creating network Endpoint Groups (NEGs) if no mapping exists for the zone of an endpoint. If undefined, the controller selects one of the zones provided to 'neg-zones' as the default. Can also be set using the environment variable DEFAULT_NEG_ZONE.
      --exclude-system-namespaces              If true, exclude Services in Namespaces that end with '-system'. Can also be set using the environment variable EXCLUDE_SYSTEM_NAMESPACES. (default true)
      --health-probe-bind-address string       The address that the probe endpoint binds to. Can also be set using the environment variable HEALTH_PROBE_BIND_ADDRESS. (default ":8081")
      --kubeconfig string                      Paths to a kubeconfig. Only required if out-of-cluster. Can also be set using the environment variable KUBECONFIG.
      --log_backtrace_at traceLocation         when logging hits line file:N, emit a stack trace (default :0)
      --log_dir string                         If non-empty, write log files in this directory (no effect when -logtostderr=true)
      --log_file string                        If non-empty, use this log file (no effect when -logtostderr=true)
      --log_file_max_size uint                 Defines the maximum size a log file can grow to (no effect when -logtostderr=true). Unit is megabytes. If the value is 0, the maximum file size is unlimited. (default 1800)
      --logtostderr                            log to standard error instead of files (default true)
      --metrics-bind-address string            The address that the metric endpoint binds to. Can also be set using the environment variable METRICS_BIND_ADDRESS. (default ":8080")
      --neg-zones string                       Compute Engine zones used by this controller to create network Endpoint Groups (NEGs). If omitted, the controller dynamically discovers zones by watching the Kubernetes cluster Nodes and mapping the values of the 'topology.kubernetes.io/zone' label to Compute Engine zones, using the mappings defined by the 'zone-mapping' flag. Can also be set using the environment variable NEG_ZONES.
      --network string                         The global Compute Engine VPC network to use when creating network Endpoint Groups (NEGs). Can also be set using the environment variable NETWORK. (default "default")
      --one_output                             If true, only write logs to their native severity level (vs also writing to each lower severity level; no effect when -logtostderr=true)
      --project-id string                      The project ID of the Google Cloud project where the controller should create network Endpoint Groups (NEGs). If unset, the controller looks up the project ID from the Compute Engine/Google Kubernetes Engine metadata server. Can also be set using the environment variable PROJECT_ID.
      --reconcile-requeue-delay-seconds int    The requeue delay for the controllers' reconcile loop on non-terminal errors. Can also be set using the environment variable RECONCILE_REQUEUE_DELAY_SECONDS. (default 10)
      --skip_headers                           If true, avoid header prefixes in the log messages
      --skip_log_headers                       If true, avoid headers when opening log files (no effect when -logtostderr=true)
      --stderrthreshold severity               logs at or above this threshold go to stderr when writing to files and stderr (no effect when -logtostderr=true or -alsologtostderr=true) (default 2)
      --timeout-create-zonal-neg-seconds int   Timeout in seconds for creating zonal network endpoint groups (NEGs). Can also be set using the environment variable TIMEOUT_CREATE_ZONAL_NEG_SECONDS. (default 300)
      --timeout-delete-zonal-neg-seconds int   Timeout in seconds for deleting zonal network endpoint groups (NEGs). Can also be set using the environment variable TIMEOUT_DELETE_ZONAL_NEG_SECONDS. (default 300)
      --timeout-sync-zonal-neg-seconds int     Timeout in seconds for synchronizing endpoints of zonal network endpoint groups (NEGs). Can also be set using the environment variable TIMEOUT_SYNC_ZONAL_NEG_SECONDS. (default 300)
  -v, --v Level                                number for the log level verbosity
      --vmodule moduleSpec                     comma-separated list of pattern=N settings for file-filtered logging
      --zone-mapping string                    List of comma-separated 'key=value' pairs, where the key is a zone used by a node in the Kubernetes cluster, and the value is the Compute Engine zone to use when creating a hybrid NEG for endpoints in that zone. To see the zones currently used by your k8s cluster Nodes, run 'kubectl get nodes --output=jsonpath="{.items[*].metadata.labels.topology\.kubernetes\.io/zone}"'. To see a list of Compute Engine zones, run 'gcloud compute zones list'. Can also be set using the environment variable ZONE_MAPPING.
```

## Disclaimer

This is not an officially supported Google product.
