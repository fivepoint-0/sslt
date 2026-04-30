from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

from textual.widgets import Input, Select

from sslt.app import SSLTuiApp
from sslt.models import CertificateRecord
from sslt.services.cert_manager import CertificateManager
from sslt.services.store import CertificateStore


def _record(cert_id: str = "demo001", common_name: str = "demo.domain.net") -> CertificateRecord:
    return CertificateRecord(
        cert_id=cert_id,
        common_name=common_name,
        cert_path="/tmp/demo-cert.pem",
        key_path="/tmp/demo-key.pem",
        created_at="2026-01-01T00:00:00+00:00",
        not_before="2026-01-01T00:00:00+00:00",
        not_after="2027-01-01T00:00:00+00:00",
        key_size=2048,
        serial_number="0x1234",
        subject=f"CN={common_name}",
        issuer=f"CN={common_name}",
        signature_algorithm="sha256",
        san=[common_name, "www.demo.domain.net"],
        sha1_fingerprint="aa:bb:cc",
        sha256_fingerprint="11:22:33",
    )


async def _capture() -> None:
    out_dir = Path("docs/screenshots")
    out_dir.mkdir(parents=True, exist_ok=True)
    names = {
        "home": "home.svg",
        "create": "create-certificate.svg",
        "list": "list-inspect.svg",
        "export": "export-certificate.svg",
        "import": "import-certificate.svg",
        "csr": "generate-csr.svg",
        "ca": "local-ca.svg",
        "help": "help.svg",
    }

    temp_store = Path(tempfile.mkdtemp(prefix="sslt-screenshot-store-"))
    app = SSLTuiApp()
    app.store = CertificateStore(root=temp_store)
    app.manager = CertificateManager(app.store)
    seeded = _record()
    app.store.add_record(seeded)

    def fake_create(*args, **kwargs):  # noqa: ANN002, ANN003
        return _record("created001", "created.domain.net")

    def fake_csr(*args, **kwargs):  # noqa: ANN002, ANN003
        return (Path("/tmp/request.csr.pem"), Path("/tmp/request.key.pem"))

    def fake_import(*args, **kwargs):  # noqa: ANN002, ANN003
        return _record("import001", "imported.domain.net")

    def fake_export(*args, **kwargs):  # noqa: ANN002, ANN003
        return Path("/tmp/exports/demo001.pem")

    def fake_create_ca(*args, **kwargs):  # noqa: ANN002, ANN003
        return Path("/tmp/local_ca/ca.crt.pem")

    def fake_install_ca(*args, **kwargs):  # noqa: ANN002, ANN003
        return "Installed local CA using update-ca-certificates."

    app.manager.create_self_signed_certificate = fake_create  # type: ignore[method-assign]
    app.manager.create_csr = fake_csr  # type: ignore[method-assign]
    app.manager.import_certificate = fake_import  # type: ignore[method-assign]
    app.manager.export_certificate = fake_export  # type: ignore[method-assign]
    app.manager.create_local_ca = fake_create_ca  # type: ignore[method-assign]
    app.manager.install_local_ca_trust = fake_install_ca  # type: ignore[method-assign]

    async with app.run_test(size=(120, 40)) as pilot:
        app.save_screenshot(str(out_dir / names["home"]))

        await pilot.press("n")
        create_screen = app.screen_stack[-1]
        create_screen.query_one("#cn", Input).value = "created.domain.net"
        create_screen.query_one("#signing-mode", Select).value = "self_signed"
        await pilot.press("ctrl+s")
        app.save_screenshot(str(out_dir / names["create"]))
        app.pop_screen()
        await pilot.pause()

        await pilot.press("l")
        details_screen = app.screen_stack[-1]
        cert_list = details_screen.query_one("#cert-list")
        cert_list.index = 0
        await pilot.pause()
        app.save_screenshot(str(out_dir / names["list"]))
        app.selected_record = seeded
        app.pop_screen()
        await pilot.pause()

        await pilot.press("e")
        export_screen = app.screen_stack[-1]
        export_screen.query_one("#format", Select).value = "pem"
        await pilot.press("ctrl+s")
        app.save_screenshot(str(out_dir / names["export"]))
        app.pop_screen()
        await pilot.pause()

        await pilot.press("i")
        import_screen = app.screen_stack[-1]
        import_screen.query_one("#cert-path", Input).value = "/tmp/demo-cert.pem"
        await pilot.press("f3")
        app.save_screenshot(str(out_dir / names["import"]))
        app.pop_screen()
        await pilot.pause()

        await pilot.press("c")
        csr_screen = app.screen_stack[-1]
        csr_screen.query_one("#cn", Input).value = "csr.domain.net"
        await pilot.press("f4")
        app.save_screenshot(str(out_dir / names["csr"]))
        app.pop_screen()
        await pilot.pause()

        await pilot.press("a")
        await pilot.press("f6")
        app.save_screenshot(str(out_dir / names["ca"]))
        app.pop_screen()
        await pilot.pause()

        await pilot.press("?")
        app.save_screenshot(str(out_dir / names["help"]))
        app.pop_screen()
        await pilot.pause()

    shutil.rmtree(temp_store, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(_capture())
