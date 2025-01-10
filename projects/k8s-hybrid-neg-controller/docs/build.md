# Build the controller manager container image

This document explains how to build the controller manager container image.

1.  Install the following tools:

    -   [Go](https://golang.org/doc/install) v1.23 or later
    -   [Skaffold](https://skaffold.dev/docs/install/#standalone-binary)
        v2.10.1 or later

1.  Clone the Git repository and navigate to the directory
    `projects/k8s-hybrid-neg-controller`.

The base image is defined by the `fromImage` field in the Skaffold configuration
file in the project base directory: `../skaffold.yaml`.

## Local container image storage

Build the container image and load it into your local Docker daemon or Podman
container storage:

```shell
skaffold build --cache-artifacts=false --push=false
```

The default destination is `/var/run/docker.sock`, but you can override the
destination using the `DOCKER_HOST` environment variable.

## Remote container image repository

Build the container image and push it to your container image repository:

```shell
skaffold build --cache-artifacts=false --push --default-repo [your container image repository]
```

You can specify the container image repository using either the `default-repo`
flag, or the `SKAFFOLD_DEFAULT_REPO` environment variable.

See below for instructions specific to cloud provider container image
registries.

### Google Cloud's Artifact Registry

Build the container image and push it to a container image repository in
[Artifact Registry](https://cloud.google.com/artifact-registry/docs/overview):

```shell
skaffold build --cache-artifacts=false --push --default-repo $AR_LOCATION-docker.pkg.dev/$PROJECT_ID/$AR_REPOSITORY
```

In the command above, replace the following:

-   `$AR_LOCATION`: the
    [location of your Artifact Registry repository](https://cloud.google.com/artifact-registry/docs/repositories/repo-locations).
-   `$PROJECT_ID`: the project ID of your
    [Google Cloud project](https://cloud.google.com/resource-manager/docs/creating-managing-projects).
-   `$AR_REPOSITORY`: the name of your Artifact Registry repository name.

### Amazon Elastic Container Registry

Build the container image and push it to an Amazon ECR repository:

```shell
AWS_ACCOUNT_ID=[your AWS account ID]
ECR_REGION=[the region of your ECR private repository, e.g., us-east-1]
ECR_REGISTRY=$AWS_ACCOUNT_ID.dkr.ecr.$ECR_REGION.amazonaws.com
ECR_REPOSITORY_NAME=hybrid-neg-controller-manager

aws ecr create-repository --region $ECR_REGION --repository-name $ECR_REPOSITORY_NAME

skaffold build --cache-artifacts=false --push --default-repo $ECR_REGISTRY
```

### Azure Container Registry

Build the container image and push it to a private registry in Azure Container
Registry:

```shell
ACR_NAME=<the name if your private registry in Azure Container Registry>
ACR_RESOURCE_GROUP=<the Azure resource group that contains your registry>

ACR_LOGIN_SERVER=$(az acr show \
  --name $ACR_NAME \
  --expose-token \
  --resource-group $ACR_RESOURCE_GROUP \
  --output tsv \
  --query loginServer)

skaffold build --cache-artifacts=false --push --default-repo $ACR_LOGIN_SERVER
```

## Building with `ko`

You can use the [`ko`](https://ko.build/) command-line tool to build the
container image, instead of
[Skaffold's `ko` builder](https://skaffold.dev/docs/builders/builder-types/ko/).

1.  Download the [`ko` binary for your platform](https://ko.build/install/).

1.  Define the base image you want to use in the
    [`.ko.yaml` config file](https://ko.build/configuration/):

    ```shell
    cat << EOF > .ko.yaml
    defaultBaseImage: gcr.io/distroless/static-debian12:nonroot
    EOF
    ```

    You can specify the base image using the `KO_DEFAULTBASEIMAGE` environment
    variable, instead of creating the `.ko.yaml` config file.

    For additional configuration options, see the documentation on
    [`ko` configuration](https://ko.build/configuration/).

1.  Specify the container image repository where `ko` should push the container
    image using the `KO_DOCKER_REPO` environment variable:

    ```shell
    export KO_DOCKER_REPO=[your container image repository]
    ```

1.  Build the container image and push it to the repository:

    ```shell
    ko build .
    ```
