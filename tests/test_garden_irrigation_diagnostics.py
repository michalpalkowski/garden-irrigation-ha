"""Tests for Garden Irrigation diagnostics helpers."""

from __future__ import annotations

import importlib.util
import sys
import unittest

from garden_irrigation_test_support import COMPONENT_PATH

_REDACTION_PATH = COMPONENT_PATH / "diagnostic_redaction.py"
_SPEC = importlib.util.spec_from_file_location(
    "garden_irrigation_diagnostic_redaction", _REDACTION_PATH
)
assert _SPEC is not None
assert _SPEC.loader is not None
redaction = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = redaction
_SPEC.loader.exec_module(redaction)


class GardenIrrigationDiagnosticsTest(unittest.TestCase):
    """Diagnostics tests that do not require Home Assistant runtime imports."""

    def test_redacts_secret_like_keys_recursively(self) -> None:
        payload = {
            "phase": "mqtt",
            "wifi_ssid": "garden-wifi",
            "password": "wifi-password",
            "ota": {
                "signing_private_key": "11" * 32,
                "last_signature": "22" * 32,
                "nonce": "20260611T101500",
            },
            "events": [
                {"api-token": "abc"},
                {"reason": "connected"},
            ],
        }

        redacted = redaction.redact_diagnostics_payload(payload)

        self.assertEqual(redacted["phase"], "mqtt")
        self.assertEqual(redacted["wifi_ssid"], "garden-wifi")
        self.assertEqual(redacted["password"], redaction.REDACTED_VALUE)
        self.assertEqual(redacted["ota"]["signing_private_key"], redaction.REDACTED_VALUE)
        self.assertEqual(
            redacted["ota"]["last_signature"], redaction.REDACTED_VALUE
        )
        self.assertEqual(redacted["ota"]["nonce"], "20260611T101500")
        self.assertEqual(redacted["events"][0]["api-token"], redaction.REDACTED_VALUE)
        self.assertEqual(redacted["events"][1]["reason"], "connected")


if __name__ == "__main__":
    unittest.main()
