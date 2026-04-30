from __future__ import annotations

from pathlib import Path

from sslt.models import CertificateRecord
from sslt.services.store import CertificateStore


def _record() -> CertificateRecord:
    """Return a representative certificate record for store tests."""
    return CertificateRecord(
        cert_id="abc123",
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


def test_store_add_and_list(tmp_path: Path) -> None:
    """Store should persist records and return them via list_records."""
    store = CertificateStore(root=tmp_path / "store")
    store.add_record(_record())
    records = store.list_records()
    assert len(records) == 1
    assert records[0].common_name == "example.com"


def test_store_get_record(tmp_path: Path) -> None:
    """Store should retrieve a record by certificate ID."""
    store = CertificateStore(root=tmp_path / "store")
    store.add_record(_record())
    found = store.get_record("abc123")
    assert found is not None
    assert found.cert_id == "abc123"


def test_store_defaults_roundtrip(tmp_path: Path) -> None:
    """Store should preserve create-form defaults through save/load."""
    store = CertificateStore(root=tmp_path / "store")
    defaults = {"O": "TPX", "L": "Miami", "C": "US", "key_size": "4096"}
    store.save_defaults(defaults)
    assert store.get_defaults() == defaults


def test_store_remove_record(tmp_path: Path) -> None:
    """Store should remove an existing record and report success."""
    store = CertificateStore(root=tmp_path / "store")
    store.add_record(_record())
    removed = store.remove_record("abc123")
    assert removed is True
    assert store.get_record("abc123") is None
