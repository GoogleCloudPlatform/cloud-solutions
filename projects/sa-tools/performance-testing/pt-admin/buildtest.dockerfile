# syntax=docker/dockerfile:1

# Note: Use this Dockerfile from the /projects/sa-tools/ and not
# from the gke-optimization/binpacker folder.

### Use node image as a builder for UI
FROM golang:1.20-alpine
ARG PROJECT_SUBDIRECTORY
WORKDIR "${PROJECT_SUBDIRECTORY}"

# Install required packages
RUN apk update \
    && apk add --no-cache protobuf-dev \
    # Install protoc-gen-go to generate go code from proto files
    && go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.28 \
    && go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.2

ENTRYPOINT [ "/bin/sh", "-e", "-x", "-c" ]
CMD [ " \
    protoc --go_out=. -I . proto/ptadmin.proto \
    && export GOPATH=/tmp/go && mkdir -p $GOPATH \
    && CGO_ENABLED=0 go build -a -o /tmp/go/pt-admin cmd/main.go \
  " ]
