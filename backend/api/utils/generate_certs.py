#!/usr/bin/env python3
"""
Self-signed certificate generator for TerraCrate server.
Generates server certificate and private key for HTTPS.
"""

import ipaddress
import os
import socket
from datetime import UTC, datetime, timedelta

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def generate_self_signed_cert(
    cert_path="./certs/server_cert.pem", key_path="./certs/server_key.pem", hostname=None, validity_days=365
):
    """
    Generate a self-signed certificate for HTTPS.

    Args:
        cert_path: Path to save certificate
        key_path: Path to save private key
        hostname: Server hostname (defaults to system hostname)
        validity_days: Certificate validity period in days
    """

    # Ensure certs directory exists
    os.makedirs(os.path.dirname(cert_path), exist_ok=True)

    # Get hostname (prefer MDNS_HOSTNAME env var for consistent cert SANs)
    if hostname is None:
        hostname = os.environ.get("MDNS_HOSTNAME", socket.gethostname())

    print(f"🔐 Generating self-signed certificate for '{hostname}'...")

    # Generate private key
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())

    # Certificate subject and issuer (same for self-signed)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TerraCrate"),
            x509.NameAttribute(NameOID.COMMON_NAME, hostname),
        ]
    )

    # Get IP address
    try:
        ip_str = socket.gethostbyname(socket.gethostname())
        ip_addr = ipaddress.ip_address(ip_str)
    except Exception:
        ip_addr = ipaddress.ip_address("127.0.0.1")

    # Build certificate
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC))
        .not_valid_after(datetime.now(UTC) + timedelta(days=validity_days))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName(hostname),
                    x509.DNSName(f"{hostname}.local"),
                    x509.DNSName("localhost"),
                    x509.IPAddress(ip_addr),
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=0),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                key_cert_sign=True,
                key_agreement=False,
                content_commitment=False,
                data_encipherment=False,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(private_key, hashes.SHA256(), default_backend())
    )

    # Write certificate to file
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    # Write private key to file
    with open(key_path, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    print("✅ Certificate generated successfully!")
    print(f"   📄 Certificate: {cert_path}")
    print(f"   🔑 Private Key: {key_path}")
    print(f"   📅 Valid until: {cert.not_valid_after}")
    print(f"   🌐 Hostnames: {hostname}, {hostname}.local, localhost")
    print()
    print("⚠️  This is a SELF-SIGNED certificate. Browsers will show a warning.")
    print("   Users will need to accept the certificate to proceed.")

    return cert_path, key_path


def generate_client_cert(ca_cert_path, ca_key_path, user_email, validity_days=365):
    """
    Generate a client certificate signed by the server CA for mTLS.

    Args:
        ca_cert_path: Path to the CA certificate (server cert acting as CA)
        ca_key_path: Path to the CA private key
        user_email: Email address of the user (used as CN and SAN)
        validity_days: Certificate validity period in days

    Returns:
        Tuple of (client_cert_pem: bytes, client_key_pem: bytes) in PEM format.
    """
    # Load CA certificate and key
    with open(ca_cert_path, "rb") as f:
        ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())

    with open(ca_key_path, "rb") as f:
        ca_key = serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())

    # Generate client private key
    client_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())

    # Build client certificate subject
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "thumbsup"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "member"),
            x509.NameAttribute(NameOID.COMMON_NAME, user_email),
        ]
    )

    # Build and sign the client certificate
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(client_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC))
        .not_valid_after(datetime.now(UTC) + timedelta(days=validity_days))
        .add_extension(
            x509.SubjectAlternativeName([x509.RFC822Name(user_email)]),
            critical=False,
        )
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                key_cert_sign=False,
                key_agreement=False,
                content_commitment=False,
                data_encipherment=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH]),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256(), default_backend())
    )

    # Serialize to PEM bytes
    client_cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    client_key_pem = client_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    return client_cert_pem, client_key_pem, cert.serial_number


