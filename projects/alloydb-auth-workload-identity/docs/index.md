# Secure and fast access to AlloyDB from GKE applications

## Background

The AlloyDB for PostgreSQL
[supports](https://cloud.google.com/alloydb/docs/manage-iam-authn)
authentication via
[Google Cloud Service Account](https://cloud.google.com/iam/docs/service-account-overview),
this way removes the requirement of managing the username/password as secrets
for applications to authenticate to the database.

This feature can be combined with the
[workload identity](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity)
feature of GKE to let applications running in GKE to authenticate to AlloyDB
directly using the associated service account.

However, the existent documentation only describes authentication through an
[auth_proxy](https://cloud.google.com/alloydb/docs/quickstart/integrate-kubernetes#auth-proxy),
which has two disadvantages:

- The sidecar might impact the performance
- Extra efforts need to be taken to setup the sidecar in the application
  deployment

This [guide](howto.md) describes a way to make the applications in GKE
authenticate to AlloyDB using workload identity without the auth_proxy.
