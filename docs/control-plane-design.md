# Control Plane Design

## Scope and Assumptions
- Single-tenant: one control plane instance manages a single organization and its Raspberry Pi fleet.
- Lightweight deployment: run the control plane as a standalone service (container or VM); no Kubernetes required.
- Offline-first: Pis continue to serve local NAS duties with their last known policy when the control plane is unreachable.
- External services allowed: the control plane may run off-device (e.g., cloud VM) and persist metadata in Postgres.

## Components
- **Control Plane API (Go or Python)** – lightweight REST service that exposes enrollment and RBAC management endpoints; deployable via Docker Compose or systemd.
- **Postgres** – stores user accounts, enrollment tokens, Pi records, RBAC policies, certificate metadata, and audit logs.
- **Web UI (React)** – single admin console for fleet management; reuses existing frontend assets where possible.
- **Certificate Authority Service** – issues client/device certificates with embedded role attributes and handles revocation lists; may be integrated into the Control Plane API.
- **Pi Agent** – minimal daemon on every Raspberry Pi responsible for enrollment, periodic policy pulls, and local enforcement (iptables, NFS export updates).
- API reference: see `docs/control-plane-api.yaml` for the sample OpenAPI surface.

## Data Model (High-Level)
- `users` – admin/operator accounts
- `enrollment_tokens` – hashed enrollment secrets, expiry, and associated admin.
- `devices` – registered Pis, hardware identifiers, issued device certificates, heartbeat timestamps, desired/actual policy versions.
- `rbac_policies` – role definitions and the mapping to NAS permissions (export paths, access modes, client IP scopes).
- `client_certificates` – issued user/client certs with role attributes and validity windows.
- `audit_events` – enrollment attempts, policy updates, revocations.

## Enrollment Workflows

### Admin Bootstrap (Control Plane with No Devices Yet)
1. Admin signs up via the Web UI, creating the first account; system marks this user as the organization owner.
2. UI directs the admin to “Enroll first Pi” and prompts for token creation.
3. Backend generates an enrollment token (single-use secret + optional hardware binding), stores a hashed copy with an expiry, and logs the event.
4. Admin downloads a bootstrap bundle containing:
   - Control plane endpoint metadata.
   - CA root certificates for future mutual TLS sessions.
   - The enrollment token (string and QR).

### First Pi Claim (No Existing Synced Cluster)
1. Admin transfers the bootstrap bundle to the Pi (e.g., USB, LAN CLI).
2. Pi agent starts in **ENROLLING** mode, presenting:
   - Enrollment token.
   - Hardware fingerprint (serial, MAC, TPM attestation when available).
3. Backend validates the token (not expired, unused, bound to requesting admin/hardware).
4. Backend issues a short-lived enrollment certificate so the Pi can immediately switch to mutual TLS for follow-up calls.
5. Backend provisions a long-lived device certificate (with the Pi’s identity) and returns control plane endpoint configuration plus initial polling cadence.
6. Backend marks the token as consumed, creates the `device` record, and flags the organization as “fleet initialized”.
    7. Pi agent transitions to **REGISTERED** state, pulls initial RBAC policy (defaults to deny until explicitly configured), and returns to idle until the next policy poll interval.

### Additional Pi Enrollment
1. Admin generates a new one-time token in the UI (optionally scoped to a specific hardware ID).
2. Pi agent repeats the claim process above; backend attaches the Pi to the existing fleet and shares current RBAC/policy bundles.
3. If the Pi was operating standalone prior to enrollment, the agent reconciles local state with the desired state fetched from the control plane before enabling optional sync features.

## RBAC Policy Distribution
- Admin defines roles and permissions in the Web UI (e.g., `viewer`, `operator`, `sync-peer`).
- Policies translate to concrete enforcement artifacts:
  - Firewall rules (iptables) for allowed client IPs/ports.
  - NFS export entries and access modes.
  - Future sync permissions (allowed peer Pis).
- Backend version-controls policies and pushes deltas to Pis; agents apply updates atomically and acknowledge success or failure.
- Each Pi maintains a cached policy bundle to continue enforcement during control plane outages.
- RBAC change workflow:
  1. Admin submits role or policy edits in the UI.
  2. Control Plane API validates the request, persists the new version, and records an audit event.
    3. Agents receive the updated policy on their next scheduled poll and apply it locally.
  4. Successful updates trigger acknowledgments; failures roll back and raise alerts in the UI.

## Client Credential Lifecycle
1. Admin invites or approves a client user in the UI.
2. Client submits a CSR (CLI or web upload) referencing requested roles.
3. Backend validates requested roles against admin-approved assignments and issues a client certificate embedding roles as custom OID attributes.
4. Pi agents trust the control plane CA and validate role attributes on incoming connections; mismatched or revoked roles trigger denial and audit events.
5. Certificates use short validity periods (e.g., 30 days); the control plane provides renewal reminders and revocation endpoints.

## Failure and Revocation Handling
- **Token misuse** – tokens expire quickly (e.g., 24 hours) and are single-use; admins can revoke outstanding tokens immediately.
- **Device compromise** – admin revokes the Pi’s device certificate; backend pushes revocation notice, other Pis stop peering with the compromised device.
- **Control plane outage** – Pis continue with cached policies, log locally, and queue telemetry until connectivity is restored.
- **Policy rollback** – backend keeps previous policy versions; admins can revert and agents roll back automatically on failure acknowledgment.

## Open Questions
- Should enrollment tokens be bound to hardware attestation to reduce reuse risk?
- How aggressive should client certificate lifetimes be to balance security with operator overhead?
