"""Typed MQTT protocol helpers for Garden Irrigation controllers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
import re
from typing import Any, Final

OTA_REQUEST_SCHEMA: Final = "garden-ota-request/v1"
OTA_MANIFEST_SCHEMA: Final = "garden-ota-manifest/v1"
OTA_PRODUCT: Final = "garden-irrigation"
OTA_APPLICATION: Final = "garden-firmware"
CLAIM_INFO_SCHEMA: Final = "garden-irrigation-claim-info/v1"
CLAIM_REQUEST_SCHEMA: Final = "garden-irrigation-claim/v1"
CLAIM_RESULT_SCHEMA: Final = "garden-irrigation-claim-result/v1"
PROVISIONING_SCHEMA: Final = "garden-irrigation-provisioning/v1"

MAX_ZONES: Final = 4
MAX_DURATION_MINUTES: Final = 60
MAX_DURATION_SECONDS: Final = MAX_DURATION_MINUTES * 60
DEFAULT_TOPIC_PREFIX: Final = "garden/irrigation"
IDENTITY_SCHEMA: Final = "garden-irrigation-device/v1"

_TOPIC_PART_RE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_HEX_32_RE: Final = re.compile(r"^[0-9a-fA-F]{64}$")
_ECDSA_P256_SIGNATURE_RE: Final = re.compile(r"^[0-9a-fA-F]{128}$")
_CHALLENGE_RE: Final = re.compile(r"^[0-9a-fA-F]{32}$")
_TOKEN_RE: Final = re.compile(r"^[A-Za-z0-9_.-]{1,48}$")
_BUILD_ID_RE: Final = re.compile(r"^[A-Za-z0-9_.-]{1,96}$")
_HOST_RE: Final = re.compile(r"^[A-Za-z0-9.-]{1,63}$")
_PATH_RE: Final = re.compile(r"^/[A-Za-z0-9/._%:-]{1,95}$")
_FACTORY_ID_RE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{5,63}$")
_PAIRING_CODE_RE: Final = re.compile(r"^[A-Z0-9][A-Z0-9-]{5,31}$")
_SSID_RE: Final = re.compile(r"^[^\x00-\x1f\x7f]{1,32}$")


class ProtocolError(ValueError):
    """Raised when a topic, payload, or manifest violates the public protocol."""


class Availability(StrEnum):
    """Controller availability payload."""

    ONLINE = "online"
    OFFLINE = "offline"


class ZoneState(StrEnum):
    """Zone state payload published by firmware."""

    OFF = "off"
    WATERING = "watering"
    SKIPPED = "skipped"
    FAULT = "fault"


class ClaimTransport(StrEnum):
    """Supported controller claim transports."""

    USB_SERIAL = "usb_serial"
    BLE = "ble"
    SOFTAP = "softap"


class ClaimResultStatus(StrEnum):
    """Provisioning result status from firmware."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    REBOOTING = "rebooting"


@dataclass(frozen=True)
class OtaImage:
    """OTA image metadata from a manifest."""

    file: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class OtaSignature:
    """Validated signature metadata from an OTA manifest."""

    algorithm: str
    format: str
    value: str


@dataclass(frozen=True)
class OtaManifest:
    """Validated Garden OTA manifest."""

    product: str
    application: str
    board: str
    chip: str
    version: str
    build_id: str
    channel: str
    provisioning_required: bool
    image: OtaImage
    signature: OtaSignature


