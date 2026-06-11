"""Tests for Garden Irrigation MQTT protocol helpers."""

from __future__ import annotations

import hashlib
import hmac
import importlib.util
from pathlib import Path
import sys
import unittest

_PROTOCOL_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "garden_irrigation"
    / "protocol.py"
)
_SPEC = importlib.util.spec_from_file_location("garden_irrigation_protocol", _PROTOCOL_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
protocol = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = protocol
_SPEC.loader.exec_module(protocol)


class GardenIrrigationProtocolTest(unittest.TestCase):
    """Protocol tests that do not require Home Assistant runtime imports."""

    def test_normalizes_base_topic(self) -> None:
        self.assertEqual(
            protocol.normalize_base_topic(" /garden/irrigation/xiao-1/ "),
            "garden/irrigation/xiao-1",
        )

        for invalid in ("", "garden//xiao", "garden/+/xiao", "garden/#"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(protocol.ProtocolError):
                    protocol.normalize_base_topic(invalid)

    def test_builds_base_topic_from_device_id(self) -> None:
        self.assertEqual(
            protocol.base_topic_from_device_id("xiao-esp32c6-1"),
            "garden/irrigation/xiao-esp32c6-1",
        )
        self.assertEqual(
            protocol.identity_topic("xiao-esp32c6-1"),
            "garden/irrigation/discovery/xiao-esp32c6-1",
        )
        with self.assertRaises(protocol.ProtocolError):
            protocol.base_topic_from_device_id("garden/xiao")

    def test_parses_identity_payload(self) -> None:
        identity = protocol.parse_identity_payload(
            {
                "schema": "garden-irrigation-device/v1",
                "device_id": "xiao-esp32c6-1",
                "base_topic": "garden/irrigation/xiao-esp32c6-1",
                "board": "xiao-esp32c6",
                "chip": "esp32c6",
                "firmware_version": "0.1.0",
                "firmware_build": "build-123",
                "protocol_schema": "garden-irrigation-mqtt/v1",
            }
        )

        self.assertEqual(identity.device_id, "xiao-esp32c6-1")
        self.assertEqual(identity.base_topic, "garden/irrigation/xiao-esp32c6-1")

    def test_rejects_identity_base_topic_mismatch(self) -> None:
        with self.assertRaises(protocol.ProtocolError):
            protocol.parse_identity_payload(
                {
                    "schema": "garden-irrigation-device/v1",
                    "device_id": "xiao-esp32c6-1",
                    "base_topic": "garden/irrigation/other",
                    "board": "xiao-esp32c6",
                    "chip": "esp32c6",
                    "firmware_version": "0.1.0",
                    "protocol_schema": "garden-irrigation-mqtt/v1",
                }
            )

    def test_builds_stable_topics(self) -> None:
        base = "garden/irrigation/xiao-1"

        self.assertEqual(
            protocol.availability_topic(base),
            "garden/irrigation/xiao-1/availability",
        )
        self.assertEqual(
            protocol.zone_command_topic(base, 2),
            "garden/irrigation/xiao-1/zone/2/command",
        )
        self.assertEqual(
            protocol.network_status_topic(base),
            "garden/irrigation/xiao-1/network/status",
        )
        self.assertEqual(
            protocol.wifi_signal_topic(base),
            "garden/irrigation/xiao-1/wifi/rssi",
        )
        self.assertEqual(
            protocol.zone_duration_command_topic(base, 2),
            "garden/irrigation/xiao-1/zone/2/duration_minutes/set",
        )

        with self.assertRaises(protocol.ProtocolError):
            protocol.zone_command_topic(base, 4)

    def test_parses_state_payloads(self) -> None:
        self.assertEqual(
            protocol.parse_availability("online"), protocol.Availability.ONLINE
        )
        self.assertEqual(
            protocol.parse_zone_state("watering"), protocol.ZoneState.WATERING
        )

        with self.assertRaises(protocol.ProtocolError):
            protocol.parse_availability("up")
        with self.assertRaises(protocol.ProtocolError):
            protocol.parse_zone_state("running")

    def test_parses_diagnostic_payloads(self) -> None:
        self.assertEqual(protocol.parse_wifi_rssi("-63"), -63)
        self.assertEqual(protocol.wifi_quality_percent(-63), 68)
        self.assertEqual(protocol.wifi_status_label(-63), "good")

        status = protocol.parse_network_status(
            '{"phase":"mqtt","reason":"connected","uptime_seconds":42}'
        )
        self.assertEqual(status["reason"], "connected")

        for invalid in ("abc", "-200", "1.5"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(protocol.ProtocolError):
                    protocol.parse_wifi_rssi(invalid)

        with self.assertRaises(protocol.ProtocolError):
            protocol.parse_network_status("not-json")

    def test_publish_helpers_never_retain_commands(self) -> None:
        base = "garden/irrigation/xiao-1"

        self.assertEqual(
            protocol.start_zone_publish(base, 1, 900),
            ("garden/irrigation/xiao-1/zone/1/command", "ON:900", 0, False),
        )
        self.assertEqual(
            protocol.stop_zone_publish(base, 1),
            ("garden/irrigation/xiao-1/zone/1/command", "STOP", 0, False),
        )
        self.assertEqual(
            protocol.stop_all_publish(base),
            ("garden/irrigation/xiao-1/command", "STOP_ALL", 0, False),
        )
        self.assertEqual(
            protocol.set_duration_publish(base, 1, 15),
            (
                "garden/irrigation/xiao-1/zone/1/duration_minutes/set",
                "15",
                0,
                False,
            ),
        )

    def test_rejects_unbounded_or_excessive_duration(self) -> None:
        base = "garden/irrigation/xiao-1"

        for seconds in (0, protocol.MAX_DURATION_SECONDS + 1):
            with self.subTest(seconds=seconds):
                with self.assertRaises(protocol.ProtocolError):
                    protocol.start_zone_publish(base, 0, seconds)

        for minutes in (0, protocol.MAX_DURATION_MINUTES + 1):
            with self.subTest(minutes=minutes):
                with self.assertRaises(protocol.ProtocolError):
                    protocol.set_duration_publish(base, 0, minutes)

    def test_validates_ota_manifest(self) -> None:
        manifest = protocol.parse_ota_manifest(
            {
                "schema": "garden-ota-manifest/v1",
                "product": "garden-irrigation",
                "application": "garden-firmware",
                "board": "xiao-esp32c6",
                "chip": "esp32c6",
                "version": "0.1.1",
                "image": {
                    "file": "garden-firmware-xiao-esp32c6.bin",
                    "size_bytes": 712976,
                    "sha256": "4e23fc7f1349beef5b55d33440efca35fccb5ce28db952fd6469ebb84a31ffde",
                },
            }
        )

        self.assertEqual(manifest.board, "xiao-esp32c6")
        self.assertEqual(manifest.image.size_bytes, 712976)

    def test_rejects_wrong_ota_manifest_identity(self) -> None:
        with self.assertRaises(protocol.ProtocolError):
            protocol.parse_ota_manifest(
                {
                    "schema": "garden-ota-manifest/v1",
                    "product": "other",
                    "application": "garden-firmware",
                    "board": "xiao-esp32c6",
                    "chip": "esp32c6",
                    "version": "0.1.1",
                    "image": {
                        "file": "garden-firmware-xiao-esp32c6.bin",
                        "size_bytes": 1,
                        "sha256": "0" * 64,
                    },
                }
            )

    def test_ota_hmac_message_matches_firmware_order(self) -> None:
        request = protocol.OtaRequest(
            product="garden-irrigation",
            application="garden-firmware",
            board="xiao-esp32c6",
            chip="esp32c6",
            version="0.1.1",
            host="192.168.1.20",
            port=8000,
            path="/garden.bin",
            size_bytes=712976,
            sha256="4e23fc7f1349beef5b55d33440efca35fccb5ce28db952fd6469ebb84a31ffde",
            challenge="0123456789abcdef0123456789abcdef",
            nonce="20260523T120000",
        )

        message = protocol.ota_hmac_message(request)

        self.assertEqual(
            message,
            "schema=garden-ota-request/v1;"
            "product=garden-irrigation;"
            "application=garden-firmware;"
            "board=xiao-esp32c6;"
            "chip=esp32c6;"
            "version=0.1.1;"
            "host=192.168.1.20;"
            "port=8000;"
            "path=/garden.bin;"
            "size=712976;"
            "sha256=4e23fc7f1349beef5b55d33440efca35fccb5ce28db952fd6469ebb84a31ffde;"
            "challenge=0123456789abcdef0123456789abcdef;"
            "nonce=20260523T120000;",
        )

    def test_signs_and_redacts_ota_request(self) -> None:
        request = protocol.OtaRequest(
            product="garden-irrigation",
            application="garden-firmware",
            board="xiao-esp32c6",
            chip="esp32c6",
            version="0.1.1",
            host="192.168.1.20",
            port=8000,
            path="/garden.bin",
            size_bytes=712976,
            sha256="4e23fc7f1349beef5b55d33440efca35fccb5ce28db952fd6469ebb84a31ffde",
            challenge="0123456789abcdef0123456789abcdef",
            nonce="20260523T120000",
        )
        key_hex = "11" * 32
        expected = hmac.new(
            bytes.fromhex(key_hex),
            protocol.ota_hmac_message(request).encode(),
            hashlib.sha256,
        ).hexdigest()

        payload = protocol.sign_ota_request(request, key_hex)

        self.assertTrue(payload.endswith(f"hmac={expected}"))
        self.assertIn("hmac=<redacted>", protocol.redact_ota_payload(payload))
        self.assertNotIn(expected, protocol.redact_ota_payload(payload))


if __name__ == "__main__":
    unittest.main()
