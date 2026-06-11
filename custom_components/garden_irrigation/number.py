"""Number entities for Garden Irrigation."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_ZONE_COUNT
from .coordinator import GardenIrrigationRuntime
from .entity import GardenIrrigationEntity
from .protocol import MAX_DURATION_MINUTES


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Garden Irrigation number entities."""
    runtime: GardenIrrigationRuntime = entry.runtime_data
    async_add_entities(
        [GardenZoneDurationNumber(runtime, zone) for zone in range(DEFAULT_ZONE_COUNT)]
    )


class GardenZoneDurationNumber(GardenIrrigationEntity, NumberEntity):
    """Firmware duration setting for one zone."""

    _attr_icon = "mdi:timer-outline"
    _attr_native_min_value = 1
    _attr_native_max_value = MAX_DURATION_MINUTES
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_mode = "slider"

    def __init__(self, runtime: GardenIrrigationRuntime, zone: int) -> None:
        """Initialize a zone duration number."""
        super().__init__(runtime, f"zone_{zone}_duration_minutes")
        self.zone = zone
        self._attr_name = f"Zone {zone} duration"

    @property
    def native_value(self) -> int | None:
        """Return the current duration in minutes."""
        return self.runtime.state.zones[self.zone].duration_minutes

    async def async_set_native_value(self, value: float) -> None:
        """Set the firmware duration in minutes."""
        await self.runtime.async_set_duration_minutes(self.zone, int(value))
