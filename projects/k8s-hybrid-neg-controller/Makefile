# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

PKG := github.com/googlecloudplatform/k8s-hybrid-neg-controller

# Set global Skaffold options
export SKAFFOLD_BUILD_CONCURRENCY:=0
export SKAFFOLD_CLEANUP:=false
export SKAFFOLD_DETECT_MINIKUBE:=false
export SKAFFOLD_INTERACTIVE:=false
export SKAFFOLD_SKIP_TESTS:=true
export SKAFFOLD_UPDATE_CHECK:=false

.PHONY: all
all: clean generate format lint test

# run builds and deploys the controller, and tails the log.
.PHONY: run
run: check-skaffold
	skaffold run --tail

# run-no-tail builds and deploys the controller, but does not tail the log.
.PHONY: run-no-tail
run-no-tail: check-skaffold
	skaffold run --tail=false

# dev builds and deploys the controller, and sets up file watching for
# automatic image rebuilds and redeploys on source code changes.
.PHONY: dev
dev: check-skaffold
	skaffold dev

# tail the logs of the controller.
.PHONY: tail
tail: check-kubectl
	kubectl logs --all-containers --follow --namespace=hybrid-neg-system deployment/hybrid-neg-controller-manager

# delete-apps deletes the controller Deployment and Service resources from the k8s cluster.
.PHONY: delete-apps
delete-apps: check-kubectl
	kubectl delete --ignore-not-found --namespace=hybrid-neg-system deployment hybrid-neg-controller-manager
	kubectl delete --ignore-not-found --namespace=hybrid-neg-system service hybrid-neg-controller-manager-metrics-service
	kubectl delete --ignore-not-found --namespace=hybrid-neg-system configmap --selector="app.kubernetes.io/part-of"=hybrid-neg-controller

# delete deletes all of the controller resources from the k8s cluster.
.PHONY: delete
delete: check-skaffold
	skaffold delete

# kind-create creates a kind Kubernetes cluster called `hybrid-neg`.
# The kubectl context will be called `kind-hybrid-neg`.
.PHONY: kind-create
kind-create: check-kind check-kubectl
	kind create cluster --config=hack/kind-cluster-config.yaml
	kubectl config set-context --current --namespace=hybrid-neg-system

# kind-delete deletes the kind Kubernetes cluster.
.PHONY: kind-delete
kind-delete: check-kind
	kind delete cluster --name=hybrid-neg

.PHONY: build
build: check-go
	CGO_ENABLED=0 go build $(PKG)

.PHONY: clean
clean: check-go
	go clean -i $(PKG)/...

.PHONY: deps
deps: check-go
	go mod download

.PHONY: format
format: check-goimports
	goimports -e -l -local $(PKG) -w .

.PHONY: generate
generate: check-go
	go generate $(PKG)/...

.PHONY: image
image: check-skaffold
	skaffold build

.PHONY: imageko
imageko: check-ko
	ko build --base-import-paths --local --sbom=none

.PHONY: lint
lint: check-golangci-lint format
	golangci-lint -v run

.PHONY: manifests
manifests: check-skaffold
	@mkdir -p deploy
	skaffold render --digest-source=local --loud=true --output=deploy/hybrid-neg.yaml

.PHONY: manifests-eks
manifests-eks: check-skaffold k8s/components/zone-mapping-flag/patch-zone-mapping-flag.yaml
	@mkdir -p deploy
	skaffold render --digest-source=local --loud=true --output=deploy/hybrid-neg-eks.yaml --profile=eks

.PHONY: manifests-gke
manifests-gke: check-skaffold k8s/components/gke-workload-identity-federation/patch-gke-workload-identity-federation.yaml
	@mkdir -p deploy
	skaffold render --digest-source=local --loud=true --output=deploy/hybrid-neg-gke.yaml --profile=gke

.PHONY: manifests-kind
manifests-kind: check-skaffold k8s/components/google-cloud-project-id/patch-google-cloud-project-id.yaml
	@mkdir -p deploy
	skaffold render --digest-source=local --loud=true --output=deploy/hybrid-neg-kind.yaml --profile=kind

.PHONY: manifests-nobuild
manifests-nobuild: check-skaffold
	@skaffold render --digest-source=none --loud=false

.PHONY: test
test: check-go
	go test -count 1 -race -timeout 3m -v $(PKG)/...

.PHONY: tidy
tidy: check-go
	go mod tidy

.PHONY: updatedeps
updatedeps: check-go
	go get -t -u $(PKG)/...

.PHONY: check-go
check-go:
	@if ! which go > /dev/null; then \
		echo "error: go is not installed: https://go.dev/doc/install" >&2; \
		exit 1; \
	fi

.PHONY: check-goimports
check-goimports:
	@if ! which goimports > /dev/null; then \
		echo "error: goimports is not installed: https://pkg.go.dev/golang.org/x/tools/cmd/goimports" >&2; \
		exit 1; \
	fi

.PHONY: check-golangci-lint
check-golangci-lint:
	@if ! which golangci-lint > /dev/null; then \
		echo "error: golangci-lint is not installed: https://golangci-lint.run/welcome/install/" >&2; \
		exit 1; \
	fi

.PHONY: check-kind
check-kind:
	@if ! which kind > /dev/null; then \
		echo "error: kind is not installed: https://kind.sigs.k8s.io/#installation-and-usage" >&2; \
		exit 1; \
	fi

.PHONY: check-ko
check-ko: check-go
	@if ! which ko > /dev/null; then \
		echo "error: ko is not installed: https://ko.build/install/" >&2; \
		exit 1; \
	fi

.PHONY: check-kubectl
check-kubectl:
	@if ! which kubectl > /dev/null; then \
		echo "error: kubectl is not installed: https://kubernetes.io/docs/tasks/tools/#kubectl" >&2; \
		exit 1; \
	fi

.PHONY: check-kustomize
check-kustomize: check-kubectl
	@if ! which kustomize > /dev/null; then \
		echo "error: kustomize is not installed: https://kubectl.docs.kubernetes.io/installation/kustomize/" >&2; \
		exit 1; \
	fi

.PHONY: check-skaffold
check-skaffold: check-go check-kustomize
	@if ! which skaffold > /dev/null; then \
		echo "error: skaffold is not installed: https://skaffold.dev/docs/install/" >&2; \
		exit 1; \
	fi
