"""Pure option validation helpers for Garden Irrigation."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class GardenOptions:
    """Validated Garden Irrigation options."""

    weather_entity: str
    ota_manifest_url: str


def validate_options(
    weather_entity: object,
    ota_manifest_url: object,
) -> GardenOptions:
    """Validate options entered in the Home Assistant options flow."""
    weather_entity_text = _option_string(weather_entity)
    ota_manifest_url_text = _option_string(ota_manifest_url)
    if weather_entity_text and not is_weather_entity_id(weather_entity_text):
        raise ValueError("invalid_weather_entity")
    if ota_manifest_url_text and not is_https_url(ota_manifest_url_text):
        raise ValueError("invalid_ota_manifest_url")
    return GardenOptions(
        weather_entity=weather_entity_text,
        ota_manifest_url=ota_manifest_url_text,
    )


def is_weather_entity_id(value: str) -> bool:
    """Return whether a user value looks like a weather entity ID."""
    return value.startswith("weather.") and "/" not in value and "#" not in value


def is_https_url(value: str) -> bool:
    """Return whether a user value is an HTTPS URL."""
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc) and bool(parsed.path)


def _option_string(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()
