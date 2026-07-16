"""Tests for private GitHub firmware release metadata."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest

from garden_irrigation_test_support import COMPONENT_PATH

_PACKAGE = types.ModuleType("garden_irrigation_github_testpkg")
_PACKAGE.__path__ = [str(COMPONENT_PATH)]  # type: ignore[attr-defined]
sys.modules[_PACKAGE.__name__] = _PACKAGE


def _load(name: str, filename: str) -> object:
    spec = importlib.util.spec_from_file_location(
        f"{_PACKAGE.__name__}.{name}", COMPONENT_PATH / filename
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


protocol = _load("protocol", "protocol.py")
github_release = _load("github_release", "github_release.py")


def _release_payload() -> dict[str, object]:
    return {
        "tag_name": "firmware-stable-abc123",
        "assets": [
            {
                "name": "garden-firmware-xiao-esp32c6.manifest.json",
                "url": (
                    "https://api.github.com/repos/owner/repo/releases/assets/101"
                ),
            },
            {
                "name": "garden-firmware-xiao-esp32c6.bin",
                "url": (
                    "https://api.github.com/repos/owner/repo/releases/assets/102"
                ),
            },
        ],
    }


class GardenIrrigationGithubReleaseTest(unittest.TestCase):
    def test_parses_exact_release_assets(self) -> None:
        release = github_release.parse_release_assets(_release_payload())

        self.assertEqual(release.tag_name, "firmware-stable-abc123")
        self.assertEqual(
            release.image_url("garden-firmware-xiao-esp32c6.bin"),
            "https://api.github.com/repos/owner/repo/releases/assets/102",
        )

    def test_rejects_non_github_asset_origin(self) -> None:
        payload = _release_payload()
        payload["assets"][0]["url"] = "https://example.com/manifest.json"  # type: ignore[index]

        with self.assertRaisesRegex(protocol.ProtocolError, "asset URL is invalid"):
            github_release.parse_release_assets(payload)

    def test_requires_manifest_and_requested_image(self) -> None:
        payload = _release_payload()
        payload["assets"] = payload["assets"][1:]  # type: ignore[index]
        with self.assertRaisesRegex(protocol.ProtocolError, "missing an OTA manifest"):
            github_release.parse_release_assets(payload)

        release = github_release.parse_release_assets(_release_payload())
        with self.assertRaisesRegex(protocol.ProtocolError, "missing asset other.bin"):
            release.image_url("other.bin")


if __name__ == "__main__":
    unittest.main()
