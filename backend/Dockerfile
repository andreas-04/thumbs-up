# Dockerfile for the TerraCrate Backend API (Go)
# The API contract is generated from proto/terracrate/v1 (see backend/gen,
# committed) so the image build needs only the Go toolchain.

FROM golang:1.26.4-alpine AS builder

WORKDIR /src

# Cache module downloads separately from source changes.
COPY go.mod go.sum ./
RUN go mod download

COPY cmd/ ./cmd/
COPY internal/ ./internal/
COPY gen/ ./gen/

RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /terracrate-server ./cmd/server

FROM alpine:3.21

# CA roots for outbound SMTP TLS; wget (busybox) for the healthcheck.
RUN apk add --no-cache ca-certificates tzdata

WORKDIR /app
COPY --from=builder /terracrate-server /usr/local/bin/terracrate-server

RUN mkdir -p /app/certs /app/storage /app/data

# HTTPS port (matches the legacy Flask default)
EXPOSE 8443

ENV HOST=0.0.0.0
ENV PORT=8443
ENV STORAGE_PATH=/app/storage
ENV CERT_PATH=/app/certs/server_cert.pem
ENV KEY_PATH=/app/certs/server_key.pem
ENV DATABASE_URI=sqlite:////app/data/terracrate.db
ENV TOKEN_EXPIRY_HOURS=24
ENV ENABLE_UPLOADS=true
ENV ENABLE_DELETE=false
ENV SERVICE_NAME="TerraCrate File Share"
ENV MAX_UPLOAD_SIZE=104857600

# ADMIN_PIN MUST be provided (docker run -e / compose); startup fails without it.

VOLUME ["/app/storage", "/app/data"]

ENTRYPOINT ["terracrate-server"]
