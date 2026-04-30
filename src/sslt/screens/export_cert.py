from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Select, Static

from sslt.models import CertificateRecord
from sslt.services.cert_manager import CertificateManager


class ExportCertificateScreen(Screen[None]):
    """Screen for exporting a selected certificate in multiple formats."""

    BINDINGS = [("q", "app.pop_screen", "Back"), ("ctrl+s", "export_certificate", "Export")]

    def __init__(self, manager: CertificateManager, record: CertificateRecord) -> None:
        """Store dependencies required to perform exports."""
        super().__init__()
        self.manager = manager
        self.record = record

    def compose(self) -> ComposeResult:
        """Render export destination, format, and password controls."""
        yield Container(
            Vertical(
                Label(f"Export certificate: {self.record.common_name} ({self.record.cert_id})"),
                Select([("PEM", "pem"), ("DER", "der"), ("PKCS#12 (.p12)", "p12")], value="pem", id="format"),
                Input(value=str(Path.cwd() / "exports"), id="dest-dir", placeholder="Destination directory"),
                Input(placeholder="Output filename (optional)", id="filename"),
                Input(password=True, placeholder="PKCS#12 password (optional)", id="password"),
                Button("Export", id="export-btn", variant="primary"),
                Static("", id="status"),
            ),
            id="screen-center",
        )

    @on(Button.Pressed, "#export-btn")
    def via_button(self) -> None:
        """Handle export button press."""
        self.action_export_certificate()

    def action_export_certificate(self) -> None:
        """Execute certificate export with current form selections."""
        export_format = str(self.query_one("#format", Select).value)
        destination_dir = Path(self.query_one("#dest-dir", Input).value.strip())
        filename = self.query_one("#filename", Input).value.strip()
        password = self.query_one("#password", Input).value.strip() or None
        ext = "p12" if export_format == "p12" else export_format
        if not filename:
            filename = f"{self.record.common_name}-{self.record.cert_id}.{ext}".replace(" ", "_")
        destination = destination_dir / filename
        status = self.query_one("#status", Static)

        try:
            exported = self.manager.export_certificate(self.record, export_format, destination, password=password)
            status.update(f"Exported to {exported}")
        except Exception as exc:  # noqa: BLE001
            status.update(f"Error: {exc}")
