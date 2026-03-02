# HTTPS Options for ThumbsUp

ThumbsUp is a self-hosted, local-network-only application. Below is a summary of HTTPS certificate options considered.

## Options Evaluated

| Solution | Portable | Trusted by browsers | Zero setup per device |
|----------|----------|---------------------|-----------------------|
| Self-signed | ✅ | ❌ (one-time browser warning) | ❌ |
| mkcert | ✅ | ✅ (if CA installed per device) | ❌ |
| Tailscale | ✅ | ✅ (requires Tailscale on each device) | ❌ |
| DuckDNS + Let's Encrypt | ❌ (breaks on network change) | ✅ | ✅ |

## Why Let's Encrypt / Certbot Is Impractical Here

Let's Encrypt requires domain ownership verification. While the DNS-01 challenge avoids needing public port access, it ties the certificate to a domain pointing to a local IP — which breaks whenever the Pi moves to a different network.

## Why Tailscale Doesn't Fully Fit

Tailscale provides a valid, universally trusted cert via `tailscale cert`, but every client device must have Tailscale installed and be joined to the Tailnet. This is too much friction for a general-purpose local network app.

## Recommendation

**Self-signed certificates** are the most practical choice for a portable self-hosted app. This is the approach used by projects like Synology DSM, TrueNAS, and Home Assistant. The browser warning only appears once per device and can be dismissed permanently.

A potential improvement would be to make it easier for users to install the local CA on their devices to eliminate the warning altogether.
