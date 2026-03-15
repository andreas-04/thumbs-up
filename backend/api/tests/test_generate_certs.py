"""
Unit tests for client certificate generation (generate_certs.py).
"""

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


class TestGenerateClientCert:
    """Tests for generate_client_cert function."""

    def _create_ca(self, tmp_path):
        """Helper: generate a CA cert/key pair and return their paths."""
        from utils.generate_certs import generate_self_signed_cert

        cert_path = str(tmp_path / "ca_cert.pem")
        key_path = str(tmp_path / "ca_key.pem")
        generate_self_signed_cert(cert_path=cert_path, key_path=key_path, hostname="testhost")
        return cert_path, key_path

    def test_returns_pem_bytes(self, tmp_path):
        from utils.generate_certs import generate_client_cert

        ca_cert, ca_key = self._create_ca(tmp_path)
        cert_pem, key_pem = generate_client_cert(ca_cert, ca_key, "user@example.com")

        assert isinstance(cert_pem, bytes)
        assert isinstance(key_pem, bytes)
        assert cert_pem.startswith(b"-----BEGIN CERTIFICATE-----")
        assert key_pem.startswith(b"-----BEGIN RSA PRIVATE KEY-----")

    def test_subject_fields(self, tmp_path):
        from utils.generate_certs import generate_client_cert

        ca_cert, ca_key = self._create_ca(tmp_path)
        cert_pem, _ = generate_client_cert(ca_cert, ca_key, "alice@example.com")

        cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
        subject = cert.subject

        assert subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value == "alice@example.com"
        assert subject.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)[0].value == "thumbsup"
        assert subject.get_attributes_for_oid(NameOID.ORGANIZATIONAL_UNIT_NAME)[0].value == "member"

    def test_san_contains_email(self, tmp_path):
        from utils.generate_certs import generate_client_cert

        ca_cert, ca_key = self._create_ca(tmp_path)
        cert_pem, _ = generate_client_cert(ca_cert, ca_key, "bob@test.org")

        cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        emails = san.value.get_values_for_type(x509.RFC822Name)
        assert "bob@test.org" in emails

    def test_not_a_ca(self, tmp_path):
        from utils.generate_certs import generate_client_cert

        ca_cert, ca_key = self._create_ca(tmp_path)
        cert_pem, _ = generate_client_cert(ca_cert, ca_key, "user@example.com")

        cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
        bc = cert.extensions.get_extension_for_class(x509.BasicConstraints)
        assert bc.value.ca is False

    def test_has_client_auth_eku(self, tmp_path):
        from utils.generate_certs import generate_client_cert

        ca_cert, ca_key = self._create_ca(tmp_path)
        cert_pem, _ = generate_client_cert(ca_cert, ca_key, "user@example.com")

        cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
        eku = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage)
        assert ExtendedKeyUsageOID.CLIENT_AUTH in eku.value

    def test_issuer_matches_ca_subject(self, tmp_path):
        from utils.generate_certs import generate_client_cert

        ca_cert_path, ca_key_path = self._create_ca(tmp_path)
        cert_pem, _ = generate_client_cert(ca_cert_path, ca_key_path, "user@example.com")

        with open(ca_cert_path, "rb") as f:
            ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())

        client_cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
        assert client_cert.issuer == ca_cert.subject

    def test_signature_valid(self, tmp_path):
        """Client cert must be verifiable with the CA public key."""
        from cryptography.hazmat.primitives.asymmetric import padding

        from utils.generate_certs import generate_client_cert

        ca_cert_path, ca_key_path = self._create_ca(tmp_path)
        cert_pem, _ = generate_client_cert(ca_cert_path, ca_key_path, "user@example.com")

        with open(ca_cert_path, "rb") as f:
            ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())

        client_cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
        # This will raise InvalidSignature if verification fails
        ca_cert.public_key().verify(
            client_cert.signature,
            client_cert.tbs_certificate_bytes,
            padding.PKCS1v15(),
            client_cert.signature_hash_algorithm,
        )

    def test_custom_validity(self, tmp_path):
        from utils.generate_certs import generate_client_cert

        ca_cert, ca_key = self._create_ca(tmp_path)
        cert_pem, _ = generate_client_cert(ca_cert, ca_key, "user@example.com", validity_days=30)

        cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
        delta = cert.not_valid_after - cert.not_valid_before
        assert 29 <= delta.days <= 30
