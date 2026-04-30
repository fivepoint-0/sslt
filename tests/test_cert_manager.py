from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from sslt.models import CertificateRecord
from sslt.services.cert_manager import CertificateManager
from sslt.services.store import CertificateStore


def _write_cert_and_key(tmp_path: Path) -> tuple[Path, Path]:
    """Generate a temporary self-signed cert/key pair for tests."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "example.com")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(tz=UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(tz=UTC) + timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("example.com")]), critical=False)
        .sign(key, hashes.SHA256())
    )

    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


def test_rejects_invalid_key_size(tmp_path: Path) -> None:
    """Certificate creation should reject unsupported key sizes."""
    manager = CertificateManager(CertificateStore(root=tmp_path / "store"))
    with pytest.raises(ValueError):
        manager.create_self_signed_certificate("example.com", key_size=1024, validity_days=365)


def test_parse_and_export_formats(tmp_path: Path) -> None:
    """Parsed certs should export successfully as pem/der/p12."""
    cert_path, key_path = _write_cert_and_key(tmp_path)
    manager = CertificateManager(CertificateStore(root=tmp_path / "store"))
    record = manager.parse_certificate(cert_path, cert_id="x1", key_path=key_path, key_size=2048)
    assert record.common_name == "example.com"
    assert record.san == ["example.com"]

    pem_out = manager.export_certificate(record, "pem", tmp_path / "out.pem")
    der_out = manager.export_certificate(record, "der", tmp_path / "out.der")
    p12_out = manager.export_certificate(record, "p12", tmp_path / "out.p12", password="secret123")

    assert pem_out.exists()
    assert der_out.exists()
    assert p12_out.exists()


def test_export_rejects_unsupported_format(tmp_path: Path) -> None:
    """Export should fail for unknown format names."""
    cert_path, key_path = _write_cert_and_key(tmp_path)
    manager = CertificateManager(CertificateStore(root=tmp_path / "store"))
    record = manager.parse_certificate(cert_path, cert_id="x2", key_path=key_path, key_size=2048)
    with pytest.raises(ValueError):
        manager.export_certificate(record, "txt", tmp_path / "bad.txt")


def test_import_certificate(tmp_path: Path) -> None:
    """Import should add certificate metadata to the store."""
    cert_path, key_path = _write_cert_and_key(tmp_path)
    manager = CertificateManager(CertificateStore(root=tmp_path / "store"))
    record = manager.import_certificate(cert_path, key_path, label="imported-cert")
    assert record.common_name == "imported-cert"
    assert manager.store.get_record(record.cert_id) is not None


def test_create_certificate_uses_local_ca_when_auto_and_available(tmp_path: Path) -> None:
    """Auto signing mode should use local-CA signing when CA exists."""
    manager = CertificateManager(CertificateStore(root=tmp_path / "store"))
    ca_dir = manager.store.root / "local_ca"
    ca_dir.mkdir(parents=True, exist_ok=True)
    (ca_dir / "ca.crt.pem").write_text("dummy", encoding="utf-8")
    (ca_dir / "ca.key.pem").write_text("dummy", encoding="utf-8")

    calls: list[list[str]] = []

    def fake_run(command: list[str]) -> None:
        """Capture OpenSSL command calls for behavior assertions."""
        calls.append(command)

    manager._run = fake_run  # type: ignore[method-assign]
    manager.parse_certificate = (  # type: ignore[method-assign]
        lambda cert_path, cert_id, key_path, key_size: _fake_record(cert_id)
    )

    manager.create_self_signed_certificate("example.com", 2048, 365, signing_mode="auto")
    assert any(cmd[:3] == ["openssl", "x509", "-req"] for cmd in calls)


def test_create_certificate_local_ca_mode_requires_existing_ca(tmp_path: Path) -> None:
    """Explicit local_ca mode should error when CA artifacts are absent."""
    manager = CertificateManager(CertificateStore(root=tmp_path / "store"))
    with pytest.raises(ValueError):
        manager.create_self_signed_certificate("example.com", 2048, 365, signing_mode="local_ca")


def test_create_local_ca_rejects_second_ca(tmp_path: Path) -> None:
    """Only one local CA should be allowed at a time."""
    manager = CertificateManager(CertificateStore(root=tmp_path / "store"))
    ca_dir = manager.store.root / "local_ca"
    ca_dir.mkdir(parents=True, exist_ok=True)
    (ca_dir / "ca.crt.pem").write_text("dummy", encoding="utf-8")
    (ca_dir / "ca.key.pem").write_text("dummy", encoding="utf-8")
    with pytest.raises(ValueError):
        manager.create_local_ca("another-ca")


def test_delete_local_ca(tmp_path: Path) -> None:
    """Deleting local CA should remove files and reset presence state."""
    manager = CertificateManager(CertificateStore(root=tmp_path / "store"))
    ca_dir = manager.store.root / "local_ca"
    ca_dir.mkdir(parents=True, exist_ok=True)
    (ca_dir / "ca.crt.pem").write_text("dummy", encoding="utf-8")
    (ca_dir / "ca.key.pem").write_text("dummy", encoding="utf-8")
    assert manager.delete_local_ca() is True
    assert manager.has_local_ca() is False


def test_detect_trust_backend_returns_value(tmp_path: Path) -> None:
    """Backend detection should return one supported identifier string."""
    manager = CertificateManager(CertificateStore(root=tmp_path / "store"))
    assert manager.detect_trust_backend() in {
        "certutil",
        "security",
        "update-ca-certificates",
        "update-ca-trust",
        "trust-anchor",
        "unsupported",
    }


def _fake_record(cert_id: str) -> CertificateRecord:
    """Return a lightweight fake record for mocked parse paths."""
    return CertificateRecord(
        cert_id=cert_id,
        common_name="example.com",
        cert_path="/tmp/cert.pem",
        key_path="/tmp/key.pem",
        created_at="2026-01-01T00:00:00+00:00",
        not_before="2026-01-01T00:00:00+00:00",
        not_after="2027-01-01T00:00:00+00:00",
        key_size=2048,
        serial_number="0x1234",
        subject="CN=example.com",
        issuer="CN=example.com",
        signature_algorithm="sha256",
        san=["example.com"],
        sha1_fingerprint="aa",
        sha256_fingerprint="bb",
    )
