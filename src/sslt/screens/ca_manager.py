from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static

from sslt.services.cert_manager import CertificateManager


class LocalCaScreen(Screen[None]):
    """Screen for creating, trusting, and deleting the local CA."""

    BINDINGS = [
        ("q", "app.pop_screen", "Back"),
        ("f5", "create_ca", "Create CA"),
        ("f6", "install_trust", "Install Trust"),
        ("f7", "delete_ca", "Delete CA"),
    ]

    def __init__(self, manager: CertificateManager) -> None:
        """Store certificate service dependency for CA operations."""
        super().__init__()
        self.manager = manager

    def compose(self) -> ComposeResult:
        """Render local CA controls and status fields."""
        yield Container(
            Vertical(
                Label("Local Certificate Authority"),
                Input(value="SSLT Local Development CA", id="ca-cn", placeholder="CA Common Name"),
                Input(value="3650", id="ca-days", placeholder="Validity days"),
                Input(password=True, id="sudo-password", placeholder="Sudo password (optional)"),
                Button("Create Local CA (F5)", id="create-ca-btn", variant="primary"),
                Button("Install CA Trust on this machine (F6)", id="trust-btn"),
                Button("Delete Local CA (F7)", id="delete-ca-btn", variant="error"),
                Static(
                    "If trust install fails due to sudo, enter password above and retry.",
                    id="ca-help",
                ),
                Static("", id="ca-diagnostics"),
                Static("", id="status"),
            ),
            id="screen-center",
        )

    def on_mount(self) -> None:
        """Refresh diagnostics when the screen is shown."""
        self._refresh_diagnostics()

    @on(Button.Pressed, "#create-ca-btn")
    def _create_button(self) -> None:
        """Handle create-CA button press."""
        self.action_create_ca()

    @on(Button.Pressed, "#trust-btn")
    def _trust_button(self) -> None:
        """Handle install-trust button press."""
        self.action_install_trust()

    @on(Button.Pressed, "#delete-ca-btn")
    def _delete_button(self) -> None:
        """Handle delete-CA button press."""
        self.action_delete_ca()

    def action_create_ca(self) -> None:
        """Create a local CA certificate and key."""
        cn = self.query_one("#ca-cn", Input).value.strip()
        days = int(self.query_one("#ca-days", Input).value.strip() or "3650")
        status = self.query_one("#status", Static)
        try:
            cert_path = self.manager.create_local_ca(cn, days)
            status.update(f"Created local CA: {cert_path}")
            self.notify("Local CA created", timeout=2)
            self._refresh_diagnostics()
        except Exception as exc:  # noqa: BLE001
            status.update(f"Error: {exc}")

    def action_install_trust(self) -> None:
        """Install the local CA into the OS trust store."""
        status = self.query_one("#status", Static)
        password_input = self.query_one("#sudo-password", Input)
        sudo_password = password_input.value.strip() or None
        try:
            message = self.manager.install_local_ca_trust(sudo_password=sudo_password)
            status.update(message)
            self.notify("Local CA trust installed", timeout=2)
            self._refresh_diagnostics()
        except Exception as exc:  # noqa: BLE001
            status.update(f"Error: {exc}")
        finally:
            password_input.value = ""

    def action_delete_ca(self) -> None:
        """Delete local CA files if they exist."""
        status = self.query_one("#status", Static)
        try:
            deleted = self.manager.delete_local_ca()
            if deleted:
                status.update("Deleted local CA files.")
                self.notify("Local CA deleted", timeout=2)
                self._refresh_diagnostics()
            else:
                status.update("No local CA found to delete.")
        except Exception as exc:  # noqa: BLE001
            status.update(f"Error: {exc}")

    def _refresh_diagnostics(self) -> None:
        """Update CA presence and trust-backend diagnostics text."""
        ca_state = "Present" if self.manager.has_local_ca() else "Not present"
        backend = self.manager.detect_trust_backend()
        self.query_one("#ca-diagnostics", Static).update(
            f"Local CA: {ca_state} | Trust backend: {backend}"
        )
