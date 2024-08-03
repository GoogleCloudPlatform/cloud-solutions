# syntax=docker/dockerfile:1

# Note: Use this Dockerfile from the /projects/sa-tools/ and not
# from the gke-optimization/binpacker folder.

### Use node image as a builder for UI
FROM golang:1.22-alpine
ARG PROJECT_SUBDIRECTORY
WORKDIR "${PROJECT_SUBDIRECTORY}"

# Install required packages
RUN apk update \
    && apk add --no-cache protobuf-dev \
    # Install protoc-gen-go to generate go code from proto files
    && go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.28

ENTRYPOINT [ "/bin/sh", "-e", "-x", "-c" ]
CMD [ " \
    export GOPATH=/tmp/go && mkdir -p $GOPATH && \
    go mod download \
    && go generate ./... \
    && go test -v ./... \
  " ]
