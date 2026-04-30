from __future__ import annotations

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Button, Footer, Header, Static

from sslt.help_data import GLOBAL_HELP
from sslt.models import CertificateRecord
from sslt.screens.ca_manager import LocalCaScreen
from sslt.screens.cert_details import CertificateDetailsScreen
from sslt.screens.create_cert import CreateCertificateScreen
from sslt.screens.csr import CsrScreen
from sslt.screens.export_cert import ExportCertificateScreen
from sslt.screens.help import HelpScreen
from sslt.screens.import_cert import ImportCertificateScreen
from sslt.services.cert_manager import CertificateManager
from sslt.services.store import CertificateStore


class SSLTuiApp(App[None]):
    """Top-level Textual app that coordinates screens and shared state."""

    TITLE = "SSL TUI Hub"
    CSS_PATH = "styles.tcss"
    BINDINGS = [
        ("n", "new_certificate", "New"),
        ("l", "list_certificates", "List"),
        ("e", "export_certificate", "Export"),
        ("i", "import_certificate", "Import"),
        ("c", "generate_csr", "CSR"),
        ("a", "manage_local_ca", "Local CA"),
        ("?", "help", "Help"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        """Initialize shared services and selected-certificate state."""
        super().__init__()
        self.store = CertificateStore()
        self.manager = CertificateManager(self.store)
        self.selected_record: CertificateRecord | None = None

    def compose(self) -> ComposeResult:
        """Render the home hub layout and global footer/header."""
        yield Header(show_clock=True)
        yield Container(
            Vertical(
                Static("SSL Certificate Hub", id="title"),
                Button("Create Certificate (n)", id="new", variant="primary"),
                Button("List / Inspect Certificates (l)", id="list"),
                Button("Export Selected Certificate (e)", id="export"),
                Button("Import Certificate (i)", id="import"),
                Button("Generate CSR (c)", id="csr"),
                Button("Manage Local CA (a)", id="ca"),
                Button("Help (?)", id="help"),
                Static("No certificate selected", id="selection-status"),
                id="home",
            ),
            id="screen-center",
        )
        yield Footer()

    @on(Button.Pressed, "#new")
    def _new_button(self) -> None:
        """Handle home button press for certificate creation."""
        self.action_new_certificate()

    @on(Button.Pressed, "#list")
    def _list_button(self) -> None:
        """Handle home button press for certificate list/details."""
        self.action_list_certificates()

    @on(Button.Pressed, "#export")
    def _export_button(self) -> None:
        """Handle home button press for export."""
        self.action_export_certificate()

    @on(Button.Pressed, "#help")
    def _help_button(self) -> None:
        """Handle home button press for help modal."""
        self.action_help()

    @on(Button.Pressed, "#import")
    def _import_button(self) -> None:
        """Handle home button press for certificate import."""
        self.action_import_certificate()

    @on(Button.Pressed, "#csr")
    def _csr_button(self) -> None:
        """Handle home button press for CSR generation."""
        self.action_generate_csr()

    @on(Button.Pressed, "#ca")
    def _ca_button(self) -> None:
        """Handle home button press for local CA management."""
        self.action_manage_local_ca()

    def action_new_certificate(self) -> None:
        """Open the create-certificate screen."""
        self.push_screen(CreateCertificateScreen(self.manager))

    def action_list_certificates(self) -> None:
        """Open the certificate list/details screen."""
        self.push_screen(
            CertificateDetailsScreen(self.store, self._open_export_for_record, self._delete_record),
            self._on_record_selected,
        )

    def action_export_certificate(self) -> None:
        """Open export for the currently selected certificate."""
        if self.selected_record is None:
            self.notify("Select a certificate first from the list screen.")
            return
        self.push_screen(ExportCertificateScreen(self.manager, self.selected_record))

    def action_help(self) -> None:
        """Open the keybindings/help modal."""
        self.push_screen(HelpScreen(GLOBAL_HELP))

    def action_import_certificate(self) -> None:
        """Open the certificate import screen."""
        self.push_screen(ImportCertificateScreen(self.manager))

    def action_generate_csr(self) -> None:
        """Open the CSR generation screen."""
        self.push_screen(CsrScreen(self.manager))

    def action_manage_local_ca(self) -> None:
        """Open the local certificate authority screen."""
        self.push_screen(LocalCaScreen(self.manager))

    def _on_record_selected(self, record: CertificateRecord | None) -> None:
        """Persist selected record and refresh home status text."""
        if record is None:
            return
        self.selected_record = record
        self.query_one("#selection-status", Static).update(
            f"Selected: {record.common_name} ({record.cert_id})"
        )

    def _open_export_for_record(self, record: CertificateRecord) -> None:
        """Select a record and open export screen for it."""
        self._on_record_selected(record)
        self.push_screen(ExportCertificateScreen(self.manager, record))

    def _delete_record(self, record: CertificateRecord) -> None:
        """Delete a record from storage and update home UI state."""
        removed = self.store.remove_record(record.cert_id)
        if removed:
            if self.selected_record and self.selected_record.cert_id == record.cert_id:
                self.selected_record = None
                self.query_one("#selection-status", Static).update("No certificate selected")
            self.notify(f"Deleted certificate {record.cert_id}")
        else:
            self.notify("Certificate not found in store.")


def main() -> None:
    """CLI script entrypoint for launching the Textual app."""
    SSLTuiApp().run()