def generate_client_p12(ca_cert_path, ca_key_path, user_email, p12_password=None, validity_days=365):
    """
    Generate a PKCS#12 (.p12) bundle containing the client certificate,
    private key, and the CA certificate chain.

    Args:
        ca_cert_path: Path to the CA certificate (server cert acting as CA)
        ca_key_path: Path to the CA private key
        user_email: Email address of the user (used as CN and SAN)
        p12_password: Optional password to protect the .p12 file (bytes or str).
                      If None, a random password is generated and returned.
        validity_days: Certificate validity period in days

    Returns:
        Tuple of (p12_bytes: bytes, password: str).
    """
    import secrets as _secrets

    from cryptography.hazmat.primitives.serialization import pkcs12

    # Generate the client cert + key in PEM form first
    client_cert_pem, client_key_pem, serial_number = generate_client_cert(
        ca_cert_path, ca_key_path, user_email, validity_days=validity_days
    )

    # Re-load them as objects for PKCS#12 serialization
    client_cert = x509.load_pem_x509_certificate(client_cert_pem, default_backend())
    client_key = serialization.load_pem_private_key(client_key_pem, password=None, backend=default_backend())

    # Load CA cert to include in the chain
    with open(ca_cert_path, "rb") as f:
        ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())

    # Resolve password
    if p12_password is None:
        password_str = _secrets.token_urlsafe(16)
    elif isinstance(p12_password, bytes):
        password_str = p12_password.decode("utf-8")
    else:
        password_str = p12_password

    password_bytes = password_str.encode("utf-8")

    # Build PKCS#12 bundle
    p12_bytes = pkcs12.serialize_key_and_certificates(
        name=user_email.encode("utf-8"),
        key=client_key,
        cert=client_cert,
        cas=[ca_cert],
        encryption_algorithm=serialization.BestAvailableEncryption(password_bytes),
    )

    return p12_bytes, password_str, serial_number, client_cert.not_valid_before_utc, client_cert.not_valid_after_utc


def generate_crl(ca_cert_path, ca_key_path, revoked_entries):
    """Generate a PEM-encoded Certificate Revocation List (CRL).

    Args:
        ca_cert_path: Path to the CA certificate
        ca_key_path: Path to the CA private key
        revoked_entries: List of dicts with 'serial_number' (int) and 'revoked_at' (datetime)

    Returns:
        PEM-encoded CRL bytes.
    """
    with open(ca_cert_path, "rb") as f:
        ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())

    with open(ca_key_path, "rb") as f:
        ca_key = serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())

    builder = x509.CertificateRevocationListBuilder()
    builder = builder.issuer_name(ca_cert.subject)
    builder = builder.last_update(datetime.now(UTC))
    builder = builder.next_update(datetime.now(UTC) + timedelta(days=7))

    for entry in revoked_entries:
        revoked = (
            x509.RevokedCertificateBuilder()
            .serial_number(entry["serial_number"])
            .revocation_date(entry["revoked_at"])
            .build()
        )
        builder = builder.add_revoked_certificate(revoked)

    crl = builder.sign(ca_key, hashes.SHA256(), default_backend())
    return crl.public_bytes(serialization.Encoding.PEM)


def update_crl_file(crl_pem_bytes, crl_path="./certs/crl.pem"):
    """Atomically write a CRL file to disk.

    Writes to a temp file first, then renames to avoid partial reads by nginx.
    """
    import tempfile

    os.makedirs(os.path.dirname(crl_path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(crl_path), suffix=".tmp")
    try:
        os.write(fd, crl_pem_bytes)
    finally:
        os.close(fd)
    os.replace(tmp_path, crl_path)


def _crl_matches_ca(crl_path, ca_cert_path):
    """Return True if the existing CRL was signed by the current CA."""
    try:
        with open(crl_path, "rb") as f:
            crl = x509.load_pem_x509_crl(f.read(), default_backend())
        with open(ca_cert_path, "rb") as f:
            ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())
        return crl.is_signature_valid(ca_cert.public_key())
    except Exception:
        return False


def generate_empty_crl(ca_cert_path, ca_key_path, crl_path="./certs/crl.pem"):
    """Generate an empty CRL file if none exists or the existing one doesn't match the current CA."""
    if os.path.exists(crl_path) and _crl_matches_ca(crl_path, ca_cert_path):
        return
    crl_bytes = generate_crl(ca_cert_path, ca_key_path, [])
    update_crl_file(crl_bytes, crl_path)
    print(f"✅ Empty CRL generated at {crl_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate self-signed SSL certificate")
    parser.add_argument("--hostname", help="Server hostname (default: system hostname)", default=None)
    parser.add_argument("--days", type=int, help="Certificate validity in days (default: 365)", default=365)
    parser.add_argument(
        "--cert-path",
        help="Path to save certificate (default: ./certs/server_cert.pem)",
        default="./certs/server_cert.pem",
    )
    parser.add_argument(
        "--key-path",
        help="Path to save private key (default: ./certs/server_key.pem)",
        default="./certs/server_key.pem",
    )

    args = parser.parse_args()

    generate_self_signed_cert(
        cert_path=args.cert_path, key_path=args.key_path, hostname=args.hostname, validity_days=args.days
    )
