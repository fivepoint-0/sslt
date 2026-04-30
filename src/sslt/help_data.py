from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KeybindingHelp:
    """Describes a keybinding row rendered in the help screen."""

    key: str
    action: str
    description: str


GLOBAL_HELP: list[KeybindingHelp] = [
    KeybindingHelp("n", "new_certificate", "Create a new certificate"),
    KeybindingHelp("l", "list_certificates", "Show certificate list/details"),
    KeybindingHelp("e", "export_certificate", "Export selected certificate"),
    KeybindingHelp("i", "import_certificate", "Import certificate/key files"),
    KeybindingHelp("c", "generate_csr", "Generate certificate signing request"),
    KeybindingHelp("a", "local_ca", "Manage local certificate authority"),
    KeybindingHelp("x", "delete_selected", "Delete selected certificate"),
    KeybindingHelp("F2", "save_profile", "Save creation form defaults profile"),
    KeybindingHelp("F3", "import", "Import certificate in import screen"),
    KeybindingHelp("F4", "csr", "Generate CSR in CSR screen"),
    KeybindingHelp("F5", "create_ca", "Create local CA in CA screen"),
    KeybindingHelp("F6", "install_trust", "Install local CA trust"),
    KeybindingHelp("F7", "delete_ca", "Delete local CA in CA screen"),
    KeybindingHelp("?", "help", "Open help window"),
    KeybindingHelp("q", "quit_or_back", "Quit app or close current modal"),
]
