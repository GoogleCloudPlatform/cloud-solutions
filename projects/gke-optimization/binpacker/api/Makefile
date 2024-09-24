# Copyright 2023 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

.PHONY: build test clean static_analysis lint vet fmt gen_proto

### Commands
GO           = go
GO_BUILD     = $(GO) build
GO_FORMAT    = $(GO) fmt
GOFMT        = gofmt
GO_LIST      = $(GO) list
GOLINT       = staticcheck
GO_TEST      = $(GO) test -v
GO_VET       = $(GO) vet
GO_LDFLAGS   = -ldflags="-s -w"
GO_RUN       = $(GO) run
GO_GENERATE  = $(GO) generate ./...
PROTOC       = protoc
GLOG_FLAG    = -logtostderr
PROJECT_FLAG = -project

### Target parameters
EXECUTABLES     = bin/binpacker
PKGROOT         = github.com/GoogleCloudPlatform/cloud-solutions/projects/sa-tools/gke_optimization/binpacker/api
GO_MAIN_PACKAGE = github.com/GoogleCloudPlatform/cloud-solutions/projects/sa-tools/gke_optimization/binpacker/api/cmd/binpacker
TARGETS         = $(EXECUTABLES)
GO_PKGROOT      = ./...
GO_PACKAGES     = $(shell $(GO_LIST) $(GO_PKGROOT) | grep -v vendor)

### Build rules
build: clean $(TARGETS)

test:
	$(GO_TEST) $(GO_PKGROOT)

clean:
	rm -rf $(TARGETS) ./vendor

static_analysis: lint vet

lint:
	$(GOLINT) $(GO_PKGROOT)
vet:
	$(GO_VET) $(GO_PACKAGES)
fmt:
	$(GO_FORMAT) $(GO_PKGROOT)

run:
	$(EXECUTABLES) $(GLOG_FLAG)

genproto:
	$(GO_GENERATE)

bin/binpacker:
	$(GO_BUILD) $(GO_LDFLAGS) -o $@ $(GO_MAIN_PACKAGE)
