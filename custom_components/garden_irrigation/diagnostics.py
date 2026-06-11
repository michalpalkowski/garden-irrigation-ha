"""Diagnostics support for Garden Irrigation."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import GardenIrrigationConfigEntry
from .const import CONF_BASE_TOPIC, CONF_BOARD, CONF_CHIP, CONF_DEVICE_ID


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: GardenIrrigationConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime = entry.runtime_data
    return {
        "entry": {
            "device_id": entry.data.get(CONF_DEVICE_ID),
            "base_topic": entry.data.get(CONF_BASE_TOPIC),
            "board": entry.data.get(CONF_BOARD),
            "chip": entry.data.get(CONF_CHIP),
        },
        "runtime": {
            "available": runtime.available,
            "availability": (
                runtime.state.availability.value
                if runtime.state.availability is not None
                else None
            ),
            "controller_state": runtime.state.controller_state,
            "diagnostics": runtime.state.diagnostics,
            "zones": {
                zone: {
                    "state": zone_state.state.value
                    if zone_state.state is not None
                    else None,
                    "duration_minutes": zone_state.duration_minutes,
                    "run_seconds": zone_state.run_seconds,
                }
                for zone, zone_state in runtime.state.zones.items()
            },
        },
    }
