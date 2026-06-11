"""Switch entities for Garden Irrigation."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_ZONE_COUNT
from .coordinator import GardenIrrigationRuntime
from .entity import GardenIrrigationEntity
from .protocol import ZoneState


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Garden Irrigation switch entities."""
    runtime: GardenIrrigationRuntime = entry.runtime_data
    async_add_entities(
        [GardenZoneSwitch(runtime, zone) for zone in range(DEFAULT_ZONE_COUNT)]
    )


class GardenZoneSwitch(GardenIrrigationEntity, SwitchEntity):
    """Manual control switch for one irrigation zone."""

    _attr_icon = "mdi:valve"

    def __init__(self, runtime: GardenIrrigationRuntime, zone: int) -> None:
        """Initialize a zone switch."""
        super().__init__(runtime, f"zone_{zone}")
        self.zone = zone
        self._attr_name = f"Zone {zone}"

    @property
    def is_on(self) -> bool | None:
        """Return whether this zone is watering."""
        state = self.runtime.state.zones[self.zone].state
        if state is None:
            return None
        return state == ZoneState.WATERING

    async def async_turn_on(self, **kwargs: object) -> None:
        """Start this zone for its Home Assistant manual duration."""
        duration_minutes = self.runtime.state.zones[self.zone].duration_minutes
        await self.runtime.async_start_zone(self.zone, duration_minutes * 60)

    async def async_turn_off(self, **kwargs: object) -> None:
        """Stop this zone."""
        await self.runtime.async_stop_zone(self.zone)
