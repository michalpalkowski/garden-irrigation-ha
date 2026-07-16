"""Tests for Garden Irrigation MQTT protocol helpers."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest

from garden_irrigation_test_support import COMPONENT_PATH

_PROTOCOL_PATH = COMPONENT_PATH / "protocol.py"
_SPEC = importlib.util.spec_from_file_location("garden_irrigation_protocol", _PROTOCOL_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
protocol = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = protocol
_SPEC.loader.exec_module(protocol)

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load_fixture(name: str) -> dict[str, object]:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


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
        self.assertEqual(
            protocol.runtime_identity_topic("garden/irrigation/xiao-esp32c6-1"),
            "garden/irrigation/xiao-esp32c6-1/identity",
        )
        with self.assertRaises(protocol.ProtocolError):
            protocol.base_topic_from_device_id("garden/xiao")

    def test_parses_identity_payload(self) -> None:
        identity = protocol.parse_identity_payload(_load_fixture("identity.valid.json"))

        self.assertEqual(identity.device_id, "xiao-esp32c6-1")
        self.assertEqual(identity.base_topic, "garden/irrigation/xiao-esp32c6-1")
        self.assertEqual(identity.capabilities["zones"], 4)

    def test_allows_identity_base_topic_migration(self) -> None:
        identity = protocol.parse_identity_payload(
            _load_fixture("identity.custom_base_topic.json")
        )

        self.assertEqual(identity.device_id, "xiao-esp32c6-1")
        self.assertEqual(
            identity.base_topic,
            "garden/irrigation/customer-a/controller-1",
        )

    def test_rejects_invalid_identity_capabilities(self) -> None:
        with self.assertRaises(protocol.ProtocolError):
            protocol.parse_identity_payload(
                _load_fixture("identity.invalid_capabilities.json")
            )

    def test_parses_claim_info_payload(self) -> None:
        info = protocol.parse_claim_info_payload(_load_fixture("claim.info.valid.json"))

        self.assertEqual(info.factory_id, "gi-c6-01HZX7M2P9F6T2Q1MZ4K8C3A")
        self.assertEqual(info.board, "xiao-esp32c6")
        self.assertIn(protocol.ClaimTransport.BLE, info.transports)
        self.assertEqual(info.expires_in_seconds, 300)

    def test_parses_and_redacts_claim_request_payload(self) -> None:
        payload = _load_fixture("claim.request.valid.json")

        request = protocol.parse_claim_request_payload(payload)
        rebuilt = protocol.build_claim_request_payload(request)
        redacted = protocol.redact_claim_payload(rebuilt)

        self.assertEqual(request.device_id, "garden-irrigation-a1b2c3")
        self.assertEqual(request.mqtt.host, "homeassistant.local")
        self.assertEqual(request.wifi.ssid, "Home-IoT")
        self.assertEqual(rebuilt["base_topic"], payload["base_topic"])
        self.assertEqual(redacted["pairing_code"], "<redacted>")
        self.assertEqual(redacted["wifi"]["password"], "<redacted>")
        self.assertEqual(redacted["mqtt"]["password"], "<redacted>")

    def test_rejects_claim_topic_that_does_not_match_device_id(self) -> None:
        payload = _load_fixture("claim.request.valid.json")
        payload["base_topic"] = "garden/irrigation/other-controller"

        with self.assertRaises(protocol.ProtocolError):
            protocol.parse_claim_request_payload(payload)

    def test_rejects_weak_claim_credentials(self) -> None:
        payload = _load_fixture("claim.request.valid.json")
        payload["pairing_code"] = "123"
        with self.assertRaises(protocol.ProtocolError):
            protocol.parse_claim_request_payload(payload)

        payload = _load_fixture("claim.request.valid.json")
        payload["wifi"]["password"] = "short"
        with self.assertRaises(protocol.ProtocolError):
            protocol.parse_claim_request_payload(payload)

    def test_parses_claim_result_payload(self) -> None:
        result = protocol.parse_claim_result_payload(
            _load_fixture("claim.result.accepted.json")
        )

        self.assertEqual(result.status, protocol.ClaimResultStatus.ACCEPTED)
        self.assertEqual(result.device_id, "garden-irrigation-a1b2c3")

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
            '{"board":"xiao-esp32c6","chip":"esp32c6","version":"0.3.0",'
            '"build_id":"abc123","phase":"mqtt","reason":"connected",'
            '"reset_reason":"sys_brownout","runtime_config_persisted":true,'
            '"mqtt_reconnects":2,'
            '"uptime_seconds":42,'
            '"free_heap_bytes":53248,"min_free_heap_bytes":49152,'
            '"heap_used_bytes":8192,"chip_temperature_celsius":61}'
        )
        self.assertEqual(status.reason, "connected")
        self.assertEqual(status.reset_reason, "sys_brownout")
        self.assertEqual(status.free_heap_bytes, 53248)
        self.assertEqual(status.chip_temperature_celsius, 61)

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
                "build_id": "xiao-esp32c6-test",
                "channel": "stable",
                "provisioning_required": False,
                "image": {
                    "file": "garden-firmware-xiao-esp32c6.bin",
                    "size_bytes": 712976,
                    "sha256": "4e23fc7f1349beef5b55d33440efca35fccb5ce28db952fd6469ebb84a31ffde",
                },
                "signature": {
                    "algorithm": "ecdsa-p256-sha256",
                    "format": "raw-r-s-hex",
                    "value": "ab" * 64,
                },
            }
        )

        self.assertEqual(manifest.board, "xiao-esp32c6")
        self.assertEqual(manifest.image.size_bytes, 712976)
        self.assertFalse(manifest.provisioning_required)

    def test_requires_explicit_ota_provisioning_mode(self) -> None:
        with self.assertRaisesRegex(
            protocol.ProtocolError, "provisioning_required is required"
        ):
            protocol.parse_ota_manifest(
                {
                    "schema": "garden-ota-manifest/v1",
                    "product": "garden-irrigation",
                    "application": "garden-firmware",
                    "board": "xiao-esp32c6",
                    "chip": "esp32c6",
                    "version": "0.1.1",
                    "build_id": "xiao-esp32c6-test",
                    "channel": "stable",
                    "image": {
                        "file": "garden-firmware-xiao-esp32c6.bin",
                        "size_bytes": 712976,
                        "sha256": "0" * 64,
                    },
                    "signature": {
                        "algorithm": "ecdsa-p256-sha256",
                        "format": "raw-r-s-hex",
                        "value": "ab" * 64,
                    },
                }
            )

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

    def test_ota_signed_manifest_message_matches_firmware_order(self) -> None:
        request = protocol.OtaRequest(
            product="garden-irrigation",
            application="garden-firmware",
            board="xiao-esp32c6",
            chip="esp32c6",
            version="0.1.1",
            build_id="xiao-esp32c6-abc123-20260623T120000Z",
            channel="stable",
            host="192.168.1.20",
            port=8000,
            path="/garden.bin",
            size_bytes=712976,
            sha256="4e23fc7f1349beef5b55d33440efca35fccb5ce28db952fd6469ebb84a31ffde",
            challenge="0123456789abcdef0123456789abcdef",
            nonce="20260523T120000",
            signature="aa" * 64,
        )

        message = protocol.ota_signed_manifest_message(request)

        self.assertEqual(
            message,
            "schema=garden-ota-signed-manifest/v1\n"
            "product=garden-irrigation\n"
            "application=garden-firmware\n"
            "board=xiao-esp32c6\n"
            "chip=esp32c6\n"
            "version=0.1.1\n"
            "build_id=xiao-esp32c6-abc123-20260623T120000Z\n"
            "channel=stable\n"
            "size=712976\n"
            "sha256=4e23fc7f1349beef5b55d33440efca35fccb5ce28db952fd6469ebb84a31ffde\n",
        )

    def test_builds_and_redacts_signed_ota_request(self) -> None:
        request = protocol.OtaRequest(
            product="garden-irrigation",
            application="garden-firmware",
            board="xiao-esp32c6",
            chip="esp32c6",
            version="0.1.1",
            build_id="xiao-esp32c6-abc123-20260623T120000Z",
            channel="stable",
            host="192.168.1.20",
            port=8000,
            path="/garden.bin",
            size_bytes=712976,
            sha256="4e23fc7f1349beef5b55d33440efca35fccb5ce28db952fd6469ebb84a31ffde",
            challenge="0123456789abcdef0123456789abcdef",
            nonce="20260523T120000",
            signature="aa" * 64,
        )

        payload = protocol.build_ota_request_payload(request)

        self.assertTrue(payload.endswith(f"signature={'aa' * 64}"))
        self.assertIn("signature=<redacted>", protocol.redact_ota_payload(payload))
        self.assertNotIn("aa" * 64, protocol.redact_ota_payload(payload))


if __name__ == "__main__":
    unittest.main()