@dataclass(frozen=True)
class NetworkStatus:
    """Validated controller telemetry published on network/status."""

    board: str
    chip: str
    version: str
    build_id: str
    runtime_config_persisted: bool
    phase: str
    reason: str
    reset_reason: str
    mqtt_reconnects: int
    uptime_seconds: int
    free_heap_bytes: int
    min_free_heap_bytes: int
    heap_used_bytes: int
    chip_temperature_celsius: int | None

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-compatible representation for HA attributes."""
        return {
            "board": self.board,
            "chip": self.chip,
            "version": self.version,
            "build_id": self.build_id,
            "runtime_config_persisted": self.runtime_config_persisted,
            "phase": self.phase,
            "reason": self.reason,
            "reset_reason": self.reset_reason,
            "mqtt_reconnects": self.mqtt_reconnects,
            "uptime_seconds": self.uptime_seconds,
            "free_heap_bytes": self.free_heap_bytes,
            "min_free_heap_bytes": self.min_free_heap_bytes,
            "heap_used_bytes": self.heap_used_bytes,
            "chip_temperature_celsius": self.chip_temperature_celsius,
        }


@dataclass(frozen=True)
class OtaRequest:
    """Canonical OTA request fields authenticated for firmware."""

    product: str
    application: str
    board: str
    chip: str
    version: str
    build_id: str
    channel: str
    host: str
    port: int
    path: str
    size_bytes: int
    sha256: str
    challenge: str
    nonce: str
    signature: str


@dataclass(frozen=True)
class DeviceIdentity:
    """Validated controller identity payload."""

    device_id: str
    base_topic: str
    board: str
    chip: str
    firmware_version: str
    firmware_build: str | None
    protocol_schema: str
    capabilities: dict[str, object]


@dataclass(frozen=True)
class ClaimInfo:
    """Validated pairing-mode advertisement from an unclaimed controller."""

    factory_id: str
    board: str
    chip: str
    firmware_version: str
    firmware_build: str | None
    transports: tuple[ClaimTransport, ...]
    expires_in_seconds: int


@dataclass(frozen=True)
class ClaimWifiCredentials:
    """Wi-Fi credentials supplied during device claim."""

    ssid: str
    password: str


@dataclass(frozen=True)
class ClaimMqttCredentials:
    """MQTT runtime credentials supplied during device claim."""

    host: str
    port: int
    username: str
    password: str
    discovery_prefix: str


@dataclass(frozen=True)
class ClaimRequest:
    """Validated claim payload sent from Home Assistant to pairing firmware."""

    factory_id: str
    pairing_code: str
    device_id: str
    base_topic: str
    mqtt_client_id: str
    wifi: ClaimWifiCredentials
    mqtt: ClaimMqttCredentials
    nonce: str


@dataclass(frozen=True)
class ClaimResult:
    """Validated claim result returned by firmware."""

    factory_id: str
    status: ClaimResultStatus
    device_id: str | None
    base_topic: str | None
    reason: str | None


def normalize_device_id(value: str) -> str:
    """Validate and normalize a user-facing controller device ID."""
    device_id = value.strip().strip("/")
    if not _TOPIC_PART_RE.fullmatch(device_id):
        raise ProtocolError("device ID contains invalid characters")
    if "/" in device_id:
        raise ProtocolError("device ID cannot contain slashes")
    return device_id


def base_topic_from_device_id(device_id: str) -> str:
    """Build the default Garden MQTT base topic for a device ID."""
    return f"{DEFAULT_TOPIC_PREFIX}/{normalize_device_id(device_id)}"


def normalize_base_topic(value: str) -> str:
    """Validate and normalize a controller MQTT base topic."""
    topic = value.strip().strip("/")
    if not topic:
        raise ProtocolError("base topic is required")
    if "+" in topic or "#" in topic:
        raise ProtocolError("base topic cannot contain MQTT wildcards")
    parts = topic.split("/")
    if any(not _TOPIC_PART_RE.fullmatch(part) for part in parts):
        raise ProtocolError("base topic contains an invalid segment")
    return topic


def identity_topic(device_id: str) -> str:
    """Return the retained identity topic for one controller."""
    return f"{DEFAULT_TOPIC_PREFIX}/discovery/{normalize_device_id(device_id)}"


def runtime_identity_topic(base_topic: str) -> str:
    """Return the retained runtime identity topic for one controller."""
    return topic(base_topic, "identity")


def parse_identity_payload(payload: dict[str, object]) -> DeviceIdentity:
    """Validate and parse a controller identity payload."""
    if payload.get("schema") != IDENTITY_SCHEMA:
        raise ProtocolError("unsupported identity schema")

    device_id = normalize_device_id(_required_str(payload, "device_id"))
    base_topic = normalize_base_topic(_required_str(payload, "base_topic"))
    capabilities = payload.get("capabilities")
    if capabilities is not None and not isinstance(capabilities, dict):
        raise ProtocolError("identity capabilities must be an object")

    return DeviceIdentity(
        device_id=device_id,
        base_topic=base_topic,
        board=_required_str(payload, "board"),
        chip=_required_str(payload, "chip"),
        firmware_version=_required_str(payload, "firmware_version"),
        firmware_build=payload.get("firmware_build")
        if isinstance(payload.get("firmware_build"), str)
        else None,
        protocol_schema=_required_str(payload, "protocol_schema"),
        capabilities=capabilities or {},
    )


def parse_claim_info_payload(payload: dict[str, object]) -> ClaimInfo:
    """Validate and parse pairing-mode claim info from firmware."""
    if payload.get("schema") != CLAIM_INFO_SCHEMA:
        raise ProtocolError("unsupported claim info schema")

    transports_payload = payload.get("transports")
    if not isinstance(transports_payload, list) or not transports_payload:
        raise ProtocolError("claim transports must be a non-empty list")

    transports: list[ClaimTransport] = []
    for item in transports_payload:
        if not isinstance(item, str):
            raise ProtocolError("claim transport must be a string")
        try:
            transports.append(ClaimTransport(item))
        except ValueError as exc:
            raise ProtocolError("unsupported claim transport") from exc

    expires_in_seconds = _required_int(payload, "expires_in_seconds")
    if not 30 <= expires_in_seconds <= 900:
        raise ProtocolError("claim expiry must be between 30 and 900 seconds")

    firmware_build = payload.get("firmware_build")
    return ClaimInfo(
        factory_id=validate_factory_id(_required_str(payload, "factory_id")),
        board=_required_str(payload, "board"),
        chip=_required_str(payload, "chip"),
        firmware_version=_required_str(payload, "firmware_version"),
        firmware_build=firmware_build if isinstance(firmware_build, str) else None,
        transports=tuple(transports),
        expires_in_seconds=expires_in_seconds,
    )


def parse_claim_request_payload(payload: dict[str, object]) -> ClaimRequest:
    """Validate and parse a Home Assistant assisted claim request."""
    if payload.get("schema") != CLAIM_REQUEST_SCHEMA:
        raise ProtocolError("unsupported claim request schema")

    wifi_payload = payload.get("wifi")
    mqtt_payload = payload.get("mqtt")
    if not isinstance(wifi_payload, dict):
        raise ProtocolError("claim Wi-Fi credentials are required")
    if not isinstance(mqtt_payload, dict):
        raise ProtocolError("claim MQTT credentials are required")

    device_id = normalize_device_id(_required_str(payload, "device_id"))
    base_topic = normalize_base_topic(_required_str(payload, "base_topic"))
    mqtt_client_id = validate_mqtt_client_id(_required_str(payload, "mqtt_client_id"))
    if base_topic != base_topic_from_device_id(device_id):
        raise ProtocolError("claim base topic must match device ID")

    return ClaimRequest(
        factory_id=validate_factory_id(_required_str(payload, "factory_id")),
        pairing_code=validate_pairing_code(_required_str(payload, "pairing_code")),
        device_id=device_id,
        base_topic=base_topic,
        mqtt_client_id=mqtt_client_id,
        wifi=ClaimWifiCredentials(
            ssid=validate_wifi_ssid(_required_str(wifi_payload, "ssid")),
            password=validate_wifi_password(_required_str(wifi_payload, "password")),
        ),
        mqtt=ClaimMqttCredentials(
            host=validate_host(_required_str(mqtt_payload, "host")),
            port=validate_port(_required_int(mqtt_payload, "port")),
            username=validate_mqtt_username(_required_str(mqtt_payload, "username")),
            password=validate_mqtt_password(_required_str(mqtt_payload, "password")),
            discovery_prefix=normalize_base_topic(
                _required_str(mqtt_payload, "discovery_prefix")
            ),
        ),
        nonce=validate_claim_nonce(_required_str(payload, "nonce")),
    )


def parse_claim_result_payload(payload: dict[str, object]) -> ClaimResult:
    """Validate and parse firmware's response to a claim request."""
    if payload.get("schema") != CLAIM_RESULT_SCHEMA:
        raise ProtocolError("unsupported claim result schema")

    try:
        status = ClaimResultStatus(_required_str(payload, "status"))
    except ValueError as exc:
        raise ProtocolError("unsupported claim result status") from exc

    device_id_payload = payload.get("device_id")
    base_topic_payload = payload.get("base_topic")
    device_id = (
        normalize_device_id(device_id_payload) if isinstance(device_id_payload, str) else None
    )
    base_topic = (
        normalize_base_topic(base_topic_payload)
        if isinstance(base_topic_payload, str)
        else None
    )
    if status in {ClaimResultStatus.ACCEPTED, ClaimResultStatus.REBOOTING}:
        if device_id is None or base_topic is None:
            raise ProtocolError("accepted claim result must include identity")
        if base_topic != base_topic_from_device_id(device_id):
            raise ProtocolError("claim result base topic must match device ID")

    reason = payload.get("reason")
    return ClaimResult(
        factory_id=validate_factory_id(_required_str(payload, "factory_id")),
        status=status,
        device_id=device_id,
        base_topic=base_topic,
        reason=reason if isinstance(reason, str) else None,
    )


