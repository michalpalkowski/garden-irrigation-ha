"""Number entities for Garden Irrigation."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DEFAULT_ZONE_COUNT
from .coordinator import GardenIrrigationRuntime
from .entity import GardenIrrigationEntity
from .protocol import MAX_DURATION_MINUTES, ProtocolError, parse_duration_minutes


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Garden Irrigation number entities."""
    runtime: GardenIrrigationRuntime = entry.runtime_data
    entities: list[NumberEntity] = []
    for zone in range(DEFAULT_ZONE_COUNT):
        entities.extend(
            [
                GardenZoneDurationNumber(runtime, zone, "manual"),
                GardenZoneDurationNumber(runtime, zone, "scheduled"),
            ]
        )
    async_add_entities(entities)


class GardenZoneDurationNumber(GardenIrrigationEntity, NumberEntity, RestoreEntity):
    """Home Assistant start duration setting for one zone."""

    _attr_icon = "mdi:timer-outline"
    _attr_native_min_value = 1
    _attr_native_max_value = MAX_DURATION_MINUTES
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_mode = "slider"

    def __init__(self, runtime: GardenIrrigationRuntime, zone: int, kind: str) -> None:
        """Initialize a zone duration number."""
        key = (
            f"zone_{zone}_duration_minutes"
            if kind == "manual"
            else f"zone_{zone}_scheduled_duration_minutes"
        )
        super().__init__(runtime, key)
        self.zone = zone
        self.kind = kind
        self._attr_name = f"Zone {zone} {kind} duration"
        self._attr_icon = (
            "mdi:timer-play-outline"
            if kind == "manual"
            else "mdi:timer-cog-outline"
        )

    @property
    def available(self) -> bool:
        """Return whether the HA-owned setting is available."""
        return True

    @property
    def native_value(self) -> int:
        """Return the current duration in minutes."""
        zone_state = self.runtime.state.zones[self.zone]
        if self.kind == "manual":
            return zone_state.manual_duration_minutes
        return zone_state.scheduled_duration_minutes

    async def async_added_to_hass(self) -> None:
        """Restore the last manual duration after Home Assistant restart."""
        await GardenIrrigationEntity.async_added_to_hass(self)
        last_state = await self.async_get_last_state()
        if last_state is None or last_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return

        try:
            value = parse_duration_minutes(last_state.state)
        except ProtocolError:
            return
        self._set_runtime_value(value)

    async def async_set_native_value(self, value: float) -> None:
        """Set the Home Assistant duration in minutes."""
        self._set_runtime_value(int(value))

    def _set_runtime_value(self, value: int) -> None:
        """Set the matching runtime duration."""
        if self.kind == "manual":
            self.runtime.set_manual_duration_minutes(self.zone, value)
        else:
            self.runtime.set_scheduled_duration_minutes(self.zone, value)
