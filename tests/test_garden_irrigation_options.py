"""Tests for Garden Irrigation options validation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

_OPTIONS_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "garden_irrigation"
    / "options.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "garden_irrigation_options",
    _OPTIONS_PATH,
)
assert _SPEC is not None
assert _SPEC.loader is not None
options = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = options
_SPEC.loader.exec_module(options)


class GardenIrrigationOptionsTest(unittest.TestCase):
    """Options validation tests without Home Assistant runtime imports."""

    def test_accepts_empty_options(self) -> None:
        parsed = options.validate_options(None, "")

        self.assertEqual(parsed.weather_entity, "")
        self.assertEqual(parsed.ota_manifest_url, "")

    def test_accepts_weather_entity_and_https_manifest(self) -> None:
        parsed = options.validate_options(
            " weather.forecast_dom ",
            " https://example.com/garden-firmware-xiao.manifest.json ",
        )

        self.assertEqual(parsed.weather_entity, "weather.forecast_dom")
        self.assertEqual(
            parsed.ota_manifest_url,
            "https://example.com/garden-firmware-xiao.manifest.json",
        )

    def test_rejects_non_weather_entity(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid_weather_entity"):
            options.validate_options("sensor.outdoor_temperature", "")

    def test_rejects_non_https_manifest_url(self) -> None:
        for invalid in (
            "http://example.com/manifest.json",
            "https://",
            "https://example.com",
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "invalid_ota_manifest_url"):
                    options.validate_options("", invalid)


if __name__ == "__main__":
    unittest.main()