def build_claim_request_payload(request: ClaimRequest) -> dict[str, object]:
    """Build a JSON-serializable claim request payload."""
    return {
        "schema": CLAIM_REQUEST_SCHEMA,
        "factory_id": validate_factory_id(request.factory_id),
        "pairing_code": validate_pairing_code(request.pairing_code),
        "device_id": normalize_device_id(request.device_id),
        "base_topic": normalize_base_topic(request.base_topic),
        "mqtt_client_id": validate_mqtt_client_id(request.mqtt_client_id),
        "wifi": {
            "ssid": validate_wifi_ssid(request.wifi.ssid),
            "password": validate_wifi_password(request.wifi.password),
        },
        "mqtt": {
            "host": validate_host(request.mqtt.host),
            "port": validate_port(request.mqtt.port),
            "username": validate_mqtt_username(request.mqtt.username),
            "password": validate_mqtt_password(request.mqtt.password),
            "discovery_prefix": normalize_base_topic(request.mqtt.discovery_prefix),
        },
        "nonce": validate_claim_nonce(request.nonce),
    }


def redact_claim_payload(payload: dict[str, object]) -> dict[str, object]:
    """Redact claim payload secrets before diagnostics or logs."""
    redacted = dict(payload)
    wifi = redacted.get("wifi")
    if isinstance(wifi, dict):
        redacted["wifi"] = {**wifi, "password": "<redacted>"}
    mqtt = redacted.get("mqtt")
    if isinstance(mqtt, dict):
        redacted["mqtt"] = {**mqtt, "password": "<redacted>"}
    if "pairing_code" in redacted:
        redacted["pairing_code"] = "<redacted>"
    return redacted


