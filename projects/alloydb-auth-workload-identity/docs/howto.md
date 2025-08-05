# Authenticate to AlloyDB using AlloyDB users and Workload Identity Federation for GKE

## Setups in your GCP project

### Create a GCP service account {#create-a-gcp-service-account}

AlloyDB supports authentication via IAM-based authentication. To do this, you
need a GCP service account. You can create a GCP service account by doing the
following:

```bash
PROJECT_ID=<your-gcp-project-id>
GCP_SA_NAME=<your-service-account-name>

gcloud --project "$PROJECT_ID" create "$GCP_SA_NAME"
```

### Grant roles to this service account

To make the service account capable of authenticate to the AlloyDB instances, it
needs these Roles:

- `roles/serviceusage.serviceUsageConsumer`
- `roles/alloydb.databaseUser`

You can do this by running the following commands:

```bash
gcloud add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$GCP_SA_NAME@${PROJECT_ID}.iam.gserviceaccount.com"\
  --role=roles/serviceusage.serviceUsageConsumer

gcloud add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$GCP_SA_NAME@${PROJECT_ID}.iam.gserviceaccount.com"\
  --role=roles/alloydb.databaseUser
```

### Grant GCP service account access to the Kubernetes Service Account {#grant-gcp-service-account-access-to-the-kubernetes-service-account}

You can follow the guidance of
[workload-identity](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity)
to grant the GCP service account you've just created to a kubernetes service
account.

The commands are like these:

```bash
K8S_NAMESPACE=<the-namespace-you-want-to-create-resources>
K8S_SA=<the-k8s-service-account-name>
gcloud --project "$PROJECT_ID" iam service-accounts add-iam-policy-binding \
  "$GCP_SA_NAME@${PROJECT_ID}.iam.gserviceaccount.com"\
  --role roles/iam.workloadIdentityUser\
  --member "serviceAccount:${PROJECT_ID}.svc.id.goog[$K8S_NAMESPACE/$K8S_SA]"
```

## Setups in the AlloyDB

On the AlloyDB side, you need the following setups.

### Enable IAM authentication on your AlloyDB instance

Run the following:

```bash
CLUSTER_NAME=<your-alloydb-cluster-name>
CLUSTER_REGION=<your-alloydb-cluster-region>
INSTANCE_NAME=<your-alloydb-instance>
OTHER_DATABASE_FLAGS=<your_existing_database_flags>
gcloud --project "$PROJECT_ID" alloydb instances update\
  "$INSTANCE_NAME"\
  --cluster "$CLUSTER_NAME"\
  --region="$CLUSTER_REGION" \
  --database-flags="alloydb.iam_authentication=on,$OTHER_DATABASE_FLAGS"
```

### Create an AlloyDB user for the IAM service account

According to the
[Manage IAM authentication in AlloyDB](https://cloud.google.com/alloydb/docs/manage-iam-authn)
document, you can create a user in the AlloyDB bound to a GCP service account.

To do so, run the following command

```bash
ALLOYDB_ROLES=<your_desired_roles_for_the_user>
gcloud --project $PROJECT_ID alloydb users \
  create "$GCP_SA_NAME@${PROJECT_ID}.iam" \
  --cluster "$CLUSTER_NAME" \
  --region="$CLUSTER_REGION" \
  --type=IAM_BASED \
  --db-roles=$ALLOYDB_ROLES
```

Note that all IAM_TYPE users in AlloyDB have the name of this form
`<sa_name>@<project_id>.iam`.

## Authenticate your application from GKE to AlloyDB

Now you can make your applications running in GKE clusters to authenticate to
the AlloyDB by using Kubernetes Service Account.

Here is how.

### Enable "Workload Identity Federation for GKE" for your GKE Cluster

Run the following commands:

```bash
CLUSTER_NAME=<your-gke-cluster-name>
LOCATION=<your-gke-cluster-location>
gcloud --project "$PROJECT_ID" container clusters update "$CLUSTER_NAME" \
    --location="$LOCATION" \
    --workload-pool="$PROJECT_ID.svc.id.goog"

```

#### Enable GKE_METADATA for the node-pools

You also need to let the node-pools in your cluster provide "GKE_METADATA".

You can check if a certain node-pool has already enabled "GKE_METADATA" by using
the following command:

```bash
gcloud --project "$PROJECT_ID" container node-pools describe \
    <your_node_pool_name> \
    --cluster=$CLUSTER_NAME \
    --location=$LOCATION | grep GKE_METADATA

```

if the node-pool has "GKE_METADATA", you should see

```text
    mode: GKE_METADATA
```

in the output of the above command.

If not, for each of the node-pools in your cluster you want "GKE_METADATA", run
the following:

```bash
gcloud --project "$PROJECT_ID" container node-pools update \
    <your_node_pool_name> \
    --cluster=$CLUSTER_NAME \
    --location=$LOCATION \
    --workload-metadata=GKE_METADATA

```

### Create a Kubernetes Service Account

Modify and apply the following manifest to your GKE cluster. You need to change
these:

- Replace `$K8S_NAMESPACE` with value of K8S_NAMESPACE in this
  [step](#grant-gcp-service-account-access-to-the-kubernetes-service-account)
- Replace `$K8S_SA` with value of K8S_SA in this
  [step](#grant-gcp-service-account-access-to-the-kubernetes-service-account)
- Replace `$GCP_SA_NAME` with value GCP_SA_NAME in this
  [step](#create-a-gcp-service-account)
- Replace `$PROJECT_ID` with your project id

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  annotations:
    iam.gke.io/gcp-service-account: $GCP_SA_NAME@$PROJECT_ID.iam.gserviceaccount.com
    iam.gke.io/scopes-override: https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/alloydb.login,openid
  name: $K8S_SA
  namespace: $K8S_NAMESPACE
```

Note that this service account has two annotations:

- `iam.gke.io/gcp-service-account` this binds the Kubernetes Service Account to
  the GCP service account
- `iam.gke.io/scopes-override` This This specifies the OAuth scopes that are
  granted to the access token for the service account. The scope:
  `https://www.googleapis.com/auth/alloydb.login` is required for connecting to
  AlloyDB, this is documented in the this
  [Connect using an IAM account | AlloyDB for PostgreSQL | Google Cloud](https://cloud.google.com/alloydb/docs/connect-iam#procedure)

### Inside the pods

To make your application authenticate to AlloyDB, you will need to get the
username and password. Instead of storing the credentials in a secret or using
the "auth_proxy", you can make your application connect to AlloyDB directly.

Here is how to get the username and password.

- Get the username You can use the following command in the pod to set the
  environment variable PGUSER for your application.

```bash
PGUSER=$(curl -H "Metadata-Flavor: Google" http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/email|sed 's/\.gserviceaccount.com//')
export PGUSER

```

- Get the password You can use the following command in the pod to set the
  environment variable PGPASSWORD for your application. _Note_ This method only
  fetches the token once, you need to fetch token eachtime when your application
  makes new connection to the database.

```bash
PGPASSWORD=$(curl -H "Metadata-Flavor: Google" http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token|jq -r .access_token)
export PGPASSWORD
```

You can put the above commands in your application start-up command. Or you can
integrate the equivalent logic in your application. _Caution_ Be mindful of the
risks of storing secrets in environment variables. Some execution environments
or the use of some frameworks can result in the contents of environment
variables being sent to logs.
