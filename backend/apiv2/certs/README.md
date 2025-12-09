# SSL Certificates

This directory contains SSL certificates for HTTPS.

## Generating Certificates

Run the certificate generation script:

```bash
python generate_certs.py
```

This will create:
- `server_cert.pem` - Server certificate
- `server_key.pem` - Private key

## Security Note

These are **self-signed certificates** for development and ad-hoc sharing.

Browsers will show a security warning. Users need to:
1. Click "Advanced"
2. Click "Proceed to [hostname] (unsafe)"

For production use, consider using certificates from a trusted CA like Let's Encrypt.

## Certificate Details

- **Validity**: 365 days (configurable)
- **Key Size**: 2048-bit RSA
- **Algorithm**: SHA-256
- **SANs**: hostname, hostname.local, localhost
