"""Firmware update metadata entity for Garden Irrigation."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from homeassistant.components.update import UpdateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_OTA_MANIFEST_URL
from .coordinator import GardenIrrigationRuntime
from .entity import GardenIrrigationEntity
from .ota_update import (
    FirmwareUpdateMetadata,
    evaluate_firmware_update,
    firmware_status_from_network_status,
)
from .protocol import OtaManifest, ProtocolError, parse_ota_manifest

_LOGGER = logging.getLogger(__name__)
_MANIFEST_TIMEOUT_SECONDS = 10


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
        self._manifest: OtaManifest | None = None
        self._manifest_error: str | None = None
        self._manifest_url: str | None = None

    @property
    def installed_version(self) -> str | None:
        """Return the firmware version reported by the controller."""
        return firmware_status_from_network_status(
            self.runtime.state.network_status
        ).display_version

    @property
    def latest_version(self) -> str | None:
        """Return latest firmware version from the configured OTA manifest."""
        return self._metadata.latest_version

    @property
    def in_progress(self) -> bool:
        """Return whether HA is installing firmware."""
        return False

    @property
    def release_summary(self) -> str:
        """Return a short release note shown by Home Assistant."""
        return self._metadata.reason

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return controller firmware metadata."""
        status = self.runtime.state.network_status or {}
        attributes: dict[str, Any] = {
            "ota_install": "signed tooling",
            "ota_signature": "ecdsa-p256-sha256",
            "ota_manifest_url": self._manifest_url or "not_configured",
            "ota_manifest_error": self._manifest_error,
            "ota_update_available": self._metadata.update_available,
        }
        if self._manifest is not None:
            attributes.update(
                {
                    "latest_board": self._manifest.board,
                    "latest_chip": self._manifest.chip,
                    "latest_image_file": self._manifest.image.file,
                    "latest_image_size_bytes": self._manifest.image.size_bytes,
                    "latest_image_sha256": self._manifest.image.sha256,
                }
            )
        for key in ("board", "chip", "build_id"):
            value = status.get(key)
            if isinstance(value, str) and value:
                attributes[key] = value
        return attributes

    @property
    def _metadata(self) -> FirmwareUpdateMetadata:
        """Return safe update metadata for the current controller state."""
        try:
            return evaluate_firmware_update(
                firmware_status_from_network_status(self.runtime.state.network_status),
                self._manifest,
            )
        except ProtocolError as exc:
            return FirmwareUpdateMetadata(
                latest_version=self.installed_version,
                update_available=False,
                reason=str(exc),
            )

    async def async_added_to_hass(self) -> None:
        """Load optional OTA release metadata after entity registration."""
        await GardenIrrigationEntity.async_added_to_hass(self)
        self._manifest_url = self._configured_manifest_url
        if self._manifest_url is not None:
            await self._async_refresh_manifest()

    async def async_update(self) -> None:
        """Refresh release metadata when Home Assistant requests an update."""
        self._manifest_url = self._configured_manifest_url
        if self._manifest_url is not None:
            await self._async_refresh_manifest()

    async def async_install(
        self,
        version: str | None,
        backup: bool,
        **kwargs: Any,
    ) -> None:
        """Reject firmware installation until HA-side OTA is hardware-verified."""
        raise HomeAssistantError(
            "Firmware installation from Home Assistant is intentionally disabled; "
            "use the signed OTA tooling until HA install flow is hardware-verified."
        )

    @property
    def _configured_manifest_url(self) -> str | None:
        """Return the configured OTA manifest URL, if present."""
        value = self.runtime.entry.options.get(CONF_OTA_MANIFEST_URL)
        if not isinstance(value, str):
            return None
        value = value.strip()
        return value or None

    async def _async_refresh_manifest(self) -> None:
        """Fetch and validate the configured OTA manifest."""
        assert self._manifest_url is not None
        session = async_get_clientsession(self.runtime.hass)
        try:
            async with asyncio.timeout(_MANIFEST_TIMEOUT_SECONDS):
                async with session.get(self._manifest_url) as response:
                    response.raise_for_status()
                    payload = json.loads(await response.text())
            if not isinstance(payload, dict):
                raise ProtocolError("OTA manifest response must be a JSON object")
            self._manifest = parse_ota_manifest(payload)
            self._manifest_error = None
        except (
            TimeoutError,
            OSError,
            json.JSONDecodeError,
            ProtocolError,
        ) as exc:
            self._manifest = None
            self._manifest_error = str(exc)
            _LOGGER.warning("Cannot load Garden Irrigation OTA manifest: %s", exc)