def validate_factory_id(value: str) -> str:
    """Validate a factory-assigned device identity."""
    factory_id = value.strip()
    if not _FACTORY_ID_RE.fullmatch(factory_id):
        raise ProtocolError("invalid factory ID")
    return factory_id


def validate_pairing_code(value: str) -> str:
    """Validate a proof-of-possession pairing code."""
    pairing_code = value.strip().upper()
    if not _PAIRING_CODE_RE.fullmatch(pairing_code):
        raise ProtocolError("invalid pairing code")
    return pairing_code


def validate_mqtt_client_id(value: str) -> str:
    """Validate a client ID used only for the MQTT session."""
    return normalize_device_id(value)


def validate_wifi_ssid(value: str) -> str:
    """Validate a Wi-Fi SSID for provisioning."""
    ssid = value.strip()
    if not _SSID_RE.fullmatch(ssid):
        raise ProtocolError("invalid Wi-Fi SSID")
    return ssid


def validate_wifi_password(value: str) -> str:
    """Validate a WPA/WPA2 personal Wi-Fi password."""
    password = value.strip()
    if not 8 <= len(password) <= 63:
        raise ProtocolError("Wi-Fi password must be 8 to 63 characters")
    if any(ord(char) < 32 or ord(char) == 127 for char in password):
        raise ProtocolError("Wi-Fi password contains invalid control characters")
    return password


