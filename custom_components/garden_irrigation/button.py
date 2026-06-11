"""Button entities for Garden Irrigation."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import GardenIrrigationRuntime
from .entity import GardenIrrigationEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Garden Irrigation button entities."""
    runtime: GardenIrrigationRuntime = entry.runtime_data
    async_add_entities([GardenStopAllButton(runtime)])


class GardenStopAllButton(GardenIrrigationEntity, ButtonEntity):
    """Stop all irrigation zones immediately."""

    _attr_name = "Stop all"
    _attr_icon = "mdi:stop-circle-outline"

    def __init__(self, runtime: GardenIrrigationRuntime) -> None:
        """Initialize the stop-all button."""
        super().__init__(runtime, "stop_all")

    async def async_press(self) -> None:
        """Publish a stop-all command."""
        await self.runtime.async_stop_all()
