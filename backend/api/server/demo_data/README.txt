Welcome to ThumbsUp Secure NAS!
================================

This is a demonstration secure network-attached storage system.

Your files are protected by:
- mTLS authentication
- Certificate-based firewall rules
- Per-client NFS exports
- LUKS encryption (when deployed to hardware)

Architecture:
------------
1. Device remains dormant until activated
2. Manual activation triggers mDNS service discovery
3. Clients authenticate using X.509 certificates
4. Dynamic firewall rules grant access per client IP
5. NFS exports configured for authenticated clients only
6. Storage auto-locks when all clients disconnect

Security Features:
-----------------
✓ Mutual TLS (mTLS) authentication
✓ Certificate validation against local CA
✓ IP-based access control via iptables
✓ Client-specific NFS exports
✓ Encrypted storage at rest (LUKS)
✓ Session logging and audit trail
✓ Automatic dormant mode after inactivity

Created: 2025-10-23
Service: _thumbsup._tcp
