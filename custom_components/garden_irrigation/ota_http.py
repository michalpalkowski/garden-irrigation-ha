"""Ephemeral HTTP image delivery for controller-initiated OTA downloads."""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import secrets

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.http import KEY_HASS

from .const import DATA_OTA_ARTIFACTS, DATA_OTA_VIEW_REGISTERED, DOMAIN

_ARTIFACT_LIFETIME = dt.timedelta(minutes=10)


@dataclass(frozen=True)
class OtaArtifact:
    """One verified image held in memory for a single OTA operation."""

    image: bytes
    expires_at: dt.datetime


class GardenOtaImageView(HomeAssistantView):
    """Serve verified images at unguessable, short-lived paths."""

    url = "/api/garden-irrigation/ota/{token}"
    name = "api:garden_irrigation:ota_image"
    requires_auth = False

    async def get(self, request: web.Request, token: str) -> web.Response:
        """Return one active image without exposing HA credentials to firmware."""
        hass: HomeAssistant = request.app[KEY_HASS]
        artifacts: dict[str, OtaArtifact] = hass.data[DOMAIN][DATA_OTA_ARTIFACTS]
        artifact = artifacts.get(token)
        if artifact is None or artifact.expires_at <= dt.datetime.now(dt.UTC):
            artifacts.pop(token, None)
            raise web.HTTPNotFound()
        return web.Response(
            body=artifact.image,
            content_type="application/octet-stream",
            headers={"Cache-Control": "no-store"},
        )


def async_register_ota_view(hass: HomeAssistant) -> None:
    """Register the shared OTA image view once."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data.setdefault(DATA_OTA_ARTIFACTS, {})
    if domain_data.get(DATA_OTA_VIEW_REGISTERED):
        return
    hass.http.register_view(GardenOtaImageView)
    domain_data[DATA_OTA_VIEW_REGISTERED] = True


def register_artifact(hass: HomeAssistant, image: bytes) -> str:
    """Register a verified image and return its URL token."""
    token = secrets.token_urlsafe(18)
    artifacts: dict[str, OtaArtifact] = hass.data[DOMAIN][DATA_OTA_ARTIFACTS]
    artifacts[token] = OtaArtifact(
        image=image,
        expires_at=dt.datetime.now(dt.UTC) + _ARTIFACT_LIFETIME,
    )
    return token


def remove_artifact(hass: HomeAssistant, token: str) -> None:
    """Remove an image immediately after OTA completion or failure."""
    artifacts: dict[str, OtaArtifact] = hass.data[DOMAIN][DATA_OTA_ARTIFACTS]
    artifacts.pop(token, None)
