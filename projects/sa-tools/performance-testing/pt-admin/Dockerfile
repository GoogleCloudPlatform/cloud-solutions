# Build pt-admin binary
FROM golang:1.19 as builder

# ARG
ARG TARGETOS
ARG TARGETARCH

# Set the Current Working Directory inside the container
WORKDIR /workspace

# Copy the Go Modules manifests
COPY go.mod go.mod
COPY go.sum go.sum
# cache deps before building and copying source so that we don't need to re-download as much
# and so that source changes don't invalidate our downloaded layer
RUN go mod download

# Copy the go source
COPY cmd/main.go cmd/main.go
COPY api/ api/
COPY internal/ internal/

#build the binary
RUN CGO_ENABLED=0 GOOS=${TARGETOS:-linux} GOARCH=${TARGETARCH} go build -a -o pt-admin cmd/main.go

# start from scratch
# FROM gcr.io/distroless/static:nonroot
FROM gcr.io/distroless/static-debian11:debug

# Copy our static executable
WORKDIR /
COPY --from=builder /workspace/pt-admin .
COPY ./manifests /manifests
COPY ./dist /dist
# USER 65532:65532

ENTRYPOINT ["/pt-admin"]