def validate_host(value: str) -> str:
    """Validate a local broker host name or IPv4-like address."""
    host = value.strip()
    if not host or len(host) > 253:
        raise ProtocolError("invalid host")
    labels = host.split(".")
    if any(not _HOST_RE.fullmatch(label) for label in labels):
        raise ProtocolError("invalid host")
    return host


def validate_port(value: int) -> int:
    """Validate a TCP port."""
    if not 1 <= value <= 65535:
        raise ProtocolError("invalid port")
    return value


def validate_mqtt_username(value: str) -> str:
    """Validate a provisioned MQTT username."""
    username = value.strip()
    if not 1 <= len(username) <= 128:
        raise ProtocolError("invalid MQTT username")
    if any(ord(char) < 32 or ord(char) == 127 for char in username):
        raise ProtocolError("MQTT username contains invalid control characters")
    return username


def validate_mqtt_password(value: str) -> str:
    """Validate a provisioned MQTT password."""
    password = value.strip()
    if not 1 <= len(password) <= 256:
        raise ProtocolError("invalid MQTT password")
    if any(ord(char) < 32 or ord(char) == 127 for char in password):
        raise ProtocolError("MQTT password contains invalid control characters")
    return password


def validate_claim_nonce(value: str) -> str:
    """Validate a short anti-replay nonce for a claim request."""
    nonce = value.strip()
    if not _TOKEN_RE.fullmatch(nonce):
        raise ProtocolError("invalid claim nonce")
    return nonce


def validate_zone(zone: int) -> int:
    """Validate a public zone index."""
    if not 0 <= zone < MAX_ZONES:
        raise ProtocolError(f"zone must be between 0 and {MAX_ZONES - 1}")
    return zone


def topic(base_topic: str, suffix: str) -> str:
    """Build a device topic from a validated base topic and suffix."""
    base = normalize_base_topic(base_topic)
    clean_suffix = suffix.strip("/")
    if not clean_suffix:
        raise ProtocolError("topic suffix is required")
    return f"{base}/{clean_suffix}"


def availability_topic(base_topic: str) -> str:
    """Return the controller availability topic."""
    return topic(base_topic, "availability")


def state_topic(base_topic: str) -> str:
    """Return the controller state topic."""
    return topic(base_topic, "state")


def diagnostics_topic(base_topic: str) -> str:
    """Return the controller diagnostics topic."""
    return topic(base_topic, "diagnostics")


def network_status_topic(base_topic: str) -> str:
    """Return the controller network status topic."""
    return topic(base_topic, "network/status")


def wifi_signal_topic(base_topic: str) -> str:
    """Return the controller Wi-Fi RSSI topic."""
    return topic(base_topic, "wifi/rssi")


def command_topic(base_topic: str) -> str:
    """Return the controller command topic."""
    return topic(base_topic, "command")


def ota_challenge_topic(base_topic: str) -> str:
    """Return the controller OTA challenge topic."""
    return topic(base_topic, "ota/challenge")


def ota_request_topic(base_topic: str) -> str:
    """Return the controller OTA request topic."""
    return topic(base_topic, "ota/request")


def ota_confirm_topic(base_topic: str) -> str:
    """Return the controller OTA confirmation topic."""
    return topic(base_topic, "ota/confirm")


def zone_state_topic(base_topic: str, zone: int) -> str:
    """Return a zone state topic."""
    return topic(base_topic, f"zone/{validate_zone(zone)}/state")


def zone_command_topic(base_topic: str, zone: int) -> str:
    """Return a zone command topic."""
    return topic(base_topic, f"zone/{validate_zone(zone)}/command")


def zone_duration_state_topic(base_topic: str, zone: int) -> str:
    """Return a zone duration state topic."""
    return topic(base_topic, f"zone/{validate_zone(zone)}/duration_minutes")


def zone_duration_command_topic(base_topic: str, zone: int) -> str:
    """Return a zone duration command topic."""
    return topic(base_topic, f"zone/{validate_zone(zone)}/duration_minutes/set")


