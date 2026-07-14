-- Initial schema. Timestamps are INTEGER unix microseconds (UTC).
-- Foreign keys are enforced (PRAGMA foreign_keys=ON is set per connection).

CREATE TABLE users (
    id                 INTEGER PRIMARY KEY,
    email              TEXT    NOT NULL UNIQUE,
    password_hash      TEXT    NOT NULL,
    role               TEXT    NOT NULL CHECK (role IN ('admin', 'user')),
    is_default_pin     INTEGER NOT NULL DEFAULT 0,
    is_approved        INTEGER NOT NULL DEFAULT 0,
    created_at         INTEGER NOT NULL,
    last_login         INTEGER,
    cert_serial_number TEXT,
    cert_revoked       INTEGER NOT NULL DEFAULT 0,
    cert_issued_at     INTEGER,
    cert_expires_at    INTEGER
);

CREATE TABLE system_settings (
    id              INTEGER PRIMARY KEY,
    auth_method     TEXT    NOT NULL DEFAULT 'email+password',
    tls_enabled     INTEGER NOT NULL DEFAULT 1,
    https_port      INTEGER NOT NULL DEFAULT 8443,
    device_name     TEXT    NOT NULL DEFAULT '',
    updated_at      INTEGER NOT NULL,
    smtp_enabled    INTEGER NOT NULL DEFAULT 0,
    smtp_host       TEXT    NOT NULL DEFAULT '',
    smtp_port       INTEGER NOT NULL DEFAULT 587,
    smtp_username   TEXT    NOT NULL DEFAULT '',
    smtp_password   TEXT    NOT NULL DEFAULT '',
    smtp_from_email TEXT    NOT NULL DEFAULT '',
    smtp_use_tls    INTEGER NOT NULL DEFAULT 1,
    allowed_domains TEXT    NOT NULL DEFAULT ''
);

-- Tri-state user-level ACLs: 'allow'/'deny' override lower tiers, NULL defers.
CREATE TABLE folder_permissions (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    folder_path TEXT    NOT NULL,
    can_read    TEXT    CHECK (can_read IN ('allow', 'deny')),
    can_write   TEXT    CHECK (can_write IN ('allow', 'deny')),
    created_at  INTEGER NOT NULL,
    UNIQUE (user_id, folder_path)
);

CREATE TABLE domain_configs (
    id         INTEGER PRIMARY KEY,
    domain     TEXT    NOT NULL UNIQUE,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE TABLE domain_permissions (
    id          INTEGER PRIMARY KEY,
    domain_id   INTEGER NOT NULL REFERENCES domain_configs (id) ON DELETE CASCADE,
    folder_path TEXT    NOT NULL,
    can_read    INTEGER NOT NULL DEFAULT 0,
    can_write   INTEGER NOT NULL DEFAULT 0,
    created_at  INTEGER NOT NULL,
    UNIQUE (domain_id, folder_path)
);

CREATE TABLE groups (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL UNIQUE,
    description TEXT,
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL
);

CREATE TABLE group_permissions (
    id          INTEGER PRIMARY KEY,
    group_id    INTEGER NOT NULL REFERENCES groups (id) ON DELETE CASCADE,
    folder_path TEXT    NOT NULL,
    can_read    INTEGER NOT NULL DEFAULT 0,
    can_write   INTEGER NOT NULL DEFAULT 0,
    created_at  INTEGER NOT NULL,
    UNIQUE (group_id, folder_path)
);

CREATE TABLE group_memberships (
    id         INTEGER PRIMARY KEY,
    group_id   INTEGER NOT NULL REFERENCES groups (id) ON DELETE CASCADE,
    user_id    INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at INTEGER NOT NULL,
    UNIQUE (group_id, user_id)
);

-- Revocation history outlives the account (user references null out).
CREATE TABLE revoked_certificates (
    id            INTEGER PRIMARY KEY,
    serial_number TEXT    NOT NULL,
    user_id       INTEGER REFERENCES users (id) ON DELETE SET NULL,
    revoked_at    INTEGER NOT NULL,
    reason        TEXT    NOT NULL,
    revoked_by    INTEGER REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_revoked_certificates_serial ON revoked_certificates (serial_number);

CREATE TABLE mtls_mismatch_logs (
    id                    INTEGER PRIMARY KEY,
    presented_cn          TEXT    NOT NULL,
    authenticated_user_id INTEGER REFERENCES users (id) ON DELETE CASCADE,
    timestamp             INTEGER NOT NULL
);
CREATE INDEX ix_mtls_mismatch_logs_cn ON mtls_mismatch_logs (presented_cn);

CREATE TABLE audit_logs (
    id            INTEGER PRIMARY KEY,
    timestamp     INTEGER NOT NULL,
    user_id       INTEGER REFERENCES users (id) ON DELETE SET NULL,
    user_email    TEXT,
    action        TEXT    NOT NULL,
    target_type   TEXT,
    target_id     TEXT,
    description   TEXT,
    ip_address    TEXT,
    status        TEXT    NOT NULL DEFAULT 'success'
);
CREATE INDEX ix_audit_logs_timestamp ON audit_logs (timestamp);
CREATE INDEX ix_audit_logs_action ON audit_logs (action);
CREATE INDEX ix_audit_logs_timestamp_action ON audit_logs (timestamp, action);

-- Revocable bearer sessions; only the SHA-256 of the token is stored.
CREATE TABLE sessions (
    id         INTEGER PRIMARY KEY,
    token_hash TEXT    NOT NULL UNIQUE,
    user_id    INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    revoked_at INTEGER
);
CREATE INDEX ix_sessions_user ON sessions (user_id);

-- One-time certificate claim links; the certificate is generated at claim
-- time so no key material is stored.
CREATE TABLE cert_claims (
    id         INTEGER PRIMARY KEY,
    token_hash TEXT    NOT NULL UNIQUE,
    user_id    INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    used_at    INTEGER
);
CREATE INDEX ix_cert_claims_user ON cert_claims (user_id);
