### Note: Use this Dockerfile from the repo root and not from the gke-optimization/binpacker folder

### Use node image as a builder for UI
FROM node:18-alpine as ui-builder
COPY . /sa-tools-src
WORKDIR /sa-tools-src/gke-optimization/binpacker/ui

# Install required packages
RUN apk update && apk add --no-cache protobuf-dev

# Build React UI Artifacts
RUN yarn install
RUN yarn genproto
RUN yarn test
RUN yarn build

### Use golang image as a builder for backend APIs
FROM golang:1.20-alpine AS api-builder
COPY . /sa-tools-src
WORKDIR /sa-tools-src/gke-optimization/binpacker/api

# Install required packages
RUN apk update && apk add --no-cache git protobuf-dev

# Install protoc-gen-go to generate go code from proto files
RUN go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.28

# Build API binary
RUN go mod download
RUN go generate ./...
RUN go test -v ./...
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -v -o binpacker github.com/GoogleCloudPlatform/cloud-solutions/projects/sa-tools/gke_optimization/binpacker/api/cmd/binpacker

### Use alpine image as a base image
FROM alpine:3.18

# Install required packages
RUN apk add --no-cache ca-certificates

# Frontend code should be stored in /static/
COPY --from=ui-builder /sa-tools-src/gke-optimization/binpacker/ui/dist ./static/
COPY --from=api-builder /sa-tools-src/gke-optimization/binpacker/api/binpacker ./

# Set home directory to root to inject the application default credential when running the container
ENV HOME /

ENTRYPOINT ["/binpacker", "-logtostderr"]
