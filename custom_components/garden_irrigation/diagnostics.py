"""Diagnostics support for Garden Irrigation."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import GardenIrrigationConfigEntry
from .const import CONF_BASE_TOPIC, CONF_BOARD, CONF_CHIP, CONF_DEVICE_ID
from .diagnostic_redaction import redact_diagnostics_payload


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
            "diagnostics": redact_diagnostics_payload(runtime.state.diagnostics),
            "network_status": redact_diagnostics_payload(runtime.state.network_status),
            "wifi_rssi": runtime.state.wifi_rssi,
            "zones": {
                zone: {
                    "state": zone_state.state.value
                    if zone_state.state is not None
                    else None,
                    "manual_duration_minutes": zone_state.manual_duration_minutes,
                    "scheduled_duration_minutes": (
                        zone_state.scheduled_duration_minutes
                    ),
                    "schedule_enabled": zone_state.schedule_enabled,
                    "schedule_time": zone_state.schedule_time.isoformat(
                        timespec="minutes"
                    ),
                    "schedule_weekdays": zone_state.schedule_weekdays,
                    "run_seconds": zone_state.run_seconds,
                }
                for zone, zone_state in runtime.state.zones.items()
            },
        },
    }
