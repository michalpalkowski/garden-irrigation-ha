"""Garden Irrigation Home Assistant integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import GardenIrrigationRuntime

type GardenIrrigationConfigEntry = ConfigEntry[GardenIrrigationRuntime]


async def async_setup_entry(
    hass: HomeAssistant, entry: GardenIrrigationConfigEntry
) -> bool:
    """Set up Garden Irrigation from a config entry."""
    runtime = GardenIrrigationRuntime(hass, entry)
    await runtime.async_start()
    entry.runtime_data = runtime

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
