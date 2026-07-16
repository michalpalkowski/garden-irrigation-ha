"""Firmware update metadata helpers for Garden Irrigation."""

from __future__ import annotations

from dataclasses import dataclass
import re

from .protocol import NetworkStatus, OtaManifest, ProtocolError

_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


@dataclass(frozen=True)
class FirmwareStatus:
    """Installed firmware identity reported by the controller."""

    version: str | None
    build_id: str | None
    board: str | None
    chip: str | None
    runtime_config_persisted: bool

    @property
    def display_version(self) -> str | None:
        """Return Home Assistant display version."""
        if not self.version:
            return None
        if self.build_id:
            return f"{self.version}+{self.build_id}"
        return self.version


@dataclass(frozen=True)
class FirmwareUpdateMetadata:
    """Safe update metadata derived from an OTA manifest."""

    latest_version: str | None
    update_available: bool
    reason: str


def firmware_status_from_network_status(
    network_status: NetworkStatus | None,
) -> FirmwareStatus:
    """Extract firmware identity from the MQTT network status payload."""
    status = network_status
    return FirmwareStatus(
        version=status.version if status is not None else None,
        build_id=status.build_id if status is not None else None,
        board=status.board if status is not None else None,
        chip=status.chip if status is not None else None,
        runtime_config_persisted=(
            status.runtime_config_persisted if status is not None else False
        ),
    )


def evaluate_firmware_update(
    installed: FirmwareStatus,
    manifest: OtaManifest | None,
) -> FirmwareUpdateMetadata:
    """Evaluate whether a manifest represents an update for this controller."""
    if manifest is None:
        return FirmwareUpdateMetadata(
            latest_version=installed.display_version,
            update_available=False,
            reason="No OTA manifest is configured.",
        )
    if installed.board and manifest.board != installed.board:
        raise ProtocolError("OTA manifest board does not match controller board")
    if installed.chip and manifest.chip != installed.chip:
        raise ProtocolError("OTA manifest chip does not match controller chip")
    if manifest.provisioning_required and not installed.runtime_config_persisted:
        return FirmwareUpdateMetadata(
            latest_version=installed.display_version,
            update_available=False,
            reason=(
                "Release requires runtime provisioning and cannot replace an "
                "operator-configured controller."
            ),
        )
    if installed.version is None:
        return FirmwareUpdateMetadata(
            latest_version=manifest.version,
            update_available=False,
            reason="Controller has not reported an installed firmware version yet.",
        )
    version_order = compare_versions(manifest.version, installed.version)
    update_available = version_order > 0 or (
        version_order == 0 and manifest.build_id != installed.build_id
    )
    latest_display_version = f"{manifest.version}+{manifest.build_id}"
    return FirmwareUpdateMetadata(
        latest_version=latest_display_version
        if update_available
        else installed.display_version,
        update_available=update_available,
        reason="OTA release has a newer version or build."
        if update_available
        else "Installed firmware is current for the configured OTA manifest.",
    )


def compare_versions(left: str, right: str) -> int:
    """Compare simple semantic firmware versions."""
    left_parts = _parse_version(left)
    right_parts = _parse_version(right)
    if left_parts == right_parts:
        return 0
    return 1 if left_parts > right_parts else -1


def _parse_version(value: str) -> tuple[int, int, int]:
    match = _SEMVER_RE.fullmatch(value.strip())
    if match is None:
        raise ProtocolError("firmware version must be semantic version x.y.z")
    return tuple(int(part) for part in match.groups())


def _optional_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None
