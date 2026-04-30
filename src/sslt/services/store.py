from __future__ import annotations

import json
import shutil
from pathlib import Path

from sslt.models import CertificateRecord


class CertificateStore:
    """File-backed storage for certificate records and creation defaults."""

    def __init__(self, root: Path | None = None) -> None:
        """Initialize on-disk storage paths.

        Args:
            root: Optional storage directory override. Defaults to
                `<cwd>/cert_store`.
        """
        self.root = root or Path.cwd() / "cert_store"
        self.index_path = self.root / "index.json"
        self.defaults_path = self.root / "defaults.json"
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self.index_path.write_text("[]", encoding="utf-8")
        if not self.defaults_path.exists():
            self.defaults_path.write_text("{}", encoding="utf-8")

    def list_records(self) -> list[CertificateRecord]:
        """Return all stored certificate records.

        Returns:
            A list of persisted certificate records.
        """
        raw = json.loads(self.index_path.read_text(encoding="utf-8"))
        return [CertificateRecord.from_dict(item) for item in raw]

    def get_record(self, cert_id: str) -> CertificateRecord | None:
        """Find a certificate record by ID, if present.

        Args:
            cert_id: Certificate identifier to search for.

        Returns:
            The matching record if found, otherwise `None`.
        """
        for record in self.list_records():
            if record.cert_id == cert_id:
                return record
        return None

    def add_record(self, record: CertificateRecord) -> None:
        """Append a certificate record to the persisted index.

        Args:
            record: Record to persist.
        """
        records = self.list_records()
        records.append(record)
        self._write_records(records)

    def remove_record(self, cert_id: str) -> bool:
        """Delete a record and local certificate directory by ID.

        Args:
            cert_id: Certificate identifier to remove.

        Returns:
            `True` if a record existed and was removed, otherwise `False`.
        """
        records = self.list_records()
        kept = [record for record in records if record.cert_id != cert_id]
        if len(kept) == len(records):
            return False
        self._write_records(kept)
        cert_dir = self.root / cert_id
        if cert_dir.exists():
            shutil.rmtree(cert_dir)
        return True

    def get_defaults(self) -> dict[str, str]:
        """Load persisted create-screen defaults.

        Returns:
            Dictionary of default field values.
        """
        return json.loads(self.defaults_path.read_text(encoding="utf-8"))

    def save_defaults(self, defaults: dict[str, str]) -> None:
        """Persist create-screen defaults used to prefill form fields.

        Args:
            defaults: Field-value map to save.
        """
        self.defaults_path.write_text(json.dumps(defaults, indent=2), encoding="utf-8")

    def _write_records(self, records: list[CertificateRecord]) -> None:
        """Write the full certificate index to disk.

        Args:
            records: Complete record list to persist.
        """
        raw = [record.to_dict() for record in records]
        self.index_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
