"""Tests for Garden Irrigation HA-assisted claim contract helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest

_ROOT = Path(__file__).resolve().parents[1]
_COMPONENT_PATH = _ROOT / "custom_components" / "garden_irrigation"

_PACKAGE = types.ModuleType("garden_irrigation_claimpkg")
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
    "garden_irrigation_claimpkg.protocol",
    _COMPONENT_PATH / "protocol.py",
)
claim_contract = _load_module(
    "garden_irrigation_claimpkg.claim_contract",
    _COMPONENT_PATH / "claim_contract.py",
)


class GardenIrrigationClaimContractTest(unittest.TestCase):
    """Claim contract tests without Home Assistant runtime imports."""

    def _claim_input(self) -> object:
        return claim_contract.ClaimInput(
            factory_id="gi-c6-01HZX7M2P9F6T2Q1MZ4K8C3A",
            pairing_code="7K4P-92QX",
            device_id="garden-irrigation-a1b2c3",
            wifi_ssid="Home-IoT",
            wifi_password="wifi-password",
            mqtt_host="homeassistant.local",
            mqtt_port=1883,
            mqtt_username="garden-irrigation",
            mqtt_password="mqtt-password",
            nonce="claim-20260615-120000",
        )

    def test_builds_canonical_claim_request(self) -> None:
        request = claim_contract.build_claim_request(self._claim_input())

        self.assertEqual(request.device_id, "garden-irrigation-a1b2c3")
        self.assertEqual(
            request.base_topic,
            "garden/irrigation/garden-irrigation-a1b2c3",
        )
        self.assertEqual(request.mqtt_client_id, "garden-irrigation-a1b2c3")

    def test_builds_softap_form_payload(self) -> None:
        request = claim_contract.build_claim_request(self._claim_input())
        payload = claim_contract.softap_form_payload(request)

        self.assertEqual(claim_contract.SOFTAP_CLAIM_URL, "http://192.168.4.1/claim")
        self.assertEqual(payload["factory_id"], request.factory_id)
        self.assertEqual(payload["device_id"], request.device_id)
        self.assertEqual(payload["wifi_ssid"], "Home-IoT")
        self.assertEqual(payload["mqtt_port"], "1883")
        self.assertNotIn("base_topic", payload)

    def test_redacts_claim_secrets(self) -> None:
        request = claim_contract.build_claim_request(self._claim_input())
        json_payload = claim_contract.redacted_claim_request_json_payload(request)
        form_payload = claim_contract.redacted_softap_form_payload(request)

        self.assertEqual(json_payload["pairing_code"], "<redacted>")
        self.assertEqual(json_payload["wifi"]["password"], "<redacted>")
        self.assertEqual(json_payload["mqtt"]["password"], "<redacted>")
        self.assertEqual(form_payload["pairing_code"], "<redacted>")
        self.assertEqual(form_payload["wifi_password"], "<redacted>")
        self.assertEqual(form_payload["mqtt_password"], "<redacted>")

    def test_rejects_invalid_flat_claim_input(self) -> None:
        with self.assertRaises(protocol.ProtocolError):
            claim_contract.claim_request_from_mapping({"factory_id": "bad"})


if __name__ == "__main__":
    unittest.main()
