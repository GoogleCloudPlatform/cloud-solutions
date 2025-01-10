# Limitations

-   Minimum Kubernetes API server version: v1.21

-   Referencing the same hybrid NEGs from multiple different Kubernetes Services
    is not supported. The controller does not prevent you from doing this, but
    behavior is undefined.

This means that NEG names that you provide in the
`solutions.cloud.google.com/hybrid-neg` Kubernetes Service annotations must be
unique across all Services in a Kubernetes cluster, and also across all
Kubernetes clusters where `k8s-hybrid-neg-controller` is deployed and configured
to use the same Google Cloud project ID and Compute Engine zones.

-   Hybrid NEGs currently allow endpoints with IPv4 addresses only. If your
    Kubernetes Services are available via both IPv4 and IPv6
    ([dual stack networking](https://kubernetes.io/docs/concepts/services-networking/dual-stack/)),
    `k8s-hybrid-neg-controller` only adds the IPv4 endpoint addresses to the
    hybrid NEGs.

For details on IPv6 and dual-stack support by proxy load balancers on Google
Cloud, see
[IPv6 for Application Load Balancers and proxy Network Load Balancers](https://cloud.google.com/load-balancing/docs/ipv6).

-   You cannot use the network endpoint groups (NEGs) created by
    `k8s-hybrid-neg-controller` as backends of load balancers managed by the
    [GKE Gateway controller](https://cloud.google.com/kubernetes-engine/docs/concepts/gateway-api#gateway_controller)
    using the [Kubernetes Gateway API](https://gateway-api.sigs.k8s.io/).

This is because the GKE Gateway controller manages the Cloud Load Balancing
resources, such as network endpoint groups (NEGs) and backend services, created
for the Kubernetes Services referenced by the
[Route resources of the Kubernetes Gateway API](https://gateway-api.sigs.k8s.io/concepts/api-overview/#route-resources).
