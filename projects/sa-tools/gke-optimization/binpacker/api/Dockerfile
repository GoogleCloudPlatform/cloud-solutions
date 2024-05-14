# 1st builder for backend
# Use golang image as a builder for backend
FROM golang:1.19-alpine AS builder

# Create and set workdir
WORKDIR /app

# Copy `go.mod` for definitions and `go.sum` to invalidate the next layer
# in case of a change in the dependencies
COPY ./go.mod ./go.sum ./

# Install git to be used "go mod download"
RUN apk add --no-cache git \
    # Download dependencies
    && go mod download

# Copy all files and build an executable
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -v -o binpacker github.com/GoogleCloudPlatform/cloud-solutions/projects/sa-tools/gke_optimization/binpacker/api/cmd/binpacker

## Image to run the backend and the frontend
FROM alpine:3.18
RUN apk add --no-cache ca-certificates

COPY --from=builder /app/binpacker /

EXPOSE 8080
ENTRYPOINT ["/binpacker", "-logtostderr"]
