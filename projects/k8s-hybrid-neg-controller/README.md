# Hybrid NEG controller for Kubernetes

`k8s-hybrid-neg-controller` is a Kubernetes controller that creates and
manages hybrid connectivity network endpoint groups, also known as
hybrid NEGs or `NON_GCP_PRIVATE_IP_PORT` NEGs, based on the
Compute Engine API and annotations on Kubernetes Services and the state of
their EndpointSlices.

Please refer to the documentation in the `docs` directory.

## Disclaimer

This is not an officially supported Google product.
