from __future__ import annotations

from datetime import UTC, datetime
from typing import Callable

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Label, ListItem, ListView, Static

from sslt.models import CertificateRecord
from sslt.services.store import CertificateStore


class CertificateDetailsScreen(Screen[CertificateRecord | None]):
    """Screen for browsing stored certificates and viewing full metadata."""

    BINDINGS = [
        ("q", "close_and_select", "Back"),
        ("r", "refresh", "Refresh"),
        ("enter", "show_selected", "Details"),
        ("e", "export_selected", "Export"),
        ("x", "delete_selected", "Delete"),
    ]

    def __init__(
        self,
        store: CertificateStore,
        on_export_selected: Callable[[CertificateRecord], None] | None = None,
        on_delete_selected: Callable[[CertificateRecord], None] | None = None,
    ) -> None:
        """Store callbacks for export/delete actions initiated from this screen."""
        super().__init__()
        self.store = store
        self.selected_record: CertificateRecord | None = None
        self.on_export_selected = on_export_selected
        self.on_delete_selected = on_delete_selected

    def compose(self) -> ComposeResult:
        """Render certificate list and details panes."""
        yield Container(
            Horizontal(
                Vertical(Label("Certificates"), ListView(id="cert-list"), Button("Refresh", id="refresh")),
                Vertical(Label("Details"), Static("Select a certificate", id="details-panel")),
                id="details-layout",
            ),
            id="screen-center",
        )

    def on_mount(self) -> None:
        """Load records when screen mounts."""
        self._load_records()

    @on(Button.Pressed, "#refresh")
    def _on_refresh_button(self) -> None:
        """Handle refresh button press."""
        self._load_records()

    def action_refresh(self) -> None:
        """Reload records from storage."""
        self._load_records()

    def _load_records(self) -> None:
        """Populate the list view with known certificates."""
        records = self.store.list_records()
        cert_list = self.query_one("#cert-list", ListView)
        cert_list.clear()
        for record in records:
            cert_list.append(ListItem(Label(f"{record.common_name} ({record.cert_id})"), name=record.cert_id))

    @on(ListView.Selected, "#cert-list")
    def on_selected(self, event: ListView.Selected) -> None:
        """Render details when a certificate is selected in the list."""
        if event.item is None or event.item.name is None:
            return
        record = self.store.get_record(event.item.name)
        if record is None:
            return
        self.selected_record = record
        self.query_one("#details-panel", Static).update(self._render_details(record))

    def action_show_selected(self) -> None:
        """Close screen returning current selection to the caller."""
        if self.selected_record is not None:
            self.dismiss(self.selected_record)

    def action_close_and_select(self) -> None:
        """Close screen preserving selection callback behavior."""
        self.dismiss(self.selected_record)

    def action_export_selected(self) -> None:
        """Invoke export callback for selected certificate."""
        if self.selected_record is None:
            self.notify("Select a certificate first.")
            return
        if self.on_export_selected is not None:
            self.on_export_selected(self.selected_record)

    def action_delete_selected(self) -> None:
        """Open delete-confirmation modal for selected certificate."""
        if self.selected_record is None:
            self.notify("Select a certificate first.")
            return
        self.app.push_screen(ConfirmDeleteScreen(self.selected_record), self._handle_delete_confirm)

    def _handle_delete_confirm(self, confirmed: bool | None) -> None:
        """Handle confirmation result and refresh local UI state."""
        if not confirmed or self.selected_record is None:
            return
        if self.on_delete_selected is not None:
            self.on_delete_selected(self.selected_record)
            self.selected_record = None
            self._load_records()
            self.query_one("#details-panel", Static).update("Certificate deleted.")

    @staticmethod
    def _render_details(record: CertificateRecord) -> str:
        """Return a human-readable details block for a certificate."""
        not_after = datetime.fromisoformat(record.not_after)
        days_remaining = (not_after - datetime.now(tz=UTC)).days
        status = "Valid" if days_remaining >= 0 else "Expired"
        san_text = ", ".join(record.san) if record.san else "None"
        return "\n".join(
            [
                f"ID: {record.cert_id}",
                f"Subject: {record.subject}",
                f"Issuer: {record.issuer}",
                f"Serial: {record.serial_number}",
                f"Key size: {record.key_size}",
                f"Signature: {record.signature_algorithm}",
                f"Valid from: {record.not_before}",
                f"Valid until: {record.not_after}",
                f"Status: {status} ({days_remaining} days remaining)",
                f"SANs: {san_text}",
                f"SHA1: {record.sha1_fingerprint}",
                f"SHA256: {record.sha256_fingerprint}",
            ]
        )


class ConfirmDeleteScreen(ModalScreen[bool]):
    """Confirmation modal used before deleting a certificate."""

    BINDINGS = [("y", "confirm", "Yes"), ("n", "cancel", "No"), ("q", "cancel", "Cancel")]

    def __init__(self, record: CertificateRecord) -> None:
        """Store selected record details for confirmation text."""
        super().__init__()
        self.record = record

    def compose(self) -> ComposeResult:
        """Render modal controls for delete confirmation."""
        yield Container(
            Vertical(
                Label(f"Delete certificate {self.record.common_name} ({self.record.cert_id})?"),
                Label("This removes it from local index and deletes stored files."),
                Button("Yes, delete", id="confirm-delete", variant="error"),
                Button("Cancel", id="cancel-delete"),
            ),
            id="screen-center",
        )

    @on(Button.Pressed, "#confirm-delete")
    def _confirm_button(self) -> None:
        """Handle confirm-delete button press."""
        self.dismiss(True)

    @on(Button.Pressed, "#cancel-delete")
    def _cancel_button(self) -> None:
        """Handle cancel button press."""
        self.dismiss(False)

    def action_confirm(self) -> None:
        """Confirm deletion via keyboard shortcut."""
        self.dismiss(True)

    def action_cancel(self) -> None:
        """Cancel deletion via keyboard shortcut."""
        self.dismiss(False)