def zone_run_seconds_topic(base_topic: str, zone: int) -> str:
    """Return a zone runtime counter topic."""
    return topic(base_topic, f"zone/{validate_zone(zone)}/run_seconds")


def parse_availability(payload: str) -> Availability:
    """Parse a controller availability payload."""
    try:
        return Availability(payload.strip())
    except ValueError as exc:
        raise ProtocolError("invalid availability payload") from exc


def parse_ota_challenge(payload: str) -> str:
    """Validate a retained OTA challenge published by firmware."""
    challenge = payload.strip().lower()
    if not _CHALLENGE_RE.fullmatch(challenge):
        raise ProtocolError("invalid OTA challenge")
    return challenge


def parse_zone_state(payload: str) -> ZoneState:
    """Parse a zone state payload."""
    try:
        return ZoneState(payload.strip())
    except ValueError as exc:
        raise ProtocolError("invalid zone state payload") from exc


def parse_duration_minutes(payload: str) -> int:
    """Parse a duration in whole minutes."""
    value = _parse_positive_int(payload.strip().removesuffix(".0").removesuffix(".00"))
    return validate_duration_minutes(value)


def validate_duration_minutes(minutes: int) -> int:
    """Validate a public irrigation duration in whole minutes."""
    if not 1 <= minutes <= MAX_DURATION_MINUTES:
        raise ProtocolError(f"minutes must be between 1 and {MAX_DURATION_MINUTES}")
    return minutes


def parse_run_seconds(payload: str) -> int:
    """Parse a zone runtime counter."""
    return _parse_non_negative_int(payload.strip())


def parse_wifi_rssi(payload: str) -> int:
    """Parse Wi-Fi RSSI in dBm."""
    value = payload.strip()
    if not value.removeprefix("-").isdecimal():
        raise ProtocolError("wifi RSSI must be an integer")
    rssi = int(value)
    if not -127 <= rssi <= 0:
        raise ProtocolError("wifi RSSI is outside plausible dBm range")
    return rssi


def parse_network_status(payload: str) -> NetworkStatus:
    """Parse the firmware network status JSON payload."""
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ProtocolError("network status must be JSON") from exc
    if not isinstance(parsed, dict):
        raise ProtocolError("network status must be an object")

    return NetworkStatus(
        board=_required_str(parsed, "board"),
        chip=_required_str(parsed, "chip"),
        version=_required_str(parsed, "version"),
        build_id=_required_str(parsed, "build_id"),
        runtime_config_persisted=_required_bool(parsed, "runtime_config_persisted"),
        phase=_required_str(parsed, "phase"),
        reason=_required_str(parsed, "reason"),
        reset_reason=_required_str(parsed, "reset_reason"),
        mqtt_reconnects=_required_non_negative_int(parsed, "mqtt_reconnects"),
        uptime_seconds=_required_non_negative_int(parsed, "uptime_seconds"),
        free_heap_bytes=_required_non_negative_int(parsed, "free_heap_bytes"),
        min_free_heap_bytes=_required_non_negative_int(parsed, "min_free_heap_bytes"),
        heap_used_bytes=_required_non_negative_int(parsed, "heap_used_bytes"),
        chip_temperature_celsius=_optional_int(parsed, "chip_temperature_celsius"),
    )


def wifi_quality_percent(rssi: int) -> int:
    """Map RSSI dBm to a bounded user-facing quality percentage."""
    clamped = min(max(rssi, -90), -50)
    return round((clamped + 90) * 2.5)


def wifi_status_label(rssi: int) -> str:
    """Return a human-readable Wi-Fi quality label."""
    if rssi >= -60:
        return "excellent"
    if rssi >= -67:
        return "good"
    if rssi >= -75:
        return "fair"
    return "weak"


def start_zone_publish(
    base_topic: str, zone: int, duration_seconds: int
) -> tuple[str, str, int, bool]:
    """Build a safe non-retained start command publish tuple.

    The tuple shape is `(topic, payload, qos, retain)`.
    """
    if not 1 <= duration_seconds <= MAX_DURATION_SECONDS:
        raise ProtocolError(
            f"duration_seconds must be between 1 and {MAX_DURATION_SECONDS}"
        )
    return (zone_command_topic(base_topic, zone), f"ON:{duration_seconds}", 0, False)


