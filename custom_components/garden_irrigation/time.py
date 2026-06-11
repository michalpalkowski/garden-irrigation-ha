"""Time entities for Garden Irrigation."""

from __future__ import annotations

import datetime as dt

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DEFAULT_ZONE_COUNT
from .coordinator import GardenIrrigationRuntime
from .entity import GardenIrrigationEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Garden Irrigation time entities."""
    runtime: GardenIrrigationRuntime = entry.runtime_data
    async_add_entities(
        [GardenZoneScheduleTime(runtime, zone) for zone in range(DEFAULT_ZONE_COUNT)]
    )


class GardenZoneScheduleTime(GardenIrrigationEntity, TimeEntity, RestoreEntity):
    """Local scheduled start time for one irrigation zone."""

    _attr_icon = "mdi:clock-outline"

    def __init__(self, runtime: GardenIrrigationRuntime, zone: int) -> None:
        """Initialize a zone schedule time entity."""
        super().__init__(runtime, f"zone_{zone}_schedule_time")
        self.zone = zone
        self._attr_name = f"Zone {zone} schedule time"

    @property
    def available(self) -> bool:
        """Return whether the HA-owned setting is available."""
        return True

    @property
    def native_value(self) -> dt.time:
        """Return the scheduled start time."""
        return self.runtime.state.zones[self.zone].schedule_time

    async def async_added_to_hass(self) -> None:
        """Restore the scheduled start time after Home Assistant restart."""
        await GardenIrrigationEntity.async_added_to_hass(self)
        last_state = await self.async_get_last_state()
        if last_state is None or last_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return
        try:
            value = dt.time.fromisoformat(last_state.state)
        except ValueError:
            return
        self.runtime.set_schedule_time(self.zone, value)

    async def async_set_value(self, value: dt.time) -> None:
        """Set the scheduled start time."""
        self.runtime.set_schedule_time(self.zone, value)
