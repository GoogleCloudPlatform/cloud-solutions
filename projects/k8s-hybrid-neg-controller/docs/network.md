# Network configuration for hybrid connectivity

`k8s-hybrid-neg-controller` relies on
[Cloud VPN](https://cloud.google.com/network-connectivity/docs/vpn/concepts/overview)
and/or
[Cloud Interconnect](https://cloud.google.com/network-connectivity/docs/interconnect/concepts/overview)
between your
[VPC network on Google Cloud](https://cloud.google.com/vpc/docs/vpc), and your
network on-prem or on other clouds for routing the following types of traffic:

- Routing of both data plane traffic and health check probes to your Pod
  endpoints on-prem or on other clouds.

- For Cloud Service Mesh: Routing of requests between your workloads running on
  Google Cloud, e.g., Pods in your GKE clusters, and Pods of your Kubernetes
  clusters running on-prem or on other clouds.

- Routing of requests from `k8s-hybrid-neg-controller` Pods to the Compute
  Engine API endpoint (`compute.googleapis.com:443`), as described in
  [Private Google Access for on-premises hosts](https://cloud.google.com/vpc/docs/private-google-access-hybrid).

If your `k8s-hybrid-neg-controller` Pods have internet connectivity, they can
connect to the Compute Engine API endpoint via the public internet, instead of
via hybrid connectivity and Private Google Access.

Traffic from Google's centralized health check mechanism and from your VPC
network on Google Cloud must be able to reach Pod endpoints in your network
on-prem or on other clouds without having to use network address translation
(NAT). This is often referred to as a
[flat-mode network model](https://cloud.google.com/kubernetes-engine/distributed-cloud/bare-metal/docs/reference/flat-vs-island-network).

## Hybrid connectivity guides

The following guides describe how to create connections between your VPC network
in Google Cloud and your network on-prem or on other clouds, using Cloud VPN and
Cloud Interconnect:

- [Create HA VPN connections between Google Cloud and AWS](https://cloud.google.com/network-connectivity/docs/vpn/tutorials/create-ha-vpn-connections-google-cloud-aws)

- [Connect HA VPN to AWS peer gateways](https://cloud.google.com/network-connectivity/docs/vpn/how-to/connect-ha-vpn-aws-peer-gateway)

- [Create HA VPN connections between Google Cloud and Azure](https://cloud.google.com/network-connectivity/docs/vpn/tutorials/create-ha-vpn-connections-google-cloud-azure)

- [Create an HA VPN gateway to a peer VPN gateway](https://cloud.google.com/network-connectivity/docs/vpn/how-to/creating-ha-vpn)

- [HA VPN over Cloud Interconnect overview](https://cloud.google.com/network-connectivity/docs/interconnect/concepts/ha-vpn-interconnect)

- [Create VLAN attachments for Dedicated Interconnect](https://cloud.google.com/network-connectivity/docs/interconnect/how-to/dedicated/creating-vlan-attachments)

We recommend that you use a high availability connection, such as
[HA VPN](https://cloud.google.com/network-connectivity/docs/vpn/concepts/overview#ha-vpn).

Before setting up HA VPN connections, review the
[HA VPN topologies](https://cloud.google.com/network-connectivity/docs/vpn/concepts/topologies)
and configurations for different levels of availability.

## Health check probes

[Health check probes](https://cloud.google.com/load-balancing/docs/health-check-concepts)
can originate from the following sources:

- From Google's
  [health checking mechanism](https://cloud.google.com/load-balancing/docs/health-check-concepts).
  These
  [centralized health checks](https://cloud.google.com/load-balancing/docs/negs/brid-neg-concepts#google-health-checks)
  originate from
  [Google Cloud probers](https://cloud.google.com/load-balancing/docs/health-check-concepts#ip-ranges).

Centralized health checks are used by the following load balancers:

- [Global external Application Load Balancers](https://cloud.google.com/load-balancing/docs/https)

- [Classic Application Load Balancers](https://cloud.google.com/load-balancing/docs/https)

- [Global external proxy Network Load Balancers](https://cloud.google.com/load-balancing/docs/tcp)

- [Classic proxy Network Load Balancers](https://cloud.google.com/load-balancing/docs/tcp)

- From Envoy proxy software operated by Google. These
  [distributed Envoy health checks](https://cloud.google.com/load-balancing/docs/negs/hybrid-neg-concepts#envoy-health-checks)
  originate from Google-operated Envoy proxy instances running in the
  [proxy-only subnets](https://cloud.google.com/load-balancing/docs/proxy-only-subnets)
  of your VPC networks.

Distributed Envoy health checks are used by the following load balancers:

- [Regional external Application Load Balancers](https://cloud.google.com/load-balancing/docs/https)

- [Cross-region and regional internal Application Load Balancers](https://cloud.google.com/load-balancing/docs/-internal)

- [Regional external proxy Network Load Balancers](https://cloud.google.com/load-balancing/docs/tcp)

- [Cross-region and regional internal proxy Network Load Balancers](https://cloud.google.com/load-balancing/cs/tcp/internal-proxy)

- From Envoy proxy software that you operate. If you use Cloud Service Mesh,
  these
  [distributed Envoy health checks](https://cloud.google.com/load-balancing/docs/negs/brid-neg-concepts#envoy-health-checks)
  originate from Envoy proxy instances running as your
  [mesh ingress gateways](https://cloud.google.com/service-mesh/docs/service-routing/set-up-ingress-gateway),
  and as
  [sidecar proxies](https://cloud.google.com/service-mesh/docs/service-routing/set-up-envoy-http-mesh)
  of your client workloads.

## Advertising routes

As part of setting up hybrid connectivity between your VPC network on Google
Cloud and your network on-prem or on another cloud, you must ensure that the
necessary routes are advertised.

- For load balancers using centralized health checks: The IP ranges used by
  Google's health check probers (`35.191.0.0/16` and `130.211.0.0/22`) must be
  [advertised to your network on-prem or on another cloud](https://cloud.google.com/network-connectivity/docs/router/how-to/advertising-custom-ip).

    This `gcloud` command advertises the IP ranges of Google's centralized
    health check probers on your Cloud Router:

    ```shell
    gcloud compute routers update-bgp-peer <CLOUD_ROUTER_NAME> \
      --peer-name <PEER_NAME> \
      --add-advertisement-ranges 35.191.0.0/16,130.211.0.0/22 \
      --region <REGION> \
      --project <PROJECT_ID>
    ```

- For load balancers using distributed Envoy health checks: The IP range of the
  [proxy-only subnet](https://cloud.google.com/load-balancing/docs/proxy-only-subnets)
  of your VPC network on Google Cloud, in the same region as the Cloud Router.

    Use this `gcloud` command to view details of your proxy-only subnets,
    including their IP ranges:

    ```shell
    gcloud compute networks subnets list \
      --filter 'purpose:(REGIONAL_MANAGED_PROXY GLOBAL_MANAGED_PROXY)' \
      --format yaml \
      --network <VPC_NETWORK_NAME> \
      --project <PROJECT_ID>
    ```

    This `gcloud` command advertises the IP ranges of your proxy-only subnet on
    your Cloud Router:

    ```shell
    gcloud compute routers update-bgp-peer <CLOUD_ROUTER_NAME> \
      --peer-name <PEER_NAME> \
      --add-advertisement-ranges <PROXY_ONLY_SUBNET_CIDR> \
      --region <REGION> \
      --project <PROJECT_ID>
    ```

    If your VPC network on Google Cloud has both a proxy-only subnet with
    purpose `REGIONAL_MANAGED_PROXY` _and_ a proxy-only subnet with purpose
    `GLOBAL_MANAGED_PROXY`, advertise the IP range of the proxy-only subnet that
    [corresponds to the load balancer](https://cloud.google.com/load-balancing/docs/proxy-only-subnets#envoy-lb)
    that you want to use with your hybrid NEGs.

- For Cloud Service Mesh: You need to advertise _both_ of the following:

    1.  The Pod IP ranges of your GKE clusters on Google Cloud to your network
        on-prem or on another cloud.

    1.  The Pod IP ranges of your Kubernetes clusters running on-prem or on
        another cloud to your VPC network on Google Cloud.

To advertise GKE cluster Pod IP ranges on your Cloud Router, you can either
advertise specified CIDR blocks, as documented above for load balancers, or you
can advertise all subnets of your VPC network (excluding any routes learned for
subnets that use VPC Network Peering):

```shell
gcloud compute routers update-bgp-peer <CLOUD_ROUTER_NAME> \
  --peer-name <PEER_NAME> \
  --advertisement-mode custom \
  --add-advertisement-groups all_subnets \
  --region <REGION> \
  --project <PROJECT_ID>
```

Note that the `all_subnets` advertised group in the `gcloud` command above
excludes any routes learned for subnets that use
[VPC Network Peering](https://cloud.google.com/vpc/docs/vpc-peering).

To advertise the Pod IP ranges of your Kubernetes clusters running on-prem or on
another cloud to your VPC network on Google Cloud, please refer to the
documentation of your VPN service.

If you use an AWS virtual private gateway (VGW) for your VPN connection, you can
use this
[`aws` command](https://docs.aws.amazon.com/cli/latest/reference/ec2/enable-vgw-route-propagation.html)
to advertise your EKS cluster Pod IP ranges to your VPC network on Google Cloud:

```shell
aws ec2 enable-vgw-route-propagation \
  --gateway-id <VIRTUAL_PRIVATE_GATEWAY_ID> \
  --route-table-id <PRIVATE_ROUTE_TABLE_ID>
```

Replace `<PRIVATE_ROUTE_TABLE_ID>` in the command above with the ID of your
route table where you have associated the subnets used for Pod IP addresses in
your EKS clusters.

If you use Terraform to manage your cloud resources, please refer to the
[`google_compute_router` resource documentation](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_router)
for details on how to update BGP peers on Cloud Routers.

For further information, see the
[network connectivity requirements](https://cloud.google.com/load-balancing/docs/negs/hybrid-neg-concepts#network_connectivity_requirements)
of hybrid NEGs.

## Firewalls

If you run `k8s-hybrid-neg-controller` on an EKS cluster, configure the EC2
security groups to allow traffic from Google Cloud to your EKS cluster Nodes.

If you connect your hybrid NEGs to load balancers on Google Cloud, you must
allow traffic from the IP ranges used by Google's health check probers.

If you connect your hybrid NEGs to Cloud Service Mesh, you must also allow
traffic from the IP ranges used by your mesh workloads on Google Cloud. If your
mesh workloads on Google Cloud run on GKE, allow traffic from the IP address
ranges of your GKE cluster nodes.

1.  Look up the security group ID of your EKS cluster:

    ```shell
    aws eks describe-cluster \
      --name <EKS_CLUSTER_NAME> \
      --query cluster.resourcesVpcConfig.clusterSecurityGroupId
    ```

1.  Configure the security group to allow traffic from Google's centralized
    health check probers:

    ```shell
    aws ec2 authorize-security-group-ingress \
      --group-id <SECURITY_GROUP_ID> \
      --protocol tcp \
      --port <application serving port> \
      --cidr 35.191.0.0/16

    aws ec2 authorize-security-group-ingress \
      --group-id <SECURITY_GROUP_ID> \
      --protocol tcp \
      --port <application serving port> \
      --cidr 130.211.0.0/22
    ```

    If your application uses different port for serving traffic and health check
    requests, execute the command again for the health check port.

    The health check port does _not_ need to be exposed by the Kubernetes
    Service.

1.  If you use Cloud Service Mesh on Google Cloud, allow traffic from your mesh
    workloads on Google Cloud to the serving ports and the health check ports of
    your mesh workloads running on EKS. Skip this step if you do not use Cloud
    Service Mesh.

    ```shell
    aws ec2 authorize-security-group-ingress \
      --group-id <SECURITY_GROUP_ID> \
      --protocol tcp \
      --port <application serving port> \
      --cidr <IP address ranges of mesh workloads on Google Cloud, e.g., GKE cluster nodes>
    ```

    If your application uses different port for serving traffic and health check
    requests, execute the command again for the health check port.

## Troubleshooting

If all endpoints in the hybrid NEGs are unhealthy:

- Verify that the BGP routing mode of your VPC network on Google Cloud is set to
  [global dynamic routing mode](https://cloud.google.com/network-connectivity/docs/router/concepts/learned-routes).

    You can
    [view and change your VPC network's dynamic routing mode](https://cloud.google.com/network-connectivity/docs/router/how-to/configuring-routing-mode).

    Learn more about
    [routing in Google Cloud](https://cloud.google.com/vpc/docs/routes).

- Verify that the Cloud Router is advertising the correct IP ranges to the
  network on-prem or on another cloud.

    For Cloud Load Balancing, depending on the load balancer used, the IP ranges
    to be advertised are either the IP ranges used by Google's
    [centralized health check](https://cloud.google.com/load-balancing/docs/negs/hybrid-neg-concepts#google-health-checks)
    probes, or the IP range of your
    [proxy-only subnet](https://cloud.google.com/load-balancing/docs/proxy-only-subnets)
    in the same region as the hybrid NEGs.

    For Cloud Service Mesh, the IP ranges to be advertised are the IP ranges
    used by your workloads running on Google Cloud that need to connect to your
    workloads running on-prem or on another cloud. For instance, if your
    workloads on Google Cloud run in Google Kubernetes Engine (GKE) clusters,
    advertise the Pod IP ranges of your GKE clusters.

- Verify that there is no route within your VPC network on Google Cloud that
  overlaps with the destination range. If there is overlap, subnet routes take
  precedence over hybrid connectivity.

- Verify that there is no firewall in your network on-prem or on another cloud
  that blocks traffic from Google Cloud on the advertised IP ranges.

    For additional details, see the hybrid NEG
    [network connectivity requirements](https://cloud.google.com/load-balancing/docs/negs/hybrid-neg-concepts#network_connectivity_requirements),
    and Cloud Load Balancing
    [firewall rules summary](https://cloud.google.com/load-balancing/docs/firewall-rules).
