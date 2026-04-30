from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Select, Static

from sslt.services.cert_manager import CertificateManager


class CsrScreen(Screen[None]):
    """Screen for creating CSRs and private keys for external signing."""

    BINDINGS = [("q", "app.pop_screen", "Back"), ("f4", "create_csr", "Generate CSR")]

    def __init__(self, manager: CertificateManager) -> None:
        """Store certificate service dependency for CSR actions."""
        super().__init__()
        self.manager = manager

    def compose(self) -> ComposeResult:
        """Render CSR input fields and generate button."""
        yield Container(
            Vertical(
                Label("Generate CSR"),
                Input(placeholder="Common Name (required)", id="cn"),
                Select([(str(2048), 2048), (str(4096), 4096)], value=2048, id="key-size"),
                Input(placeholder="Organization (O)", id="org"),
                Input(placeholder="Org Unit (OU)", id="ou"),
                Input(placeholder="Locality (L)", id="loc"),
                Input(placeholder="State (ST)", id="state"),
                Input(placeholder="Country (C)", id="country"),
                Input(placeholder="SANs comma-separated (optional)", id="sans"),
                Button("Generate CSR (F4)", id="csr-btn", variant="primary"),
                Static("", id="status"),
            ),
            id="screen-center",
        )

    @on(Button.Pressed, "#csr-btn")
    def _csr_button(self) -> None:
        """Handle CSR generation button press."""
        self.action_create_csr()

    def action_create_csr(self) -> None:
        """Generate CSR and associated key from current form values."""
        cn = self.query_one("#cn", Input).value.strip()
        key_size = int(self.query_one("#key-size", Select).value)
        sans = [value.strip() for value in self.query_one("#sans", Input).value.split(",") if value.strip()]
        subject = {
            "O": self.query_one("#org", Input).value.strip(),
            "OU": self.query_one("#ou", Input).value.strip(),
            "L": self.query_one("#loc", Input).value.strip(),
            "ST": self.query_one("#state", Input).value.strip(),
            "C": self.query_one("#country", Input).value.strip(),
        }
        subject = {k: v for k, v in subject.items() if v}
        status = self.query_one("#status", Static)
        try:
            csr_path, key_path = self.manager.create_csr(cn, key_size, subject, sans)
            status.update(f"Created CSR: {csr_path} | Key: {key_path}")
            self.notify("CSR generated", timeout=2)
        except Exception as exc:  # noqa: BLE001
            status.update(f"Error: {exc}")
