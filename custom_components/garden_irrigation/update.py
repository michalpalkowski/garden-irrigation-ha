"""Firmware update metadata entity for Garden Irrigation."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import datetime as dt
import hashlib
import json
import logging
from typing import Any
from urllib.parse import urljoin, urlparse

import aiohttp
from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.network import get_url

from .const import (
    CONF_OTA_GITHUB_REPOSITORY,
    CONF_OTA_GITHUB_TOKEN,
    CONF_OTA_MANIFEST_URL,
    DEFAULT_OTA_GITHUB_REPOSITORY,
)
from .coordinator import GardenIrrigationRuntime
from .entity import GardenIrrigationEntity
from .ota_update import (
    FirmwareUpdateMetadata,
    evaluate_firmware_update,
    firmware_status_from_network_status,
)
from .ota_http import register_artifact, remove_artifact
from .github_release import latest_release_url, parse_release_assets
from .protocol import (
    OTA_APPLICATION,
    OTA_PRODUCT,
    OtaManifest,
    OtaRequest,
    ProtocolError,
    build_ota_request_payload,
    parse_ota_manifest,
)

_LOGGER = logging.getLogger(__name__)
_MANIFEST_TIMEOUT_SECONDS = 10
_IMAGE_TIMEOUT_SECONDS = 30
_OTA_OPERATION_TIMEOUT_SECONDS = 300
_MAX_OTA_IMAGE_BYTES = 1_245_184
_OTA_CONFIRMED_DIAGNOSTIC = "ota: running image confirmed"
_GITHUB_API_VERSION = "2022-11-28"


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
    _attr_supported_features = UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS

    def __init__(self, runtime: GardenIrrigationRuntime) -> None:
        """Initialize firmware metadata entity."""
        super().__init__(runtime, "firmware")
        self._manifest: OtaManifest | None = None
        self._manifest_error: str | None = None
        self._manifest_url: str | None = None
        self._github_repository: str | None = None
        self._github_token: str | None = None
        self._image_download_url: str | None = None
        self._release_tag: str | None = None
        self._installing = False
        self._install_percentage: int | None = None
        self._install_error: str | None = None

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
        return self._installing

    @property
    def update_percentage(self) -> int | None:
        """Return progress for the active OTA operation."""
        return self._install_percentage

    @property
    def release_summary(self) -> str:
        """Return a short release note shown by Home Assistant."""
        return self._metadata.reason

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return controller firmware metadata."""
        status = self.runtime.state.network_status
        attributes: dict[str, Any] = {
            "ota_install": "home_assistant_signed_ota",
            "ota_signature": "ecdsa-p256-sha256",
            "ota_manifest_url": self._manifest_url or "not_configured",
            "ota_github_repository": self._github_repository or "not_configured",
            "ota_github_token_configured": self._github_token is not None,
            "ota_release_tag": self._release_tag,
            "ota_manifest_error": self._manifest_error,
            "ota_update_available": self._metadata.update_available,
            "ota_install_error": self._install_error,
        }
        if self._manifest is not None:
            attributes.update(
                {
                    "latest_board": self._manifest.board,
                    "latest_chip": self._manifest.chip,
                    "latest_image_file": self._manifest.image.file,
                    "latest_image_size_bytes": self._manifest.image.size_bytes,
                    "latest_image_sha256": self._manifest.image.sha256,
                    "latest_build_id": self._manifest.build_id,
                    "latest_channel": self._manifest.channel,
                    "latest_provisioning_required": (
                        self._manifest.provisioning_required
                    ),
                }
            )
        if status is not None:
            attributes.update(status.as_dict())
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
        self._refresh_source_config()
        if self._has_release_source:
            await self._async_refresh_manifest()

    async def async_update(self) -> None:
        """Refresh release metadata when Home Assistant requests an update."""
        self._refresh_source_config()
        if self._has_release_source:
            await self._async_refresh_manifest()

    async def async_install(
        self,
        version: str | None,
        backup: bool,
        **kwargs: Any,
    ) -> None:
        """Install and remotely confirm one signed firmware image."""
        if backup:
            raise HomeAssistantError("Firmware OTA does not support Home Assistant backups")
        if self._installing:
            raise HomeAssistantError("A firmware OTA operation is already running")
        if not self.runtime.available:
            raise HomeAssistantError("Controller must be online before OTA can start")
        if not self._has_release_source:
            raise HomeAssistantError("Configure an OTA release source first")

        await self._async_refresh_manifest()
        manifest = self._manifest
        if manifest is None:
            raise HomeAssistantError(
                f"Cannot load OTA manifest: {self._manifest_error or 'unknown error'}"
            )
        if version is not None and version != manifest.version:
            raise HomeAssistantError("Requested version does not match OTA manifest")
        status = self.runtime.state.network_status
        if status is None:
            raise HomeAssistantError("Controller has not published network status")
        if manifest.board != status.board or manifest.chip != status.chip:
            raise HomeAssistantError("OTA manifest does not match controller hardware")
        if manifest.provisioning_required and not status.runtime_config_persisted:
            raise HomeAssistantError(
                "Firmware release requires persisted runtime configuration"
            )

        token: str | None = None
        self._installing = True
        self._install_error = None
        self._set_install_percentage(5)
        try:
            image = await self._async_download_verified_image(manifest)
            self._set_install_percentage(20)
            token = register_artifact(self.runtime.hass, image)
            host, port, path = self._controller_download_location(token)

            challenge = self.runtime.state.ota_challenge
            if challenge is None:
                raise HomeAssistantError("Controller has not published an OTA challenge")
            diagnostics_sequence = self.runtime.state.diagnostics_sequence
            network_sequence = self.runtime.state.network_status_sequence
            challenge_sequence = self.runtime.state.ota_challenge_sequence
            nonce = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
            request = OtaRequest(
                product=OTA_PRODUCT,
                application=OTA_APPLICATION,
                board=manifest.board,
                chip=manifest.chip,
                version=manifest.version,
                build_id=manifest.build_id,
                channel=manifest.channel,
                host=host,
                port=port,
                path=path,
                size_bytes=manifest.image.size_bytes,
                sha256=manifest.image.sha256,
                challenge=challenge,
                nonce=nonce,
                signature=manifest.signature.value,
            )
            await self.runtime.async_publish_ota_request(
                build_ota_request_payload(request)
            )
            self._set_install_percentage(35)

            await _async_wait_for_runtime(
                self.runtime,
                lambda: (
                    self.runtime.state.diagnostics_sequence > diagnostics_sequence
                    and self.runtime.state.diagnostics == f"ota:verified:{challenge}"
                ),
                _OTA_OPERATION_TIMEOUT_SECONDS,
                "Firmware did not verify the OTA image before timeout",
            )
            self._set_install_percentage(65)

            await _async_wait_for_runtime(
                self.runtime,
                lambda: (
                    self.runtime.state.network_status_sequence > network_sequence
                    and self.runtime.state.network_status is not None
                    and self.runtime.state.network_status.build_id == manifest.build_id
                ),
                _OTA_OPERATION_TIMEOUT_SECONDS,
                "Controller did not return with the expected OTA build",
            )
            await _async_wait_for_runtime(
                self.runtime,
                lambda: (
                    self.runtime.state.ota_challenge_sequence > challenge_sequence
                    and self.runtime.state.ota_challenge is not None
                    and self.runtime.state.ota_challenge != challenge
                ),
                _OTA_OPERATION_TIMEOUT_SECONDS,
                "Controller did not publish a fresh post-reboot OTA challenge",
            )
            self._set_install_percentage(85)

            post_reboot_challenge = self.runtime.state.ota_challenge
            assert post_reboot_challenge is not None
            confirmation_sequence = self.runtime.state.diagnostics_sequence
            await self.runtime.async_confirm_ota(
                f"CONFIRM2:{post_reboot_challenge}:{manifest.build_id}:"
                f"{manifest.image.sha256}"
            )
            await _async_wait_for_runtime(
                self.runtime,
                lambda: (
                    self.runtime.state.diagnostics_sequence > confirmation_sequence
                    and self.runtime.state.diagnostics == _OTA_CONFIRMED_DIAGNOSTIC
                ),
                _OTA_OPERATION_TIMEOUT_SECONDS,
                "Firmware did not confirm the new boot slot",
            )
            self._set_install_percentage(100)
        except (HomeAssistantError, ProtocolError, TimeoutError, OSError) as exc:
            self._install_error = str(exc)
            raise HomeAssistantError(f"Firmware OTA failed: {exc}") from exc
        finally:
            if token is not None:
                remove_artifact(self.runtime.hass, token)
            self._installing = False
            self._install_percentage = None
            self.async_write_ha_state()

    @property
    def _configured_manifest_url(self) -> str | None:
        """Return the configured OTA manifest URL, if present."""
        value = self.runtime.entry.options.get(CONF_OTA_MANIFEST_URL)
        if not isinstance(value, str):
            return None
        value = value.strip()
        return value or None

    @property
    def _configured_github_repository(self) -> str | None:
        value = self.runtime.entry.options.get(CONF_OTA_GITHUB_REPOSITORY)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if self._configured_manifest_url is not None:
            return None
        return DEFAULT_OTA_GITHUB_REPOSITORY

    @property
    def _configured_github_token(self) -> str | None:
        value = self.runtime.entry.options.get(CONF_OTA_GITHUB_TOKEN)
        if not isinstance(value, str):
            return None
        value = value.strip()
        return value or None

    @property
    def _has_release_source(self) -> bool:
        return self._manifest_url is not None or self._github_repository is not None

    def _refresh_source_config(self) -> None:
        self._manifest_url = self._configured_manifest_url
        self._github_repository = self._configured_github_repository
        self._github_token = self._configured_github_token

    async def _async_refresh_manifest(self) -> None:
        """Fetch and validate the configured OTA manifest."""
        if not self._has_release_source:
            raise HomeAssistantError("OTA release source is not configured")
        session = async_get_clientsession(self.runtime.hass)
        release = None
        try:
            async with asyncio.timeout(_MANIFEST_TIMEOUT_SECONDS):
                if self._github_repository is not None:
                    headers = self._github_headers("application/vnd.github+json")
                    async with session.get(
                        latest_release_url(self._github_repository),
                        headers=headers,
                    ) as response:
                        response.raise_for_status()
                        release_payload = json.loads(await response.text())
                    release = parse_release_assets(release_payload)
                    async with session.get(
                        release.manifest_url,
                        headers=self._github_headers("application/octet-stream"),
                    ) as response:
                        response.raise_for_status()
                        payload = json.loads(await response.text())
                    self._release_tag = release.tag_name
                else:
                    assert self._manifest_url is not None
                    async with session.get(self._manifest_url) as response:
                        response.raise_for_status()
                        payload = json.loads(await response.text())
            if not isinstance(payload, dict):
                raise ProtocolError("OTA manifest response must be a JSON object")
            manifest = parse_ota_manifest(payload)
            self._manifest = manifest
            self._image_download_url = (
                release.image_url(manifest.image.file)
                if self._github_repository is not None
                else urljoin(self._manifest_url or "", manifest.image.file)
            )
            self._manifest_error = None
        except (
            TimeoutError,
            OSError,
            aiohttp.ClientError,
            json.JSONDecodeError,
            ProtocolError,
        ) as exc:
            self._manifest = None
            self._image_download_url = None
            self._manifest_error = str(exc)
            _LOGGER.warning("Cannot load Garden Irrigation OTA manifest: %s", exc)

    async def _async_download_verified_image(self, manifest: OtaManifest) -> bytes:
        """Download an image over HTTPS and verify signed manifest metadata."""
        image_url = self._image_download_url
        if image_url is None:
            raise HomeAssistantError("OTA image URL is not available")
        parsed = urlparse(image_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise HomeAssistantError("OTA image URL must use HTTPS")
        if manifest.image.size_bytes > _MAX_OTA_IMAGE_BYTES:
            raise HomeAssistantError("OTA image is larger than the controller slot")

        session = async_get_clientsession(self.runtime.hass)
        chunks: list[bytes] = []
        received = 0
        digest = hashlib.sha256()
        async with asyncio.timeout(_IMAGE_TIMEOUT_SECONDS):
            headers = (
                self._github_headers("application/octet-stream")
                if self._github_repository is not None
                else None
            )
            async with session.get(image_url, headers=headers) as response:
                response.raise_for_status()
                async for chunk in response.content.iter_chunked(64 * 1024):
                    received += len(chunk)
                    if received > manifest.image.size_bytes:
                        raise HomeAssistantError("OTA image exceeds manifest size")
                    digest.update(chunk)
                    chunks.append(chunk)
        if received != manifest.image.size_bytes:
            raise HomeAssistantError("OTA image size does not match manifest")
        if digest.hexdigest() != manifest.image.sha256:
            raise HomeAssistantError("OTA image SHA-256 does not match manifest")
        return b"".join(chunks)

    def _github_headers(self, accept: str) -> dict[str, str]:
        headers = {
            "Accept": accept,
            "X-GitHub-Api-Version": _GITHUB_API_VERSION,
        }
        if self._github_token is not None:
            headers["Authorization"] = f"Bearer {self._github_token}"
        return headers

    def _controller_download_location(self, token: str) -> tuple[str, int, str]:
        """Return a firmware-compatible URL on HA's configured internal URL."""
        base_url = get_url(
            self.runtime.hass,
            prefer_external=False,
            allow_internal=True,
            allow_ip=True,
        )
        parsed = urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname is None:
            raise HomeAssistantError(
                "Home Assistant internal URL must be plain HTTP and reachable from the controller"
            )
        path = f"/api/garden-irrigation/ota/{token}"
        return parsed.hostname, parsed.port or 80, path

    def _set_install_percentage(self, value: int) -> None:
        self._install_percentage = value
        self.async_write_ha_state()


async def _async_wait_for_runtime(
    runtime: GardenIrrigationRuntime,
    predicate: Callable[[], bool],
    timeout_seconds: int,
    timeout_message: str,
) -> None:
    """Wait for a coordinator transition without polling MQTT directly."""
    if predicate():
        return
    changed = asyncio.Event()
    unsubscribe = runtime.async_add_listener(changed.set)
    try:
        async with asyncio.timeout(timeout_seconds):
            while not predicate():
                await changed.wait()
                changed.clear()
    except TimeoutError as exc:
        raise HomeAssistantError(timeout_message) from exc
    finally:
        unsubscribe()
