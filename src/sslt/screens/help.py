from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Label

from sslt.help_data import KeybindingHelp


class HelpScreen(ModalScreen[None]):
    """Modal that displays all configured hotkeys and actions."""

    BINDINGS = [("q", "dismiss", "Back"), ("escape", "dismiss", "Back")]

    def __init__(self, items: list[KeybindingHelp]) -> None:
        """Accept help rows to render in the table."""
        super().__init__()
        self.items = items

    def compose(self) -> ComposeResult:
        """Render help modal layout."""
        yield Container(
            Label("Hotkeys", id="help-title"),
            DataTable(id="help-table"),
            Footer(),
            id="screen-center",
        )

    def on_mount(self) -> None:
        """Populate table rows after mount."""
        table = self.query_one("#help-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Key", "Action", "Description")
        for item in self.items:
            table.add_row(item.key, item.action, item.description)
