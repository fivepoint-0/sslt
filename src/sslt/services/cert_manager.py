from __future__ import annotations

import platform
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs12

from sslt.models import CertificateRecord
from sslt.services.store import CertificateStore

VALID_KEY_SIZES = {2048, 4096}


class CertificateManager:
    """Core certificate operations: create, parse, import, export, CSR, and CA tasks."""

    def __init__(self, store: CertificateStore | None = None) -> None:
        """Initialize manager with storage backend.

        Args:
            store: Optional store instance. If omitted, a default
                `CertificateStore` is created.
        """
        self.store = store or CertificateStore()

    def create_self_signed_certificate(
        self,
        common_name: str,
        key_size: int,
        validity_days: int,
        subject_fields: dict[str, str] | None = None,
        sans: list[str] | None = None,
        signing_mode: str = "auto",
    ) -> CertificateRecord:
        """Create a certificate using self-signed or local-CA signing mode.

        Args:
            common_name: Certificate common name.
            key_size: RSA key size, must be 2048 or 4096.
            validity_days: Number of validity days.
            subject_fields: Optional subject metadata fields.
            sans: Optional DNS SAN list.
            signing_mode: One of `auto`, `self_signed`, or `local_ca`.

        Returns:
            Parsed and persisted certificate record.
        """
        if key_size not in VALID_KEY_SIZES:
            raise ValueError("Key size must be 2048 or 4096")
        if not common_name.strip():
            raise ValueError("Common Name is required")
        if validity_days < 1:
            raise ValueError("Validity must be at least 1 day")

        cert_id = uuid4().hex[:12]
        cert_dir = self.store.root / cert_id
        cert_dir.mkdir(parents=True, exist_ok=True)
        key_path = cert_dir / "certificate.key.pem"
        cert_path = cert_dir / "certificate.pem"
        csr_path = cert_dir / "certificate.csr.pem"
        config_path = self._build_openssl_config(common_name, subject_fields or {}, sans or [])

        subject = self._build_subject(common_name, subject_fields or {})
        effective_mode = self._resolve_signing_mode(signing_mode)
        if effective_mode == "local_ca":
            self._create_local_ca_signed_certificate(
                key_size=key_size,
                validity_days=validity_days,
                subject=subject,
                key_path=key_path,
                csr_path=csr_path,
                cert_path=cert_path,
                config_path=config_path,
            )
        else:
            command = [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                f"rsa:{key_size}",
                "-sha256",
                "-days",
                str(validity_days),
                "-nodes",
                "-keyout",
                str(key_path),
                "-out",
                str(cert_path),
                "-subj",
                subject,
            ]
            if config_path is not None:
                command.extend(["-extensions", "v3_req", "-config", str(config_path)])
            self._run(command)

        record = self.parse_certificate(cert_path, cert_id=cert_id, key_path=key_path, key_size=key_size)
        self.store.add_record(record)
        return record

    def import_certificate(
        self,
        cert_file: Path,
        key_file: Path | None = None,
        label: str | None = None,
    ) -> CertificateRecord:
        """Import a certificate and optional key into managed storage.

        Args:
            cert_file: Certificate file path (PEM/DER).
            key_file: Optional private key path.
            label: Optional display label that overrides parsed common name.

        Returns:
            Parsed and persisted certificate record.
        """
        if not cert_file.exists():
            raise ValueError("Certificate file does not exist")
        cert_id = uuid4().hex[:12]
        cert_dir = self.store.root / cert_id
        cert_dir.mkdir(parents=True, exist_ok=True)
        target_cert = cert_dir / cert_file.name
        target_cert.write_bytes(cert_file.read_bytes())
        target_key: Path | None = None
        if key_file is not None:
            if not key_file.exists():
                raise ValueError("Key file does not exist")
            target_key = cert_dir / key_file.name
            target_key.write_bytes(key_file.read_bytes())
        record = self.parse_certificate(target_cert, cert_id=cert_id, key_path=target_key, key_size=0)
        if label:
            record.common_name = label
        self.store.add_record(record)
        return record

    def create_csr(
        self,
        common_name: str,
        key_size: int,
        subject_fields: dict[str, str] | None = None,
        sans: list[str] | None = None,
    ) -> tuple[Path, Path]:
        """Generate a CSR and private key for external certificate authorities.

        Args:
            common_name: CSR common name.
            key_size: RSA key size.
            subject_fields: Optional CSR subject fields.
            sans: Optional DNS SAN values.

        Returns:
            Tuple of `(csr_path, key_path)`.
        """
        if key_size not in VALID_KEY_SIZES:
            raise ValueError("Key size must be 2048 or 4096")
        if not common_name.strip():
            raise ValueError("Common Name is required")
        csr_id = uuid4().hex[:12]
        csr_dir = self.store.root / f"csr-{csr_id}"
        csr_dir.mkdir(parents=True, exist_ok=True)
        key_path = csr_dir / "request.key.pem"
        csr_path = csr_dir / "request.csr.pem"
        config_path = self._build_openssl_config(common_name, subject_fields or {}, sans or [])
        subject = self._build_subject(common_name, subject_fields or {})
        command = [
            "openssl",
            "req",
            "-new",
            "-newkey",
            f"rsa:{key_size}",
            "-nodes",
            "-keyout",
            str(key_path),
            "-out",
            str(csr_path),
            "-subj",
            subject,
        ]
        if config_path is not None:
            command.extend(["-reqexts", "v3_req", "-config", str(config_path)])
        self._run(command)
        return csr_path, key_path

    def create_local_ca(self, common_name: str, validity_days: int = 3650) -> Path:
        """Create a single local CA root certificate and private key.

        Args:
            common_name: Common name for the CA root certificate.
            validity_days: CA validity duration in days.

        Returns:
            Path to generated CA certificate file.
        """
        if not common_name.strip():
            raise ValueError("CA Common Name is required")
        if self.has_local_ca():
            raise ValueError("A local CA already exists. Delete it before creating a new one.")
        ca_dir = self.store.root / "local_ca"
        ca_dir.mkdir(parents=True, exist_ok=True)
        key_path = ca_dir / "ca.key.pem"
        cert_path = ca_dir / "ca.crt.pem"
        subject = self._build_subject(common_name, {"O": "SSLT Local CA"})
        command = [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:4096",
            "-sha256",
            "-days",
            str(validity_days),
            "-nodes",
            "-keyout",
            str(key_path),
            "-out",
            str(cert_path),
            "-subj",
            subject,
        ]
        self._run(command)
        return cert_path

    def has_local_ca(self) -> bool:
        """Return whether local CA certificate and key are both present."""
        ca_dir = self.store.root / "local_ca"
        return (ca_dir / "ca.crt.pem").exists() and (ca_dir / "ca.key.pem").exists()

    def delete_local_ca(self) -> bool:
        """Delete local CA files if they exist.

        Returns:
            `True` when CA files existed and were removed, otherwise `False`.
        """
        ca_dir = self.store.root / "local_ca"
        if not ca_dir.exists():
            return False
        shutil.rmtree(ca_dir)
        return True

    def install_local_ca_trust(self, sudo_password: str | None = None) -> str:
        """Install local CA into OS trust store using platform-specific commands.

        Args:
            sudo_password: Optional sudo password for Linux/macOS privileged operations.

        Returns:
            Human-readable status message describing the install backend used.
        """
        ca_cert = self.store.root / "local_ca" / "ca.crt.pem"
        if not ca_cert.exists():
            raise ValueError("No local CA certificate exists. Create it first.")
        backend = self.detect_trust_backend()
        system = platform.system().lower()
        if system == "windows":
            self._run(["certutil", "-addstore", "Root", str(ca_cert)])
            return "Installed local CA into Windows Root trust store."
        if system == "darwin":
            self._run_with_sudo(
                [
                    "security",
                    "add-trusted-cert",
                    "-d",
                    "-r",
                    "trustRoot",
                    "-k",
                    "/Library/Keychains/System.keychain",
                    str(ca_cert),
                ],
                sudo_password,
            )
            return "Installed local CA into macOS System keychain trust store."
        if system == "linux":
            if backend == "update-ca-certificates":
                dest = "/usr/local/share/ca-certificates/sslt-local-ca.crt"
                self._run_with_sudo(["cp", str(ca_cert), dest], sudo_password)
                self._run_with_sudo(["update-ca-certificates"], sudo_password)
                return "Installed local CA using update-ca-certificates."
            if backend == "update-ca-trust":
                dest = "/etc/pki/ca-trust/source/anchors/sslt-local-ca.crt"
                self._run_with_sudo(["cp", str(ca_cert), dest], sudo_password)
                self._run_with_sudo(["update-ca-trust", "extract"], sudo_password)
                return "Installed local CA using update-ca-trust."
            if backend == "trust-anchor":
                self._run_with_sudo(["trust", "anchor", str(ca_cert)], sudo_password)
                return "Installed local CA using p11-kit trust anchor."
            raise RuntimeError("No supported Linux trust-store command found on this system.")
        raise RuntimeError(f"Unsupported platform: {platform.system()}")

    def detect_trust_backend(self) -> str:
        """Detect available trust-store backend for current platform.

        Returns:
            Backend identifier string, or `unsupported`.
        """
        system = platform.system().lower()
        if system == "windows":
            return "certutil"
        if system == "darwin":
            return "security"
        if system == "linux":
            if shutil.which("update-ca-certificates"):
                return "update-ca-certificates"
            if shutil.which("update-ca-trust"):
                return "update-ca-trust"
            if shutil.which("trust"):
                return "trust-anchor"
            return "unsupported"
        return "unsupported"

    def parse_certificate(
        self,
        cert_path: Path,
        cert_id: str | None = None,
        key_path: Path | None = None,
        key_size: int | None = None,
    ) -> CertificateRecord:
        """Parse certificate bytes into a normalized CertificateRecord.

        Args:
            cert_path: Path to certificate file.
            cert_id: Optional externally provided certificate ID.
            key_path: Optional private key path associated with the certificate.
            key_size: Optional key size metadata override.

        Returns:
            Parsed certificate record instance.
        """
        cert_data = cert_path.read_bytes()
        cert = self._load_certificate(cert_data)
        san_values: list[str] = []
        try:
            ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
            san_values = [entry.value for entry in ext.value]
        except x509.ExtensionNotFound:
            san_values = []

        now = datetime.now(tz=UTC)
        return CertificateRecord(
            cert_id=cert_id or cert_path.stem,
            common_name=self._get_common_name(cert),
            cert_path=str(cert_path),
            key_path=str(key_path or ""),
            created_at=now.isoformat(),
            not_before=cert.not_valid_before_utc.isoformat(),
            not_after=cert.not_valid_after_utc.isoformat(),
            key_size=key_size or 0,
            serial_number=hex(cert.serial_number),
            subject=cert.subject.rfc4514_string(),
            issuer=cert.issuer.rfc4514_string(),
            signature_algorithm=cert.signature_hash_algorithm.name,
            san=san_values,
            sha1_fingerprint=cert.fingerprint(hashes.SHA1()).hex(":"),
            sha256_fingerprint=cert.fingerprint(hashes.SHA256()).hex(":"),
        )

    def export_certificate(
        self,
        record: CertificateRecord,
        export_format: str,
        destination: Path,
        password: str | None = None,
    ) -> Path:
        """Export certificate record into PEM/DER/P12 destination file.

        Args:
            record: Source certificate record.
            export_format: Export format (`pem`, `der`, or `p12`).
            destination: Output file path.
            password: Optional P12 password.

        Returns:
            Final destination path.
        """
        destination.parent.mkdir(parents=True, exist_ok=True)
        export_format = export_format.lower()
        cert_path = Path(record.cert_path)

        if export_format == "pem":
            destination.write_bytes(cert_path.read_bytes())
            return destination
        if export_format == "der":
            cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
            destination.write_bytes(cert.public_bytes(serialization.Encoding.DER))
            return destination
        if export_format == "p12":
            key_file = Path(record.key_path)
            cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
            private_key = serialization.load_pem_private_key(key_file.read_bytes(), password=None)
            enc = serialization.NoEncryption()
            if password:
                enc = serialization.BestAvailableEncryption(password.encode("utf-8"))
            blob = pkcs12.serialize_key_and_certificates(
                name=record.common_name.encode("utf-8"),
                key=private_key,
                cert=cert,
                cas=None,
                encryption_algorithm=enc,
            )
            destination.write_bytes(blob)
            return destination
        raise ValueError(f"Unsupported export format: {export_format}")

    @staticmethod
    def _run(command: list[str]) -> None:
        """Execute subprocess command and raise user-friendly errors."""
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except FileNotFoundError as exc:
            raise RuntimeError("OpenSSL is not installed or not in PATH") from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() or "OpenSSL command failed"
            raise RuntimeError(stderr) from exc

    @staticmethod
    def _run_with_sudo(command: list[str], sudo_password: str | None = None) -> None:
        """Execute command with sudo, optionally supplying password via stdin."""
        try:
            if sudo_password:
                subprocess.run(
                    ["sudo", "-S", "-p", ""] + command,
                    input=f"{sudo_password}\n",
                    check=True,
                    capture_output=True,
                    text=True,
                )
            else:
                subprocess.run(
                    ["sudo", "-n"] + command,
                    check=True,
                    capture_output=True,
                    text=True,
                )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip()
            if "a password is required" in stderr.lower() or "sudo:" in stderr.lower():
                raise RuntimeError(
                    "Sudo authentication required. Enter sudo password in the field and retry."
                ) from exc
            raise RuntimeError(stderr or "Command failed") from exc
        except FileNotFoundError as exc:
            raise RuntimeError("Required system command not found") from exc

    @staticmethod
    def _run_shell(command: str) -> None:
        """Execute shell command helper used by legacy paths/tests."""
        try:
            subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() or "Command failed"
            raise RuntimeError(stderr) from exc

    @staticmethod
    def _load_certificate(cert_data: bytes) -> x509.Certificate:
        """Load certificate as PEM first, then fallback to DER."""
        try:
            return x509.load_pem_x509_certificate(cert_data)
        except ValueError:
            return x509.load_der_x509_certificate(cert_data)

    def _resolve_signing_mode(self, signing_mode: str) -> str:
        """Resolve requested signing mode into an executable mode."""
        mode = signing_mode.strip().lower()
        if mode not in {"auto", "self_signed", "local_ca"}:
            raise ValueError("Signing mode must be auto, self_signed, or local_ca")
        if mode == "auto":
            return "local_ca" if self.has_local_ca() else "self_signed"
        if mode == "local_ca" and not self.has_local_ca():
            raise ValueError("Local CA not found. Create one first or use self-signed mode.")
        return mode

    def _create_local_ca_signed_certificate(
        self,
        key_size: int,
        validity_days: int,
        subject: str,
        key_path: Path,
        csr_path: Path,
        cert_path: Path,
        config_path: Path | None,
    ) -> None:
        """Generate key/CSR and sign certificate with local CA."""
        ca_dir = self.store.root / "local_ca"
        ca_cert = ca_dir / "ca.crt.pem"
        ca_key = ca_dir / "ca.key.pem"
        serial_path = ca_dir / "ca.srl"
        csr_cmd = [
            "openssl",
            "req",
            "-new",
            "-newkey",
            f"rsa:{key_size}",
            "-nodes",
            "-keyout",
            str(key_path),
            "-out",
            str(csr_path),
            "-subj",
            subject,
        ]
        if config_path is not None:
            csr_cmd.extend(["-reqexts", "v3_req", "-config", str(config_path)])
        self._run(csr_cmd)

        sign_cmd = [
            "openssl",
            "x509",
            "-req",
            "-in",
            str(csr_path),
            "-CA",
            str(ca_cert),
            "-CAkey",
            str(ca_key),
            "-CAcreateserial",
            "-CAserial",
            str(serial_path),
            "-out",
            str(cert_path),
            "-days",
            str(validity_days),
            "-sha256",
        ]
        if config_path is not None:
            sign_cmd.extend(["-extensions", "v3_req", "-extfile", str(config_path)])
        self._run(sign_cmd)

    @staticmethod
    def _build_subject(common_name: str, fields: dict[str, str]) -> str:
        """Build OpenSSL subject string from common name and optional fields."""
        parts = [
            f"/C={fields.get('C', '')}",
            f"/ST={fields.get('ST', '')}",
            f"/L={fields.get('L', '')}",
            f"/O={fields.get('O', '')}",
            f"/OU={fields.get('OU', '')}",
            f"/CN={common_name}",
        ]
        return "".join(parts)

    @staticmethod
    def _get_common_name(cert: x509.Certificate) -> str:
        """Extract certificate common name, if present."""
        attributes = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
        if not attributes:
            return ""
        return attributes[0].value

    @staticmethod
    def _build_openssl_config(common_name: str, fields: dict[str, str], sans: list[str]) -> Path | None:
        """Create temporary OpenSSL config file when SAN entries are provided."""
        if not sans:
            return None
        lines = [
            "[req]",
            "distinguished_name = req_distinguished_name",
            "req_extensions = v3_req",
            "prompt = no",
            "",
            "[req_distinguished_name]",
            f"C = {fields.get('C', '')}",
            f"ST = {fields.get('ST', '')}",
            f"L = {fields.get('L', '')}",
            f"O = {fields.get('O', '')}",
            f"OU = {fields.get('OU', '')}",
            f"CN = {common_name}",
            "",
            "[v3_req]",
            "subjectAltName = @alt_names",
            "",
            "[alt_names]",
        ]
        for idx, san in enumerate(sans, start=1):
            lines.append(f"DNS.{idx} = {san.strip()}")
        tmp = tempfile.NamedTemporaryFile(prefix="sslt-openssl-", suffix=".cnf", delete=False)
        tmp.write("\n".join(lines).encode("utf-8"))
        tmp.flush()
        tmp.close()
        return Path(tmp.name)
