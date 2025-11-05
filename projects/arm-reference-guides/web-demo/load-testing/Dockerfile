FROM golang:1.24-alpine AS builder

RUN apk add --no-cache \
  build-base \
  git

WORKDIR /app

ENV CGO_ENABLED=1
RUN go install go.k6.io/xk6/cmd/xk6@v1.2.3 \
  && xk6 build \
  --with github.com/grafana/xk6-sql@v1.0.5 \
  --with github.com/grafana/xk6-sql-driver-postgres@v0.1.1 \
  --with github.com/grafana/xk6-redis@v0.3.4

FROM alpine:3.22

COPY --from=builder /app/k6 /bin/

ENTRYPOINT ["k6"]