def stop_zone_publish(base_topic: str, zone: int) -> tuple[str, str, int, bool]:
    """Build a safe non-retained stop-zone command publish tuple."""
    return (zone_command_topic(base_topic, zone), "STOP", 0, False)


def stop_all_publish(base_topic: str) -> tuple[str, str, int, bool]:
    """Build a safe non-retained stop-all command publish tuple."""
    return (command_topic(base_topic), "STOP_ALL", 0, False)


def set_duration_publish(
    base_topic: str, zone: int, minutes: int
) -> tuple[str, str, int, bool]:
    """Build a safe non-retained duration update publish tuple."""
    return (
        zone_duration_command_topic(base_topic, zone),
        str(validate_duration_minutes(minutes)),
        0,
        False,
    )


def parse_ota_manifest(payload: dict[str, object]) -> OtaManifest:
    """Validate and parse an OTA manifest dictionary."""
    if payload.get("schema") != OTA_MANIFEST_SCHEMA:
        raise ProtocolError("unsupported OTA manifest schema")
    if payload.get("product") != OTA_PRODUCT:
        raise ProtocolError("OTA manifest product mismatch")
    if payload.get("application") != OTA_APPLICATION:
        raise ProtocolError("OTA manifest application mismatch")

    image_payload = payload.get("image")
    signature_payload = payload.get("signature")
    if not isinstance(image_payload, dict):
        raise ProtocolError("OTA manifest image is required")
    if not isinstance(signature_payload, dict):
        raise ProtocolError("OTA manifest signature is required")

    board = _required_str(payload, "board")
    chip = _required_str(payload, "chip")
    version = _required_str(payload, "version")
    build_id = _required_str(payload, "build_id")
    channel = _required_str(payload, "channel")
    provisioning_required = _required_bool(payload, "provisioning_required")
    image_file = _required_str(image_payload, "file")
    sha256 = _required_str(image_payload, "sha256").lower()
    size_bytes = _required_int(image_payload, "size_bytes")
    signature_algorithm = _required_str(signature_payload, "algorithm")
    signature_format = _required_str(signature_payload, "format")
    signature_value = _required_str(signature_payload, "value").lower()

    if not _TOPIC_PART_RE.fullmatch(board):
        raise ProtocolError("invalid OTA board")
    if not _TOPIC_PART_RE.fullmatch(chip):
        raise ProtocolError("invalid OTA chip")
    if not image_file.endswith(".bin") or "/" in image_file:
        raise ProtocolError("OTA image file must be a local .bin filename")
    if size_bytes <= 0:
        raise ProtocolError("OTA image size must be positive")
    if not _HEX_32_RE.fullmatch(sha256):
        raise ProtocolError("OTA image sha256 must be 64 hex characters")
    if not _BUILD_ID_RE.fullmatch(build_id):
        raise ProtocolError("invalid OTA build_id")
    if channel not in {"stable", "beta"}:
        raise ProtocolError("invalid OTA channel")
    if signature_algorithm != "ecdsa-p256-sha256":
        raise ProtocolError("unsupported OTA signature algorithm")
    if signature_format != "raw-r-s-hex":
        raise ProtocolError("unsupported OTA signature format")
    if not _ECDSA_P256_SIGNATURE_RE.fullmatch(signature_value):
        raise ProtocolError("OTA signature must be 128 hex characters")

    return OtaManifest(
        product=OTA_PRODUCT,
        application=OTA_APPLICATION,
        board=board,
        chip=chip,
        version=version,
        build_id=build_id,
        channel=channel,
        provisioning_required=provisioning_required,
        image=OtaImage(file=image_file, size_bytes=size_bytes, sha256=sha256),
        signature=OtaSignature(
            algorithm=signature_algorithm,
            format=signature_format,
            value=signature_value,
        ),
    )


