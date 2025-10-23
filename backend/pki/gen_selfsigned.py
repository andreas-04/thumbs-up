# pki/gen_selfsigned.py
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from datetime import datetime, timedelta

def make_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)

def make_selfsigned_cert(common_name: str, key, is_server: bool):
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
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(san, critical=False)
        .add_extension(eku, critical=False)
        .sign(private_key=key, algorithm=hashes.SHA256())
    )
    return cert

def write_pem_pair(prefix: str, key, cert):
    open(f"{prefix}_key.pem", "wb").write(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    open(f"{prefix}_cert.pem", "wb").write(cert.public_bytes(serialization.Encoding.PEM))

if __name__ == "__main__":
    # Server
    skey = make_key()
    scert = make_selfsigned_cert("localhost", skey, is_server=True)
    write_pem_pair("server", skey, scert)

    # Client
    ckey = make_key()
    ccert = make_selfsigned_cert("python-client", ckey, is_server=False)
    write_pem_pair("client", ckey, ccert)

    print("Wrote: server_key.pem, server_cert.pem, client_key.pem, client_cert.pem")
