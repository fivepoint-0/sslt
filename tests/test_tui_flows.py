from __future__ import annotations

import pytest
from textual.widgets import Input, Select, Static

from sslt.app import SSLTuiApp
from sslt.models import CertificateRecord
from sslt.screens.ca_manager import LocalCaScreen
from sslt.screens.cert_details import CertificateDetailsScreen, ConfirmDeleteScreen
from sslt.screens.create_cert import CreateCertificateScreen
from sslt.screens.export_cert import ExportCertificateScreen
from sslt.services.cert_manager import CertificateManager
from sslt.services.store import CertificateStore


def _record(cert_id: str = "abc123", common_name: str = "example.com") -> CertificateRecord:
    """Return a representative record used in TUI interaction tests."""
    return CertificateRecord(
        cert_id=cert_id,
        common_name=common_name,
        cert_path="/tmp/cert.pem",
        key_path="/tmp/key.pem",
        created_at="2026-01-01T00:00:00+00:00",
        not_before="2026-01-01T00:00:00+00:00",
        not_after="2027-01-01T00:00:00+00:00",
        key_size=2048,
        serial_number="0x1234",
        subject=f"CN={common_name}",
        issuer=f"CN={common_name}",
        signature_algorithm="sha256",
        san=[common_name],
        sha1_fingerprint="aa",
        sha256_fingerprint="bb",
    )


def _text(static_widget: Static) -> str:
    """Render a Static widget into plain string text for assertions."""
    return str(static_widget.render())


@pytest.mark.asyncio
async def test_create_certificate_hotkey_submits_form(tmp_path) -> None:
    """Create screen should submit via hotkey and update status output."""
    app = SSLTuiApp()
    app.store = CertificateStore(root=tmp_path / "store")
    app.manager = CertificateManager(app.store)

    fake = _record("created001", "sub.domain.net")

    def fake_create(*args, **kwargs):  # noqa: ANN002, ANN003
        """Return deterministic record without invoking OpenSSL."""
        return fake

    app.manager.create_self_signed_certificate = fake_create  # type: ignore[method-assign]

    async with app.run_test() as pilot:
        await pilot.press("n")
        create_screen = app.screen_stack[-1]
        assert isinstance(create_screen, CreateCertificateScreen)
        create_screen.query_one("#cn", Input).value = "sub.domain.net"
        await pilot.press("ctrl+s")
        status = _text(create_screen.query_one("#status", Static))
        assert "Created certificate created001" in status


@pytest.mark.asyncio
async def test_create_certificate_passes_selected_signing_mode(tmp_path) -> None:
    """Create screen should forward selected signing mode to service call."""
    app = SSLTuiApp()
    app.store = CertificateStore(root=tmp_path / "store")
    app.manager = CertificateManager(app.store)

    captured: dict[str, str] = {}

    def fake_create(*args, **kwargs):  # noqa: ANN002, ANN003
        """Capture signing mode argument and return fake result."""
        captured["signing_mode"] = kwargs["signing_mode"]
        return _record("created002", "mode.test")

    app.manager.create_self_signed_certificate = fake_create  # type: ignore[method-assign]

    async with app.run_test() as pilot:
        await pilot.press("n")
        create_screen = app.screen_stack[-1]
        assert isinstance(create_screen, CreateCertificateScreen)
        create_screen.query_one("#cn", Input).value = "mode.test"
        create_screen.query_one("#signing-mode", Select).value = "local_ca"
        await pilot.press("ctrl+s")
        assert captured["signing_mode"] == "local_ca"


@pytest.mark.asyncio
async def test_details_screen_export_hotkey_opens_export_screen(tmp_path) -> None:
    """Details screen export hotkey should navigate to export screen."""
    app = SSLTuiApp()
    app.store = CertificateStore(root=tmp_path / "store")
    app.manager = CertificateManager(app.store)
    record = _record("rec001", "export.test")
    app.store.add_record(record)

    async with app.run_test() as pilot:
        await pilot.press("l")
        details_screen = app.screen_stack[-1]
        assert isinstance(details_screen, CertificateDetailsScreen)
        details_screen.selected_record = record
        await pilot.press("e")
        assert isinstance(app.screen_stack[-1], ExportCertificateScreen)


@pytest.mark.asyncio
async def test_details_screen_delete_confirmation_removes_record(tmp_path) -> None:
    """Delete confirmation flow should remove selected certificate."""
    app = SSLTuiApp()
    app.store = CertificateStore(root=tmp_path / "store")
    app.manager = CertificateManager(app.store)
    record = _record("rec-delete", "delete.test")
    app.store.add_record(record)

    async with app.run_test() as pilot:
        await pilot.press("l")
        details_screen = app.screen_stack[-1]
        assert isinstance(details_screen, CertificateDetailsScreen)
        details_screen.selected_record = record
        await pilot.press("x")
        assert isinstance(app.screen_stack[-1], ConfirmDeleteScreen)
        await pilot.press("y")
        assert app.store.get_record("rec-delete") is None


@pytest.mark.asyncio
async def test_local_ca_screen_shows_diagnostics_and_clears_password(tmp_path) -> None:
    """CA screen should display diagnostics and clear password after install."""
    app = SSLTuiApp()
    app.store = CertificateStore(root=tmp_path / "store")
    app.manager = CertificateManager(app.store)

    def fake_install(sudo_password=None):  # noqa: ANN001
        """Fake trust installation to avoid privileged system changes in tests."""
        assert sudo_password == "topsecret"
        return "Installed mock trust."

    app.manager.install_local_ca_trust = fake_install  # type: ignore[method-assign]

    async with app.run_test() as pilot:
        await pilot.press("a")
        ca_screen = app.screen_stack[-1]
        assert isinstance(ca_screen, LocalCaScreen)
        diagnostics = _text(ca_screen.query_one("#ca-diagnostics", Static))
        assert "Local CA:" in diagnostics
        assert "Trust backend:" in diagnostics

        password_input = ca_screen.query_one("#sudo-password", Input)
        password_input.value = "topsecret"
        await pilot.press("f6")
        assert password_input.value == ""
        status = _text(ca_screen.query_one("#status", Static))
        assert "Installed mock trust." in status
