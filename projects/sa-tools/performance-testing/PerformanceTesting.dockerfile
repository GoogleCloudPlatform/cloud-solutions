### Note: Use this Dockerfile from the repo root and not from the diagrams2terraform folder
FROM node:18 AS build-ui-server
COPY . /sa-tools-src

### Build React UI Artifacts
WORKDIR /sa-tools-src/performance-testing/ui
RUN yarn install
RUN yarn style-check
RUN yarn run build


## Build pt-admin binary
FROM golang:1.19 as build-pt-admin
COPY . /sa-tools-src

## Set the Current Working Directory inside the container
WORKDIR /sa-tools-src/performance-testing/pt-admin

## cache deps before building
RUN go mod tidy

## Install protoc & related plugins
RUN apt-get update && apt-get -y upgrade
RUN apt-get install -y zip unzip
RUN curl -LO "https://github.com/protocolbuffers/protobuf/releases/download/v22.3/protoc-22.3-linux-x86_64.zip"
RUN mkdir /protoc && unzip protoc-22.3-linux-x86_64.zip -d /protoc
RUN go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.28
RUN go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.2

## Generate the protobuf code
RUN /protoc/bin/protoc --go_out=. -I . proto/ptadmin.proto
## Build the binary
RUN CGO_ENABLED=0 go build -a -o pt-admin cmd/main.go



## Start from scratch to build 
FROM gcr.io/distroless/static:nonroot

## Copy our static executable
WORKDIR /
### Copy pt-admin binary from pt-admin build
COPY --from=build-pt-admin /sa-tools-src/performance-testing/pt-admin/pt-admin .
### Copy manifests from pt-admin build
COPY --from=build-pt-admin /sa-tools-src/performance-testing/pt-admin/manifests /manifests

### Copy UI Artefacts from UI build
COPY --from=build-ui-server /sa-tools-src/performance-testing/ui/dist /dist

USER 65532:65532
ENTRYPOINT ["/pt-admin"]