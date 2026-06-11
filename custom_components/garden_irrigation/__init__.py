"""Garden Irrigation Home Assistant integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, PLATFORMS
from .coordinator import GardenIrrigationRuntime
from .protocol import MAX_DURATION_MINUTES, validate_zone

type GardenIrrigationConfigEntry = ConfigEntry[GardenIrrigationRuntime]

SERVICE_START_ZONE = "start_zone"
SERVICE_STOP_ZONE = "stop_zone"
SERVICE_STOP_ALL = "stop_all"

ATTR_DEVICE_ID = "device_id"
ATTR_ENTRY_ID = "entry_id"
ATTR_ZONE = "zone"
ATTR_DURATION_MINUTES = "duration_minutes"

SERVICE_TARGET_SCHEMA = {
    vol.Optional(ATTR_DEVICE_ID): cv.string,
    vol.Optional(ATTR_ENTRY_ID): cv.string,
}

START_ZONE_SCHEMA = vol.Schema(
    {
        **SERVICE_TARGET_SCHEMA,
        vol.Required(ATTR_ZONE): vol.All(vol.Coerce(int), vol.Range(min=0, max=3)),
        vol.Required(ATTR_DURATION_MINUTES): vol.All(
            vol.Coerce(int),
            vol.Range(min=1, max=MAX_DURATION_MINUTES),
        ),
    }
)
STOP_ZONE_SCHEMA = vol.Schema(
    {
        **SERVICE_TARGET_SCHEMA,
        vol.Required(ATTR_ZONE): vol.All(vol.Coerce(int), vol.Range(min=0, max=3)),
    }
)
STOP_ALL_SCHEMA = vol.Schema(SERVICE_TARGET_SCHEMA)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up Garden Irrigation services."""
    hass.data.setdefault(DOMAIN, {})

    async def _handle_start_zone(call: Any) -> None:
        runtime = _runtime_from_service_call(hass, call.data)
        zone = validate_zone(call.data[ATTR_ZONE])
        duration_minutes = call.data[ATTR_DURATION_MINUTES]
        await runtime.async_start_zone(zone, duration_minutes * 60)

    async def _handle_stop_zone(call: Any) -> None:
        runtime = _runtime_from_service_call(hass, call.data)
        await runtime.async_stop_zone(validate_zone(call.data[ATTR_ZONE]))

    async def _handle_stop_all(call: Any) -> None:
        runtime = _runtime_from_service_call(hass, call.data)
        await runtime.async_stop_all()

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_ZONE,
        _handle_start_zone,
        schema=START_ZONE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_ZONE,
        _handle_stop_zone,
        schema=STOP_ZONE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_ALL,
        _handle_stop_all,
        schema=STOP_ALL_SCHEMA,
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: GardenIrrigationConfigEntry
) -> bool:
    """Set up Garden Irrigation from a config entry."""
    runtime = GardenIrrigationRuntime(hass, entry)
    await runtime.async_start()
    entry.runtime_data = runtime
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GardenIrrigationConfigEntry
) -> bool:
    """Unload a Garden Irrigation config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await entry.runtime_data.async_stop()
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok


def _runtime_from_service_call(
    hass: HomeAssistant,
    data: dict[str, Any],
) -> GardenIrrigationRuntime:
    """Resolve a configured runtime from a service call."""
    runtimes: dict[str, GardenIrrigationRuntime] = hass.data.get(DOMAIN, {})
    entry_id = data.get(ATTR_ENTRY_ID)
    device_id = data.get(ATTR_DEVICE_ID)

    if entry_id is not None:
        runtime = runtimes.get(entry_id)
        if runtime is None:
            raise HomeAssistantError(f"Garden Irrigation entry {entry_id} not found")
        return runtime

    if device_id is not None:
        for runtime in runtimes.values():
            if runtime.device_id == device_id:
                return runtime
        raise HomeAssistantError(f"Garden Irrigation device {device_id} not found")

    if len(runtimes) == 1:
        return next(iter(runtimes.values()))

    if not runtimes:
        raise HomeAssistantError("No Garden Irrigation controller is configured")
    raise HomeAssistantError("Specify entry_id or device_id for this service call")