def ota_signed_manifest_message(request: OtaRequest) -> str:
    """Return the canonical signed manifest message used by firmware."""
    _validate_ota_request(request)
    fields = (
        ("schema", "garden-ota-signed-manifest/v1"),
        ("product", request.product),
        ("application", request.application),
        ("board", request.board),
        ("chip", request.chip),
        ("version", request.version),
        ("build_id", request.build_id),
        ("channel", request.channel),
        ("size", str(request.size_bytes)),
        ("sha256", request.sha256.lower()),
    )
    return "".join(f"{key}={value}\n" for key, value in fields)


def build_ota_request_payload(request: OtaRequest) -> str:
    """Build a signed OTA request payload for MQTT."""
    _validate_ota_request(request)
    fields = (
        ("schema", OTA_REQUEST_SCHEMA),
        ("product", request.product),
        ("application", request.application),
        ("board", request.board),
        ("chip", request.chip),
        ("version", request.version),
        ("build_id", request.build_id),
        ("channel", request.channel),
        ("host", request.host),
        ("port", str(request.port)),
        ("path", request.path),
        ("size", str(request.size_bytes)),
        ("sha256", request.sha256.lower()),
        ("challenge", request.challenge.lower()),
        ("nonce", request.nonce),
        ("signature", request.signature.lower()),
    )
    return ";".join(f"{key}={value}" for key, value in fields)


def redact_ota_payload(payload: str) -> str:
    """Redact the authenticator from an OTA request before logging."""
    return re.sub(r"signature=[0-9a-fA-F]{128}", "signature=<redacted>", payload)


def _parse_positive_int(value: str) -> int:
    parsed = _parse_non_negative_int(value)
    if parsed == 0:
        raise ProtocolError("value must be positive")
    return parsed


def _parse_non_negative_int(value: str) -> int:
    if not value or not value.isdecimal():
        raise ProtocolError("value must be an integer")
    return int(value)


def _required_str(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ProtocolError(f"{key} is required")
    return value


def _required_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProtocolError(f"{key} is required")
    return value


def _required_bool(payload: dict[str, object], key: str) -> bool:
    """Return one required boolean without accepting integer coercion."""
    value = payload.get(key)
    if not isinstance(value, bool):
        raise ProtocolError(f"{key} is required")
    return value


def _required_non_negative_int(payload: dict[str, object], key: str) -> int:
    value = _required_int(payload, key)
    if value < 0:
        raise ProtocolError(f"{key} must be non-negative")
    return value


def _optional_int(payload: dict[str, object], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProtocolError(f"{key} must be an integer or null")
    return value


def _validate_ota_request(request: OtaRequest) -> None:
    if request.product != OTA_PRODUCT:
        raise ProtocolError("OTA request product mismatch")
    if request.application != OTA_APPLICATION:
        raise ProtocolError("OTA request application mismatch")
    if not _TOPIC_PART_RE.fullmatch(request.board):
        raise ProtocolError("invalid OTA request board")
    if not _TOPIC_PART_RE.fullmatch(request.chip):
        raise ProtocolError("invalid OTA request chip")
    if not _BUILD_ID_RE.fullmatch(request.build_id):
        raise ProtocolError("invalid OTA request build_id")
    if request.channel not in {"stable", "beta"}:
        raise ProtocolError("invalid OTA request channel")
    if not _HOST_RE.fullmatch(request.host):
        raise ProtocolError("invalid OTA request host")
    if not 1 <= request.port <= 65535:
        raise ProtocolError("invalid OTA request port")
    if not _PATH_RE.fullmatch(request.path):
        raise ProtocolError("invalid OTA request path")
    if request.size_bytes <= 0:
        raise ProtocolError("invalid OTA request size")
    if not _HEX_32_RE.fullmatch(request.sha256):
        raise ProtocolError("invalid OTA request sha256")
    if not _CHALLENGE_RE.fullmatch(request.challenge):
        raise ProtocolError("invalid OTA challenge")
    if not _TOKEN_RE.fullmatch(request.nonce):
        raise ProtocolError("invalid OTA request nonce")
    if not _ECDSA_P256_SIGNATURE_RE.fullmatch(request.signature):
        raise ProtocolError("invalid OTA request signature")
