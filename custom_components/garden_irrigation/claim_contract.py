"""Pure helpers for the HA-assisted claim contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .protocol import (
    ClaimMqttCredentials,
    ClaimRequest,
    ClaimWifiCredentials,
    ProtocolError,
    base_topic_from_device_id,
    build_claim_request_payload,
    parse_claim_request_payload,
    redact_claim_payload,
    validate_claim_nonce,
    validate_factory_id,
    validate_mqtt_client_id,
    validate_pairing_code,
)

SOFTAP_CLAIM_URL = "http://192.168.4.1/claim"


@dataclass(frozen=True)
class ClaimInput:
    """User input required to claim a fresh or factory-reset controller."""

    factory_id: str
    pairing_code: str
    device_id: str
    wifi_ssid: str
    wifi_password: str
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str
    mqtt_password: str
    discovery_prefix: str = "homeassistant"
    nonce: str = "claim"


def build_claim_request(input_data: ClaimInput) -> ClaimRequest:
    """Build a validated claim request from user input."""
    device_id = validate_mqtt_client_id(input_data.device_id)
    base_topic = base_topic_from_device_id(device_id)
    payload = {
        "schema": "garden-irrigation-claim/v1",
        "factory_id": validate_factory_id(input_data.factory_id),
        "pairing_code": validate_pairing_code(input_data.pairing_code),
        "device_id": device_id,
        "base_topic": base_topic,
        "mqtt_client_id": validate_mqtt_client_id(device_id),
        "wifi": {
            "ssid": input_data.wifi_ssid,
            "password": input_data.wifi_password,
        },
        "mqtt": {
            "host": input_data.mqtt_host,
            "port": input_data.mqtt_port,
            "username": input_data.mqtt_username,
            "password": input_data.mqtt_password,
            "discovery_prefix": input_data.discovery_prefix,
        },
        "nonce": validate_claim_nonce(input_data.nonce),
    }
    return parse_claim_request_payload(payload)


def claim_request_from_mapping(payload: Mapping[str, object]) -> ClaimRequest:
    """Build a validated claim request from a flat form-like mapping."""
    try:
        mqtt_port_raw = payload["mqtt_port"]
        mqtt_port = (
            mqtt_port_raw
            if isinstance(mqtt_port_raw, int)
            else int(str(mqtt_port_raw).strip())
        )
        return build_claim_request(
            ClaimInput(
                factory_id=str(payload["factory_id"]),
                pairing_code=str(payload["pairing_code"]),
                device_id=str(payload["device_id"]),
                wifi_ssid=str(payload["wifi_ssid"]),
                wifi_password=str(payload["wifi_password"]),
                mqtt_host=str(payload["mqtt_host"]),
                mqtt_port=mqtt_port,
                mqtt_username=str(payload["mqtt_username"]),
                mqtt_password=str(payload["mqtt_password"]),
                discovery_prefix=str(payload.get("discovery_prefix", "homeassistant")),
                nonce=str(payload.get("nonce", "claim")),
            )
        )
    except (KeyError, ValueError) as exc:
        raise ProtocolError("invalid claim input") from exc


def claim_request_json_payload(request: ClaimRequest) -> dict[str, object]:
    """Return the canonical JSON-compatible claim payload."""
    return build_claim_request_payload(request)


def redacted_claim_request_json_payload(request: ClaimRequest) -> dict[str, object]:
    """Return a redacted JSON-compatible claim payload for diagnostics."""
    return redact_claim_payload(claim_request_json_payload(request))


def softap_form_payload(request: ClaimRequest) -> dict[str, str]:
    """Return form fields accepted by the firmware SoftAP claim portal."""
    return {
        "factory_id": request.factory_id,
        "pairing_code": request.pairing_code,
        "device_id": request.device_id,
        "wifi_ssid": request.wifi.ssid,
        "wifi_password": request.wifi.password,
        "mqtt_host": request.mqtt.host,
        "mqtt_port": str(request.mqtt.port),
        "mqtt_username": request.mqtt.username,
        "mqtt_password": request.mqtt.password,
        "discovery_prefix": request.mqtt.discovery_prefix,
    }


def redacted_softap_form_payload(request: ClaimRequest) -> dict[str, str]:
    """Return redacted SoftAP form fields for diagnostics."""
    payload = softap_form_payload(request)
    return {
        **payload,
        "pairing_code": "<redacted>",
        "wifi_password": "<redacted>",
        "mqtt_password": "<redacted>",
    }
