
# Image URL to use all building/pushing image targets
IMG ?= ptadmin:latest
# Region to deploy Cloud Run
REGION ?= asia-southeast2

# Get the currently used golang install path (in GOPATH/bin, unless GOBIN is set)
ifeq (,$(shell go env GOBIN))
GOBIN=$(shell go env GOPATH)/bin
else
GOBIN=$(shell go env GOBIN)
endif

# Setting SHELL to bash allows bash commands to be executed by recipes.
# Options are set to exit when a recipe line exits non-zero or a piped command fails.
SHELL = /usr/bin/env bash -o pipefail
.SHELLFLAGS = -ec

.PHONY: all
all: build

##@ General
.PHONY: generate
generate:  ## Generate code from proto.
	protoc --go_out=. -I . proto/ptadmin.proto

.PHONY: fmt
fmt: ## Run go fmt against code.
	go fmt ./...

.PHONY: vet
vet: ## Run go vet against code.
	go vet ./...

.PHONY: test
test: generate fmt vet ## Run tests.
	go test ./... -coverprofile cover.out

##@ Build

.PHONY: build
build: generate fmt vet ## Build ptadmin binary.
	go build -o bin/ptadmin cmd/main.go

.PHONY: run
run: generate fmt vet ## Run ptadmin from your host.
	go run ./cmd/main.go


.PHONY: docker-push
docker-push: ## Push docker image with the manager.
	docker push ${IMG}

# PLATFORMS ?= linux/arm64,linux/amd64,linux/s390x,linux/ppc64le
PLATFORMS ?= linux/amd64
.PHONY: docker-buildx
docker-buildx: test ## Build and push docker image for the manager for cross-platform support
	cd ../ui && yarn install && yarn build
	cd ../pt-admin && cp -r ../ui/dist ./
	# copy existing Dockerfile and insert --platform=${BUILDPLATFORM} into Dockerfile.cross, and preserve the original Dockerfile
	sed -e '1 s/\(^FROM\)/FROM --platform=\$$\{BUILDPLATFORM\}/; t' -e ' 1,// s//FROM --platform=\$$\{BUILDPLATFORM\}/' Dockerfile > Dockerfile.cross
	- docker buildx create --name project-v3-builder
	docker buildx use project-v3-builder
	- docker buildx build --push --platform=$(PLATFORMS) --tag ${IMG} -f Dockerfile.cross .
	- docker buildx rm project-v3-builder
	rm Dockerfile.cross

##@ Deployment

ifndef ignore-not-found
	ignore-not-found = false
endif

.PHONY: deploy
deploy: build
	echo "Deploying ptadmin to Cloud Run..."
	gcloud run deploy ptadmin \
		--image ${IMG} \
		--platform managed \
		--region ${REGION} \
		--allow-unauthenticated \
		--set-env-vars "PTADMIN_COLLECTION=${PTADMIN_COLLECTION}
