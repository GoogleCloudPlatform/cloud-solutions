# Performance Testing


## Description

The performance testing process is to evaluate the performance of the system under different workloads and identify potential bottlenecks that can impact its performance. The following are the objectives of the performance testing process:

- Evaluate the system's performance under different workloads
- Identify potential bottlenecks in the system
- Determine the maximum capacity of the system
- Determine the system's response time and throughput
- Evaluate the system's scalability and stability



## Components

- pt-admin: *Management backend for performance testing.*

- pt-operator: *Operator to schedule performance testing in GKE cluster, aggregate metrics and logs into Cloud Operation Suite.*

- ui: *Web UI to manage and visualize performance testing.*

- tf: *Terraform scripts to provision all resources.*



## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli) >= 1.3.9
- [Go](https://go.dev/doc/install) >= 1.19
- [protoc](https://grpc.io/docs/protoc-installation/) >= 22.x
- [Docker](https://docs.docker.com/desktop/install/mac-install/) >= 20.10
- [gcloud CLI](https://cloud.google.com/sdk/docs/install) >= 423.0.0 with [credentials](https://cloud.google.com/sdk/docs/authorizing#run_gcloud_init)
- [nodejs](https://nodejs.org/en/download) >= 16.0
- [yarn](https://classic.yarnpkg.com/lang/en/docs/install/#mac-stable) >= 1.22



## Setup
The deployment approach is by deploying two copies of pt-admin component:
1. To the target GCP Project. Create a new GCP Project, or use an existing GCP Project where the deployer user having permissions as Owner or Editor.
2. To run pt-admin container locally (hosting the UI and part of the backend)

The less pre-requisite dependencies to run this setup is by doing it from the Cloud Shell. Make sure there's enough disk space to run the commands below.

Setup Firebase in Firestore Native Mode
Enable firestore.googeleapis.com then
go to https://console.cloud.google.com/datastore/databases/-default-/entities/query/kind?cloudshell=false&project=<REPLACE_WITH_PROJECT_ID>
and click SWTICH TO NATIVE MODE button.

```shell
# 1. Set environment variables
# Change to your project id
export PROJECT_ID=$(gcloud config get-value project)

# Change to your region, where you want to deploy
export REGION=asia-southeast1
# Set pt-admin image
export PT_ADMIN_IMAGE=${REGION}-docker.pkg.dev/${PROJECT_ID}/performance-testing/pt-admin:latest
# Set pt-operator image
export PT_OPERATOR_IMAGE=${REGION}-docker.pkg.dev/${PROJECT_ID}/performance-testing/pt-operator:latest

Setup Firebase in Firestore Native Mode
Go to https://console.cloud.google.com/datastore/databases/-default-/entities/query/kind?cloudshell=false&project=<REPLACE_WITH_PROJECT_ID>


# 2. Create artifact registry in your project
gcloud artifacts repositories create performance-testing \
  --repository-format=docker \
  --location=${REGION} \
  --description="Performance testing images"

# 3. Build pt-admin image and push to GAR
cd pt-admin
make docker-buildx IMG=${PT_ADMIN_IMAGE}

# 4. Build pt-operator image and push to GAR
cd pt-operator
make docker-buildx IMG=${PT_OPERATOR_IMAGE}


# 5. Provision all resources 
cd tf
terraform init
# Edit terraform.tfvars file with the actual value of these parameters:
#   - project_id: ${PROJECT_ID}
#   - region: ${REGION}
#   - pt_admin_image: ${PT_ADMIN_IMAGE}
terraform apply
```

## Run Performance Testing UI locally
This is tool deployment is intended to be deployed in two place: local machine/laptop, and on the Cloud Run. The locally run container will communicate to the Cloud Run's deployed container via pub/sub call.

```shell
# 1. Authenticate to the GCP Project where the Cloud Run is Deployed.
gcloud auth login

# 2. Run The Image Locally. Also make sure that Docker daemon is already running
# Input required parameters:
#   - PROJECT_ID: ${PROJECT_ID}
#   - REGION: ${REGION}
#   - PT_ADMIN_IMAGE: ${PT_ADMIN_IMAGE}
docker run -e PROJECT_ID=$PROJECT_ID -e REGION=$REGION -e ARCHIEVE_BUCKET="${PROJECT_ID}_pt-results-archive" -e LOCATION=$REGION -e TARGET_PRINCIPAL="pt-service-account@${PROJECT_ID}.iam.gserviceaccount.com" -e K_SERVICE='pt-admin-run' -p 9080:9080 -v ~/.config:/root/.config $PT_ADMIN_IMAGE

```

Navigate to browser: http://localhost:9080/webui


## Troubleshooting

### Error on missing protoc-gen-go

Sample error:
 protoc-gen-go: program not found or is not executable

Make sure protoc-gen-go plugin is installed
 ```shell
go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
```

Make sure to add to the PATH the location of protoc-gen-go
```shell
export PATH="$PATH:$HOME/go/bin"
```
or `gopath`, if `$HOME/go` folder doesn't exist:
```shell
export PATH="$PATH:$HOME/gopath/bin"
```

### Error when applying Terraform
Sample error:
 Error: Error when reading or editing Document: Delete "https://firestore.googleapis.com/v1/projects/test1-351108/databases/(default)/documents/pt-transactions/doc-u7q2e257ak406jc0?alt=json": dial tcp [2404:6800:4003:c0f::5f]:443: connect: cannot assign requested address

Re-run the `terraform apply` command.

### Permission Denied on Docker Daemon
Sample error:
 ERROR: failed to initialize builder project-v3-builder (project-v3-builder0): permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock: Get "http://%2Fvar%2Frun%2Fdocker.sock/v1.24/containers/buildx_buildkit_project-v3-builder0/json": dial unix /var/run/docker.sock: connect: permission denied
```shell
sudo chmod 666 /var/run/docker.sock
```

### Error on Not Enough Disk Space When Running make docker-buildx IMG=${PT_OPERATOR_IMAGE}
Sample error:
 ERROR: failed to solve: process "/bin/sh -c CGO_ENABLED=0 GOOS=${TARGETOS:-linux} GOARCH=${TARGETARCH} go build -a -o manager cmd/main.go" did not complete successfully: exit code: 2
Try to run the `make docker-buildx IMG=${PT_OPERATOR_IMAGE}` inside new (disk-space reset) Cloud Shell


## References
- [Taurus Configuration Syntax](https://gettaurus.org/docs/ConfigSyntax/)



