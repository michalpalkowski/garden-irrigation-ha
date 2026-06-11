"""Switch entities for Garden Irrigation."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DEFAULT_ZONE_COUNT, WEEKDAYS
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
    entities: list[SwitchEntity] = []
    for zone in range(DEFAULT_ZONE_COUNT):
        entities.append(GardenZoneSwitch(runtime, zone))
        entities.append(GardenZoneScheduleEnabledSwitch(runtime, zone))
        for weekday, slug, label in WEEKDAYS:
            entities.append(GardenZoneWeekdaySwitch(runtime, zone, weekday, slug, label))
    async_add_entities(entities)


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
        duration_minutes = self.runtime.state.zones[self.zone].manual_duration_minutes
        await self.runtime.async_start_zone(self.zone, duration_minutes * 60)

    async def async_turn_off(self, **kwargs: object) -> None:
        """Stop this zone."""
        await self.runtime.async_stop_zone(self.zone)


class GardenZoneScheduleEnabledSwitch(
    GardenIrrigationEntity, SwitchEntity, RestoreEntity
):
    """Local schedule enable switch for one irrigation zone."""

    _attr_icon = "mdi:calendar-check-outline"

    def __init__(self, runtime: GardenIrrigationRuntime, zone: int) -> None:
        """Initialize a schedule enable switch."""
        super().__init__(runtime, f"zone_{zone}_schedule_enabled")
        self.zone = zone
        self._attr_name = f"Zone {zone} schedule"

    @property
    def available(self) -> bool:
        """Return whether the HA-owned setting is available."""
        return True

    @property
    def is_on(self) -> bool:
        """Return whether the local schedule is enabled."""
        return self.runtime.state.zones[self.zone].schedule_enabled

    async def async_added_to_hass(self) -> None:
        """Restore the schedule setting after Home Assistant restart."""
        await GardenIrrigationEntity.async_added_to_hass(self)
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self.runtime.set_schedule_enabled(self.zone, last_state.state == STATE_ON)

    async def async_turn_on(self, **kwargs: object) -> None:
        """Enable the local schedule."""
        self.runtime.set_schedule_enabled(self.zone, True)

    async def async_turn_off(self, **kwargs: object) -> None:
        """Disable the local schedule."""
        self.runtime.set_schedule_enabled(self.zone, False)


class GardenZoneWeekdaySwitch(GardenIrrigationEntity, SwitchEntity, RestoreEntity):
    """Local weekday switch for one scheduled irrigation zone."""

    _attr_icon = "mdi:calendar-blank-outline"

    def __init__(
        self,
        runtime: GardenIrrigationRuntime,
        zone: int,
        weekday: int,
        slug: str,
        label: str,
    ) -> None:
        """Initialize a schedule weekday switch."""
        super().__init__(runtime, f"zone_{zone}_schedule_{slug}")
        self.zone = zone
        self.weekday = weekday
        self._attr_name = f"Zone {zone} {label}"

    @property
    def available(self) -> bool:
        """Return whether the HA-owned setting is available."""
        return True

    @property
    def is_on(self) -> bool:
        """Return whether this weekday is enabled."""
        return self.runtime.state.zones[self.zone].schedule_weekdays[self.weekday]

    async def async_added_to_hass(self) -> None:
        """Restore the weekday setting after Home Assistant restart."""
        await GardenIrrigationEntity.async_added_to_hass(self)
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self.runtime.set_schedule_weekday(
                self.zone,
                self.weekday,
                last_state.state == STATE_ON,
            )

    async def async_turn_on(self, **kwargs: object) -> None:
        """Enable this scheduled weekday."""
        self.runtime.set_schedule_weekday(self.zone, self.weekday, True)

    async def async_turn_off(self, **kwargs: object) -> None:
        """Disable this scheduled weekday."""
        self.runtime.set_schedule_weekday(self.zone, self.weekday, False)
