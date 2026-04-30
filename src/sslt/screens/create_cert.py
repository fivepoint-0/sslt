from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Select, Static

from sslt.services.cert_manager import CertificateManager


class CreateCertificateScreen(Screen[None]):
    """Form screen for creating certificates and saving default profile fields."""

    BINDINGS = [
        ("q", "app.pop_screen", "Back"),
        ("ctrl+s", "save_certificate", "Create"),
        ("f2", "save_profile_defaults", "Save Profile"),
    ]

    def __init__(self, manager: CertificateManager) -> None:
        """Store certificate service dependency for form actions."""
        super().__init__()
        self.manager = manager

    def compose(self) -> ComposeResult:
        """Render certificate create form controls."""
        yield Container(
            Vertical(
                Label("Create Certificate"),
                Input(placeholder="Common Name (required)", id="cn"),
                Input(placeholder="Validity days (default: 365)", id="days"),
                Select(
                    [
                        ("Auto (use local CA if available)", "auto"),
                        ("Self-signed", "self_signed"),
                        ("Local CA", "local_ca"),
                    ],
                    value="auto",
                    id="signing-mode",
                ),
                Select([(str(2048), 2048), (str(4096), 4096)], value=2048, id="key-size"),
                Input(placeholder="Organization (O)", id="org"),
                Input(placeholder="Org Unit (OU)", id="ou"),
                Input(placeholder="Locality (L)", id="loc"),
                Input(placeholder="State (ST)", id="state"),
                Input(placeholder="Country (C)", id="country"),
                Input(placeholder="SANs comma-separated (optional)", id="sans"),
                Button("Create", id="create-btn", variant="primary"),
                Button("Save current fields as defaults (F2)", id="save-defaults-btn"),
                Static("", id="status"),
            ),
            id="screen-center",
        )

    def on_mount(self) -> None:
        """Prefill fields with persisted defaults when the screen opens."""
        defaults = self.manager.store.get_defaults()
        self.query_one("#days", Input).value = defaults.get("days", "365")
        self.query_one("#org", Input).value = defaults.get("O", "")
        self.query_one("#ou", Input).value = defaults.get("OU", "")
        self.query_one("#loc", Input).value = defaults.get("L", "")
        self.query_one("#state", Input).value = defaults.get("ST", "")
        self.query_one("#country", Input).value = defaults.get("C", "")
        self.query_one("#sans", Input).value = defaults.get("sans", "")
        key_size = defaults.get("key_size", "2048")
        self.query_one("#key-size", Select).value = int(key_size)
        self.query_one("#signing-mode", Select).value = defaults.get("signing_mode", "auto")

    @on(Button.Pressed, "#create-btn")
    def save_via_button(self) -> None:
        """Create certificate when the primary button is clicked."""
        self.action_save_certificate()

    @on(Button.Pressed, "#save-defaults-btn")
    def save_defaults_via_button(self) -> None:
        """Persist defaults when the save-defaults button is clicked."""
        self.action_save_profile_defaults()

    def action_save_certificate(self) -> None:
        """Collect form values and run certificate creation."""
        cn = self.query_one("#cn", Input).value.strip()
        days_input = self.query_one("#days", Input).value.strip() or "365"
        key_size = int(self.query_one("#key-size", Select).value)
        sans_input = self.query_one("#sans", Input).value.strip()

        subject = {
            "O": self.query_one("#org", Input).value.strip(),
            "OU": self.query_one("#ou", Input).value.strip(),
            "L": self.query_one("#loc", Input).value.strip(),
            "ST": self.query_one("#state", Input).value.strip(),
            "C": self.query_one("#country", Input).value.strip(),
        }
        subject = {k: v for k, v in subject.items() if v}
        sans = [value.strip() for value in sans_input.split(",") if value.strip()]
        status = self.query_one("#status", Static)

        try:
            record = self.manager.create_self_signed_certificate(
                common_name=cn,
                key_size=key_size,
                validity_days=int(days_input),
                subject_fields=subject,
                sans=sans,
                signing_mode=str(self.query_one("#signing-mode", Select).value),
            )
            status.update(f"Created certificate {record.cert_id}")
        except Exception as exc:  # noqa: BLE001
            status.update(f"Error: {exc}")

    def action_save_profile_defaults(self) -> None:
        """Persist current form values as future defaults."""
        defaults = {
            "days": self.query_one("#days", Input).value.strip() or "365",
            "key_size": str(self.query_one("#key-size", Select).value),
            "signing_mode": str(self.query_one("#signing-mode", Select).value),
            "O": self.query_one("#org", Input).value.strip(),
            "OU": self.query_one("#ou", Input).value.strip(),
            "L": self.query_one("#loc", Input).value.strip(),
            "ST": self.query_one("#state", Input).value.strip(),
            "C": self.query_one("#country", Input).value.strip(),
            "sans": self.query_one("#sans", Input).value.strip(),
        }
        self.manager.store.save_defaults(defaults)
        self.query_one("#status", Static).update("Saved profile defaults.")
        self.notify("Saved profile defaults.", timeout=2)
