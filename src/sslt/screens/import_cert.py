from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static

from sslt.services.cert_manager import CertificateManager


class ImportCertificateScreen(Screen[None]):
    """Screen for importing existing certificate and optional key files."""

    BINDINGS = [("q", "app.pop_screen", "Back"), ("f3", "import_certificate", "Import")]

    def __init__(self, manager: CertificateManager) -> None:
        """Store certificate service dependency for import actions."""
        super().__init__()
        self.manager = manager

    def compose(self) -> ComposeResult:
        """Render file path inputs and import trigger."""
        yield Container(
            Vertical(
                Label("Import Certificate"),
                Input(placeholder="Certificate file path (.pem/.crt/.cer/.der)", id="cert-path"),
                Input(placeholder="Private key path (optional)", id="key-path"),
                Input(placeholder="Display label (optional)", id="label"),
                Button("Import (F3)", id="import-btn", variant="primary"),
                Static("", id="status"),
            ),
            id="screen-center",
        )

    @on(Button.Pressed, "#import-btn")
    def _import_button(self) -> None:
        """Handle import button press."""
        self.action_import_certificate()

    def action_import_certificate(self) -> None:
        """Import certificate artifacts into managed local storage."""
        cert_path = Path(self.query_one("#cert-path", Input).value.strip())
        key_raw = self.query_one("#key-path", Input).value.strip()
        key_path = Path(key_raw) if key_raw else None
        label = self.query_one("#label", Input).value.strip() or None
        status = self.query_one("#status", Static)
        try:
            record = self.manager.import_certificate(cert_path, key_path, label=label)
            status.update(f"Imported certificate {record.cert_id}")
            self.notify(f"Imported {record.common_name}", timeout=2)
        except Exception as exc:  # noqa: BLE001
            status.update(f"Error: {exc}")
