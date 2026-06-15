"""Tests for Garden Irrigation firmware update metadata helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest

_ROOT = Path(__file__).resolve().parents[1]
_COMPONENT_PATH = _ROOT / "custom_components" / "garden_irrigation"

_PACKAGE = types.ModuleType("garden_irrigation_testpkg")
_PACKAGE.__path__ = [str(_COMPONENT_PATH)]  # type: ignore[attr-defined]
sys.modules[_PACKAGE.__name__] = _PACKAGE


def _load_module(name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


protocol = _load_module(
    "garden_irrigation_testpkg.protocol",
    _COMPONENT_PATH / "protocol.py",
)
ota_update = _load_module(
    "garden_irrigation_testpkg.ota_update",
    _COMPONENT_PATH / "ota_update.py",
)


class GardenIrrigationOtaUpdateTest(unittest.TestCase):
    """OTA update metadata tests without Home Assistant runtime imports."""

    def test_extracts_firmware_status_from_network_status(self) -> None:
        status = ota_update.firmware_status_from_network_status(
            {
                "version": "0.2.0",
                "build_id": "abc123-xiao",
                "board": "xiao-esp32c6",
                "chip": "esp32c6",
            }
        )

        self.assertEqual(status.display_version, "0.2.0+abc123-xiao")
        self.assertEqual(status.board, "xiao-esp32c6")

    def test_detects_newer_manifest(self) -> None:
        installed = ota_update.FirmwareStatus(
            version="0.2.0",
            build_id="old",
            board="xiao-esp32c6",
            chip="esp32c6",
        )
        manifest = protocol.parse_ota_manifest(
            {
                "schema": "garden-ota-manifest/v1",
                "product": "garden-irrigation",
                "application": "garden-firmware",
                "board": "xiao-esp32c6",
                "chip": "esp32c6",
                "version": "0.3.0",
                "image": {
                    "file": "garden-firmware-xiao-esp32c6.bin",
                    "size_bytes": 712976,
                    "sha256": (
                        "4e23fc7f1349beef5b55d33440efca35fccb5ce28db952fd"
                        "6469ebb84a31ffde"
                    ),
                },
            }
        )

        metadata = ota_update.evaluate_firmware_update(installed, manifest)

        self.assertTrue(metadata.update_available)
        self.assertEqual(metadata.latest_version, "0.3.0")

    def test_same_manifest_version_does_not_report_update_with_build_suffix(
        self,
    ) -> None:
        installed = ota_update.FirmwareStatus(
            version="0.3.0",
            build_id="abc123-xiao",
            board="xiao-esp32c6",
            chip="esp32c6",
        )
        manifest = protocol.parse_ota_manifest(
            {
                "schema": "garden-ota-manifest/v1",
                "product": "garden-irrigation",
                "application": "garden-firmware",
                "board": "xiao-esp32c6",
                "chip": "esp32c6",
                "version": "0.3.0",
                "image": {
                    "file": "garden-firmware-xiao-esp32c6.bin",
                    "size_bytes": 712976,
                    "sha256": (
                        "4e23fc7f1349beef5b55d33440efca35fccb5ce28db952fd"
                        "6469ebb84a31ffde"
                    ),
                },
            }
        )

        metadata = ota_update.evaluate_firmware_update(installed, manifest)

        self.assertFalse(metadata.update_available)
        self.assertEqual(metadata.latest_version, "0.3.0+abc123-xiao")

    def test_rejects_manifest_for_different_board(self) -> None:
        installed = ota_update.FirmwareStatus(
            version="0.2.0",
            build_id="old",
            board="xiao-esp32c6",
            chip="esp32c6",
        )
        manifest = protocol.parse_ota_manifest(
            {
                "schema": "garden-ota-manifest/v1",
                "product": "garden-irrigation",
                "application": "garden-firmware",
                "board": "esp32c3-devkit-rust-1",
                "chip": "esp32c3",
                "version": "0.3.0",
                "image": {
                    "file": "garden-firmware-esp32c3-devkit-rust-1.bin",
                    "size_bytes": 712976,
                    "sha256": (
                        "4e23fc7f1349beef5b55d33440efca35fccb5ce28db952fd"
                        "6469ebb84a31ffde"
                    ),
                },
            }
        )

        with self.assertRaises(protocol.ProtocolError):
            ota_update.evaluate_firmware_update(installed, manifest)

    def test_compares_semantic_versions(self) -> None:
        self.assertGreater(ota_update.compare_versions("0.3.0", "0.2.9"), 0)
        self.assertEqual(ota_update.compare_versions("0.3.0", "0.3.0"), 0)
        self.assertLess(ota_update.compare_versions("0.3.0", "0.3.1"), 0)


if __name__ == "__main__":
    unittest.main()
