"""Tests for Garden Irrigation options validation."""

from __future__ import annotations

import importlib.util
import sys
import unittest

from garden_irrigation_test_support import COMPONENT_PATH

_OPTIONS_PATH = COMPONENT_PATH / "options.py"
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
        self.assertEqual(parsed.ota_github_repository, "")
        self.assertEqual(parsed.ota_github_token, "")

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

    def test_accepts_private_github_release_source(self) -> None:
        parsed = options.validate_options(
            "",
            "",
            " michalpalkowski/garden-irrigation ",
            " github_pat_read_only_token_1234567890 ",
        )

        self.assertEqual(
            parsed.ota_github_repository,
            "michalpalkowski/garden-irrigation",
        )
        self.assertEqual(parsed.ota_github_token, "github_pat_read_only_token_1234567890")

    def test_requires_complete_single_ota_source(self) -> None:
        public = options.validate_options("", "", "owner/repo", "")
        self.assertEqual(public.ota_github_repository, "owner/repo")
        with self.assertRaisesRegex(ValueError, "incomplete_ota_github_credentials"):
            options.validate_options("", "", "", "github_pat_read_only_token_1234567890")
        with self.assertRaisesRegex(ValueError, "multiple_ota_sources"):
            options.validate_options(
                "",
                "https://example.com/manifest.json",
                "owner/repo",
                "github_pat_read_only_token_1234567890",
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
