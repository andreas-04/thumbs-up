#!/usr/bin/env python3
"""
Self-signed certificate generator for ThumbsUp server.
Generates server certificate and private key for HTTPS.
"""

import os
import ipaddress
from datetime import datetime, timedelta, timezone
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtensionOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import socket


def generate_self_signed_cert(
    cert_path="./certs/server_cert.pem",
    key_path="./certs/server_key.pem",
    hostname=None,
    validity_days=365
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
    
    # Get hostname
    if hostname is None:
        hostname = socket.gethostname()
    
    print(f"🔐 Generating self-signed certificate for '{hostname}'...")
    
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    # Certificate subject and issuer (same for self-signed)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ThumbsUp"),
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),
    ])
    
    # Get IP address
    try:
        ip_str = socket.gethostbyname(socket.gethostname())
        ip_addr = ipaddress.ip_address(ip_str)
    except:
        ip_addr = ipaddress.ip_address('127.0.0.1')
    
    # Build certificate
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=validity_days))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(hostname),
                x509.DNSName(f"{hostname}.local"),
                x509.DNSName("localhost"),
                x509.IPAddress(ip_addr),
                x509.IPAddress(ipaddress.ip_address('127.0.0.1')),
            ]),
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
                crl_sign=False,
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
                encryption_algorithm=serialization.NoEncryption()
            )
        )
    
    print(f"✅ Certificate generated successfully!")
    print(f"   📄 Certificate: {cert_path}")
    print(f"   🔑 Private Key: {key_path}")
    print(f"   📅 Valid until: {cert.not_valid_after}")
    print(f"   🌐 Hostnames: {hostname}, {hostname}.local, localhost")
    print()
    print("⚠️  This is a SELF-SIGNED certificate. Browsers will show a warning.")
    print("   Users will need to accept the certificate to proceed.")
    
    return cert_path, key_path


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate self-signed SSL certificate")
    parser.add_argument(
        "--hostname",
        help="Server hostname (default: system hostname)",
        default=None
    )
    parser.add_argument(
        "--days",
        type=int,
        help="Certificate validity in days (default: 365)",
        default=365
    )
    parser.add_argument(
        "--cert-path",
        help="Path to save certificate (default: ./certs/server_cert.pem)",
        default="./certs/server_cert.pem"
    )
    parser.add_argument(
        "--key-path",
        help="Path to save private key (default: ./certs/server_key.pem)",
        default="./certs/server_key.pem"
    )
    
    args = parser.parse_args()
    
    generate_self_signed_cert(
        cert_path=args.cert_path,
        key_path=args.key_path,
        hostname=args.hostname,
        validity_days=args.days
    )
