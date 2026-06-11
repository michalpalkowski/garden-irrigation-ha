"""Typed MQTT protocol helpers for Garden Irrigation controllers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import hmac
import re
from typing import Final

OTA_REQUEST_SCHEMA: Final = "garden-ota-request/v1"
OTA_MANIFEST_SCHEMA: Final = "garden-ota-manifest/v1"
OTA_PRODUCT: Final = "garden-irrigation"
OTA_APPLICATION: Final = "garden-firmware"

MAX_ZONES: Final = 4
MAX_DURATION_MINUTES: Final = 60
MAX_DURATION_SECONDS: Final = MAX_DURATION_MINUTES * 60
DEFAULT_TOPIC_PREFIX: Final = "garden/irrigation"
IDENTITY_SCHEMA: Final = "garden-irrigation-device/v1"

_TOPIC_PART_RE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_HEX_32_RE: Final = re.compile(r"^[0-9a-fA-F]{64}$")
_CHALLENGE_RE: Final = re.compile(r"^[0-9a-fA-F]{32}$")
_TOKEN_RE: Final = re.compile(r"^[A-Za-z0-9_.-]{1,48}$")
_HOST_RE: Final = re.compile(r"^[A-Za-z0-9.-]{1,63}$")
_PATH_RE: Final = re.compile(r"^/[A-Za-z0-9/._%:-]{1,95}$")


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


@dataclass(frozen=True)
class OtaImage:
    """OTA image metadata from a manifest."""

    file: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class OtaManifest:
    """Validated Garden OTA manifest."""

    product: str
    application: str
    board: str
    chip: str
    version: str
    image: OtaImage


@dataclass(frozen=True)
class OtaRequest:
    """Canonical OTA request fields signed for firmware."""

    product: str
    application: str
    board: str
    chip: str
    version: str
    host: str
    port: int
    path: str
    size_bytes: int
    sha256: str
    challenge: str
    nonce: str


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


def parse_identity_payload(payload: dict[str, object]) -> DeviceIdentity:
    """Validate and parse a controller identity payload."""
    if payload.get("schema") != IDENTITY_SCHEMA:
        raise ProtocolError("unsupported identity schema")

    device_id = normalize_device_id(_required_str(payload, "device_id"))
    base_topic = normalize_base_topic(_required_str(payload, "base_topic"))
    expected_base_topic = base_topic_from_device_id(device_id)
    if base_topic != expected_base_topic:
        raise ProtocolError("identity base topic does not match device ID")

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
    )


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


def command_topic(base_topic: str) -> str:
    """Return the controller command topic."""
    return topic(base_topic, "command")


def ota_challenge_topic(base_topic: str) -> str:
    """Return the controller OTA challenge topic."""
    return topic(base_topic, "ota/challenge")


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


def parse_zone_state(payload: str) -> ZoneState:
    """Parse a zone state payload."""
    try:
        return ZoneState(payload.strip())
    except ValueError as exc:
        raise ProtocolError("invalid zone state payload") from exc


def parse_duration_minutes(payload: str) -> int:
    """Parse a firmware duration in whole minutes."""
    value = _parse_positive_int(payload.strip().removesuffix(".0").removesuffix(".00"))
    if value > MAX_DURATION_MINUTES:
        raise ProtocolError(f"duration cannot exceed {MAX_DURATION_MINUTES} minutes")
    return value


def parse_run_seconds(payload: str) -> int:
    """Parse a zone runtime counter."""
    return _parse_non_negative_int(payload.strip())


def start_zone_publish(base_topic: str, zone: int, duration_seconds: int) -> tuple[str, str, int, bool]:
    """Build a safe non-retained start command publish tuple.

    The tuple shape is `(topic, payload, qos, retain)`.
    """
    if not 1 <= duration_seconds <= MAX_DURATION_SECONDS:
        raise ProtocolError(f"duration_seconds must be between 1 and {MAX_DURATION_SECONDS}")
    return (zone_command_topic(base_topic, zone), f"ON:{duration_seconds}", 0, False)


def stop_zone_publish(base_topic: str, zone: int) -> tuple[str, str, int, bool]:
    """Build a safe non-retained stop-zone command publish tuple."""
    return (zone_command_topic(base_topic, zone), "STOP", 0, False)


def stop_all_publish(base_topic: str) -> tuple[str, str, int, bool]:
    """Build a safe non-retained stop-all command publish tuple."""
    return (command_topic(base_topic), "STOP_ALL", 0, False)


def set_duration_publish(base_topic: str, zone: int, minutes: int) -> tuple[str, str, int, bool]:
    """Build a safe non-retained duration update publish tuple."""
    if not 1 <= minutes <= MAX_DURATION_MINUTES:
        raise ProtocolError(f"minutes must be between 1 and {MAX_DURATION_MINUTES}")
    return (zone_duration_command_topic(base_topic, zone), str(minutes), 0, False)


def parse_ota_manifest(payload: dict[str, object]) -> OtaManifest:
    """Validate and parse an OTA manifest dictionary."""
    if payload.get("schema") != OTA_MANIFEST_SCHEMA:
        raise ProtocolError("unsupported OTA manifest schema")
    if payload.get("product") != OTA_PRODUCT:
        raise ProtocolError("OTA manifest product mismatch")
    if payload.get("application") != OTA_APPLICATION:
        raise ProtocolError("OTA manifest application mismatch")

    image_payload = payload.get("image")
    if not isinstance(image_payload, dict):
        raise ProtocolError("OTA manifest image is required")

    board = _required_str(payload, "board")
    chip = _required_str(payload, "chip")
    version = _required_str(payload, "version")
    image_file = _required_str(image_payload, "file")
    sha256 = _required_str(image_payload, "sha256").lower()
    size_bytes = _required_int(image_payload, "size_bytes")

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

    return OtaManifest(
        product=OTA_PRODUCT,
        application=OTA_APPLICATION,
        board=board,
        chip=chip,
        version=version,
        image=OtaImage(file=image_file, size_bytes=size_bytes, sha256=sha256),
    )


def ota_hmac_message(request: OtaRequest) -> str:
    """Return the canonical HMAC message used by firmware."""
    _validate_ota_request(request)
    fields = (
        ("schema", OTA_REQUEST_SCHEMA),
        ("product", request.product),
        ("application", request.application),
        ("board", request.board),
        ("chip", request.chip),
        ("version", request.version),
        ("host", request.host),
        ("port", str(request.port)),
        ("path", request.path),
        ("size", str(request.size_bytes)),
        ("sha256", request.sha256.lower()),
        ("challenge", request.challenge.lower()),
        ("nonce", request.nonce),
    )
    return ";".join(f"{key}={value}" for key, value in fields) + ";"


def sign_ota_request(request: OtaRequest, hmac_key_hex: str) -> str:
    """Build a signed OTA request payload for MQTT."""
    key = bytes.fromhex(hmac_key_hex)
    if len(key) != 32:
        raise ProtocolError("OTA HMAC key must be 32 bytes")
    message = ota_hmac_message(request)
    digest = hmac.new(key, message.encode(), hashlib.sha256).hexdigest()
    return f"{message}hmac={digest}"


def redact_ota_payload(payload: str) -> str:
    """Redact the signature from an OTA request before logging."""
    return re.sub(r"hmac=[0-9a-fA-F]{64}", "hmac=<redacted>", payload)


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
    if not isinstance(value, int):
        raise ProtocolError(f"{key} is required")
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
