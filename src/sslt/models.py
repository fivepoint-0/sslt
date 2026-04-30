from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class CertificateRecord:
    """Persisted certificate metadata used by the UI and services."""

    cert_id: str
    common_name: str
    cert_path: str
    key_path: str
    created_at: str
    not_before: str
    not_after: str
    key_size: int
    serial_number: str
    subject: str
    issuer: str
    signature_algorithm: str
    san: list[str]
    sha1_fingerprint: str
    sha256_fingerprint: str

    def to_dict(self) -> dict:
        """Serialize a record for JSON persistence."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CertificateRecord":
        """Create a record from a JSON-compatible dictionary."""
        return cls(**data)
