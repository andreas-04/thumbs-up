# pki/gen_selfsigned.py
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from datetime import datetime, timedelta
import argparse
from pathlib import Path

def make_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)

def make_selfsigned_cert(common_name: str, key, is_server: bool, validity_days: int = 365):
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.utcnow()
    # add SAN = CN (helps some clients)
    san = x509.SubjectAlternativeName([x509.DNSName(common_name)])
    eku = x509.ExtendedKeyUsage(
        [ExtendedKeyUsageOID.SERVER_AUTH] if is_server else [ExtendedKeyUsageOID.CLIENT_AUTH]
    )

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=validity_days))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(san, critical=False)
        .add_extension(eku, critical=False)
        .sign(private_key=key, algorithm=hashes.SHA256())
    )
    return cert

def write_pem_pair(prefix: str, key, cert):
    Path(prefix).parent.mkdir(parents=True, exist_ok=True)
    open(f"{prefix}_key.pem", "wb").write(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    open(f"{prefix}_cert.pem", "wb").write(cert.public_bytes(serialization.Encoding.PEM))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate self-signed TLS certificates for ThumbsUp mTLS authentication"
    )
    parser.add_argument(
        "--server-cn",
        default="localhost",
        help="Common Name for server certificate (default: localhost)"
    )
    parser.add_argument(
        "--client-cn",
        default="python-client",
        help="Common Name for client certificate (default: python-client)"
    )
    parser.add_argument(
        "--validity-days",
        type=int,
        default=365,
        help="Certificate validity period in days (default: 365)"
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Output directory for certificate files (default: current directory)"
    )
    
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Server
    print(f"Generating server certificate (CN={args.server_cn}, valid for {args.validity_days} days)...")
    skey = make_key()
    scert = make_selfsigned_cert(args.server_cn, skey, is_server=True, validity_days=args.validity_days)
    server_prefix = str(output_path / "server")
    write_pem_pair(server_prefix, skey, scert)

    # Client
    print(f"Generating client certificate (CN={args.client_cn}, valid for {args.validity_days} days)...")
    ckey = make_key()
    ccert = make_selfsigned_cert(args.client_cn, ckey, is_server=False, validity_days=args.validity_days)
    client_prefix = str(output_path / "client")
    write_pem_pair(client_prefix, ckey, ccert)

    print(f"\n[SUCCESS] Certificates generated successfully in '{args.output_dir}':")
    print(f"   - server_key.pem, server_cert.pem")
    print(f"   - client_key.pem, client_cert.pem")
