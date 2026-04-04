"""
Unit tests for client certificate generation (generate_certs.py).
"""

from datetime import UTC

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
        cert_pem, key_pem, serial = generate_client_cert(ca_cert, ca_key, "user@example.com")

        assert isinstance(cert_pem, bytes)
        assert isinstance(key_pem, bytes)
        assert isinstance(serial, int)
        assert cert_pem.startswith(b"-----BEGIN CERTIFICATE-----")
        assert key_pem.startswith(b"-----BEGIN RSA PRIVATE KEY-----")

    def test_subject_fields(self, tmp_path):
        from utils.generate_certs import generate_client_cert

        ca_cert, ca_key = self._create_ca(tmp_path)
        cert_pem, _, _ = generate_client_cert(ca_cert, ca_key, "alice@example.com")

        cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
        subject = cert.subject

        assert subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value == "alice@example.com"
        assert subject.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)[0].value == "thumbsup"
        assert subject.get_attributes_for_oid(NameOID.ORGANIZATIONAL_UNIT_NAME)[0].value == "member"

    def test_san_contains_email(self, tmp_path):
        from utils.generate_certs import generate_client_cert

        ca_cert, ca_key = self._create_ca(tmp_path)
        cert_pem, _, _ = generate_client_cert(ca_cert, ca_key, "bob@test.org")

        cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        emails = san.value.get_values_for_type(x509.RFC822Name)
        assert "bob@test.org" in emails

    def test_not_a_ca(self, tmp_path):
        from utils.generate_certs import generate_client_cert

        ca_cert, ca_key = self._create_ca(tmp_path)
        cert_pem, _, _ = generate_client_cert(ca_cert, ca_key, "user@example.com")

        cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
        bc = cert.extensions.get_extension_for_class(x509.BasicConstraints)
        assert bc.value.ca is False

    def test_has_client_auth_eku(self, tmp_path):
        from utils.generate_certs import generate_client_cert

        ca_cert, ca_key = self._create_ca(tmp_path)
        cert_pem, _, _ = generate_client_cert(ca_cert, ca_key, "user@example.com")

        cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
        eku = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage)
        assert ExtendedKeyUsageOID.CLIENT_AUTH in eku.value

    def test_issuer_matches_ca_subject(self, tmp_path):
        from utils.generate_certs import generate_client_cert

        ca_cert_path, ca_key_path = self._create_ca(tmp_path)
        cert_pem, _, _ = generate_client_cert(ca_cert_path, ca_key_path, "user@example.com")

        with open(ca_cert_path, "rb") as f:
            ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())

        client_cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
        assert client_cert.issuer == ca_cert.subject

    def test_signature_valid(self, tmp_path):
        """Client cert must be verifiable with the CA public key."""
        from cryptography.hazmat.primitives.asymmetric import padding

        from utils.generate_certs import generate_client_cert

        ca_cert_path, ca_key_path = self._create_ca(tmp_path)
        cert_pem, _, _ = generate_client_cert(ca_cert_path, ca_key_path, "user@example.com")

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
        cert_pem, _, _ = generate_client_cert(ca_cert, ca_key, "user@example.com", validity_days=30)

        cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
        delta = cert.not_valid_after - cert.not_valid_before
        assert 29 <= delta.days <= 30


class TestGenerateCRL:
    """Tests for CRL generation."""

    def _create_ca(self, tmp_path):
        from utils.generate_certs import generate_self_signed_cert

        cert_path = str(tmp_path / "ca_cert.pem")
        key_path = str(tmp_path / "ca_key.pem")
        generate_self_signed_cert(cert_path=cert_path, key_path=key_path, hostname="testhost")
        return cert_path, key_path

    def test_empty_crl(self, tmp_path):
        from utils.generate_certs import generate_crl

        ca_cert, ca_key = self._create_ca(tmp_path)
        crl_pem = generate_crl(ca_cert, ca_key, [])

        assert isinstance(crl_pem, bytes)
        assert b"-----BEGIN X509 CRL-----" in crl_pem

        crl = x509.load_pem_x509_crl(crl_pem, default_backend())
        assert len(list(crl)) == 0

    def test_crl_with_revoked_serials(self, tmp_path):
        from datetime import datetime

        from utils.generate_certs import generate_crl

        ca_cert, ca_key = self._create_ca(tmp_path)
        entries = [
            {"serial_number": 12345, "revoked_at": datetime(2026, 1, 1, tzinfo=UTC)},
            {"serial_number": 67890, "revoked_at": datetime(2026, 2, 1, tzinfo=UTC)},
        ]
        crl_pem = generate_crl(ca_cert, ca_key, entries)
        crl = x509.load_pem_x509_crl(crl_pem, default_backend())

        revoked = list(crl)
        assert len(revoked) == 2
        serials = {r.serial_number for r in revoked}
        assert serials == {12345, 67890}

    def test_update_crl_file(self, tmp_path):
        import os

        from utils.generate_certs import generate_crl, update_crl_file

        ca_cert, ca_key = self._create_ca(tmp_path)
        crl_pem = generate_crl(ca_cert, ca_key, [])

        crl_path = str(tmp_path / "crl.pem")
        update_crl_file(crl_pem, crl_path)

        assert os.path.exists(crl_path)
        with open(crl_path, "rb") as f:
            assert f.read() == crl_pem

    def test_generate_empty_crl_creates_file(self, tmp_path):
        import os

        from utils.generate_certs import generate_empty_crl

        ca_cert, ca_key = self._create_ca(tmp_path)
        crl_path = str(tmp_path / "crl.pem")
        generate_empty_crl(ca_cert, ca_key, crl_path)

        assert os.path.exists(crl_path)
        crl = x509.load_pem_x509_crl(open(crl_path, "rb").read(), default_backend())
        assert len(list(crl)) == 0

    def test_generate_empty_crl_noop_if_valid(self, tmp_path):
        import os

        from utils.generate_certs import generate_crl, generate_empty_crl, update_crl_file

        ca_cert, ca_key = self._create_ca(tmp_path)
        crl_path = str(tmp_path / "crl.pem")

        # Create a valid CRL signed by this CA
        crl_bytes = generate_crl(ca_cert, ca_key, [])
        update_crl_file(crl_bytes, crl_path)

        # Record mtime
        mtime_before = os.path.getmtime(crl_path)

        generate_empty_crl(ca_cert, ca_key, crl_path)

        # Should NOT overwrite — CRL already matches the CA
        assert os.path.getmtime(crl_path) == mtime_before

    def test_generate_empty_crl_replaces_stale_crl(self, tmp_path):

        from utils.generate_certs import generate_crl, generate_empty_crl, update_crl_file

        # Create two separate CAs
        ca_cert_old, ca_key_old = self._create_ca(tmp_path / "old")
        ca_cert_new, ca_key_new = self._create_ca(tmp_path / "new")

        crl_path = str(tmp_path / "crl.pem")

        # Write a CRL signed by the OLD CA
        crl_bytes = generate_crl(ca_cert_old, ca_key_old, [])
        update_crl_file(crl_bytes, crl_path)

        # Now generate_empty_crl with the NEW CA should replace it
        generate_empty_crl(ca_cert_new, ca_key_new, crl_path)

        # CRL should now be valid against the new CA
        with open(crl_path, "rb") as f:
            crl = x509.load_pem_x509_crl(f.read(), default_backend())
        with open(ca_cert_new, "rb") as f:
            new_cert = x509.load_pem_x509_certificate(f.read(), default_backend())
        assert crl.is_signature_valid(new_cert.public_key())
