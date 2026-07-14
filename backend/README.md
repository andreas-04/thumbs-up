# TerraCrate Backend (Go)

Go rewrite of the original Python/Flask backend, serving the `/api/v1` REST
surface (plus `/health`) over HTTPS. Key architectural points:

- **PKI**: a long-lived dedicated CA signs the server leaf certificate, mTLS
  client certificates, and the CRL; rotating the server cert never
  invalidates issued client certs. nginx validates clients against
  `ca_cert.pem`.
- **Sessions**: opaque bearer tokens backed by a `sessions` table (only the
  SHA-256 is stored) — logout revokes, refresh rotates, password changes
  revoke everything.
- **Certificate delivery**: one-time expiring claim links
  (`POST /api/v1/certs/claim`); the `.p12` is generated at redemption time
  and never stored or emailed.
- **Database**: SQLite in WAL mode with enforced foreign keys and embedded
  versioned migrations (`internal/store/migrations`); timestamps are INTEGER
  unix microseconds.

## API source of truth

The wire contract lives in [`../proto/terracrate/v1`](../proto/terracrate/v1):
every endpoint is a protobuf RPC with a `google.api.http` annotation naming
its REST route, and every request/response body is a protobuf message.
Responses use the canonical proto3 JSON mapping (`protojson` with
`EmitUnpopulated`): lowerCamelCase keys, RFC 3339 timestamps, `int64` values
encoded as strings, unset `optional` scalars omitted, and unset message
fields as `null`.

Code is generated with [buf](https://buf.build):

```sh
go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
buf lint          # from the repo root
buf generate      # regenerates backend/gen (committed)
```

Generated code is committed: `backend/gen` (Go, protoc-gen-go) and
`frontend/src/gen` (TypeScript, protoc-gen-es with `json_types`) — the
frontend's `api.ts` derives its types from the generated JSON shapes, so
wire drift is a compile error on both sides. `internal/httpapi/routes_test.go`
additionally walks the proto annotations and fails if any declared route is
not served by the mux.

## Layout

| Path | Purpose |
| --- | --- |
| `cmd/server` | entry point: config, DB init, cert bootstrap, HTTPS server |
| `gen/terracrate/v1` | buf-generated Go types (do not edit) |
| `internal/httpapi` | stdlib `net/http` handlers, CORS, auth middleware, mTLS header checks |
| `internal/store` | `database/sql` + pure-Go SQLite (WAL, enforced FKs, embedded migrations) |
| `internal/auth` | argon2id password hashing + opaque session tokens (hash-at-rest) |
| `internal/perms` | layered domain → group → user permission resolver |
| `internal/certs` | dedicated CA, server leaf, mTLS client certs (.p12), CRL generation |
| `internal/mailer` | invite/approval/revocation emails (one-time claim links) over stdlib `net/smtp` |
| `internal/audit` | best-effort audit logging |

Business logic is standard library throughout; the only runtime dependencies
are the protobuf runtime, the pure-Go SQLite driver, `x/crypto` (argon2id),
`x/text` (filename normalisation), and `go-pkcs12`.

## Development

```sh
go test ./...        # unit tests (resolver, auth, certs, handlers)
go vet ./...
go build ./cmd/server
```

Run locally (generates a self-signed cert and SQLite DB on first boot):

```sh
ADMIN_PIN=123456 go run ./cmd/server
```

Configuration uses the same environment variables as before (`PORT`,
`STORAGE_PATH`, `CERT_PATH`, `KEY_PATH`, `DATABASE_URI`, `ADMIN_PIN`,
`ENABLE_UPLOADS`, `ENABLE_DELETE`, `CORS_ORIGINS`, …); see
`internal/config/config.go`.
