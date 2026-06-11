"""Firmware update metadata entity for Garden Irrigation."""

from __future__ import annotations

from typing import Any

from homeassistant.components.update import UpdateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import GardenIrrigationRuntime
from .entity import GardenIrrigationEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Garden Irrigation update entities."""
    runtime: GardenIrrigationRuntime = entry.runtime_data
    async_add_entities([GardenFirmwareUpdateEntity(runtime)])


class GardenFirmwareUpdateEntity(GardenIrrigationEntity, UpdateEntity):
    """Expose installed firmware metadata from the controller."""

    _attr_name = "Firmware"
    _attr_icon = "mdi:chip"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime: GardenIrrigationRuntime) -> None:
        """Initialize firmware metadata entity."""
        super().__init__(runtime, "firmware")

    @property
    def installed_version(self) -> str | None:
        """Return the firmware version reported by the controller."""
        status = self.runtime.state.network_status or {}
        version = status.get("version")
        if not isinstance(version, str) or not version:
            return None

        build_id = status.get("build_id")
        if isinstance(build_id, str) and build_id:
            return f"{version}+{build_id}"
        return version

    @property
    def latest_version(self) -> str | None:
        """Return latest known version.

        HACS updates the integration itself. Firmware installation still uses
        the signed OTA tooling, so HA must not advertise a firmware update until
        a trusted release manifest source is configured.
        """
        return self.installed_version

    @property
    def release_summary(self) -> str:
        """Return a short release note shown by Home Assistant."""
        return "Firmware metadata is reported by MQTT; signed OTA is handled by the release tooling."

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return controller firmware metadata."""
        status = self.runtime.state.network_status or {}
        attributes: dict[str, Any] = {
            "ota_install": "signed tooling",
            "ota_signature": "ecdsa-p256-sha256",
        }
        for key in ("board", "chip", "build_id"):
            value = status.get(key)
            if isinstance(value, str) and value:
                attributes[key] = value
        return attributes
