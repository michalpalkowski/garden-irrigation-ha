"""Number entities for Garden Irrigation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DEFAULT_HUMIDITY_SKIP_PERCENT,
    DEFAULT_PRECIPITATION_SKIP_MM,
    DEFAULT_RAIN_PROBABILITY_SKIP_PERCENT,
    DEFAULT_ZONE_COUNT,
)
from .coordinator import GardenIrrigationRuntime
from .entity import GardenIrrigationEntity
from .protocol import MAX_DURATION_MINUTES, ProtocolError, parse_duration_minutes


@dataclass(frozen=True)
class GardenThresholdDescription:
    """Description for one HA-owned weather guard threshold."""

    key: str
    name: str
    icon: str
    native_min_value: float
    native_max_value: float
    native_step: float
    native_unit_of_measurement: str
    value_fn: Callable[[GardenIrrigationRuntime], float]
    set_fn: Callable[[GardenIrrigationRuntime, float], None]


THRESHOLD_DESCRIPTIONS = (
    GardenThresholdDescription(
        key="weather_rain_probability_skip_percent",
        name="Weather rain probability skip threshold",
        icon="mdi:weather-pouring",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda runtime: runtime.state.rain_probability_skip_percent,
        set_fn=lambda runtime, value: runtime.set_rain_probability_skip_percent(value),
    ),
    GardenThresholdDescription(
        key="weather_precipitation_skip_mm",
        name="Weather precipitation skip threshold",
        icon="mdi:weather-rainy",
        native_min_value=0,
        native_max_value=100,
        native_step=0.1,
        native_unit_of_measurement="mm",
        value_fn=lambda runtime: runtime.state.precipitation_skip_mm,
        set_fn=lambda runtime, value: runtime.set_precipitation_skip_mm(value),
    ),
    GardenThresholdDescription(
        key="weather_humidity_skip_percent",
        name="Weather humidity skip threshold",
        icon="mdi:water-percent",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda runtime: runtime.state.humidity_skip_percent,
        set_fn=lambda runtime, value: runtime.set_humidity_skip_percent(value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Garden Irrigation number entities."""
    runtime: GardenIrrigationRuntime = entry.runtime_data
    entities: list[NumberEntity] = [
        GardenWeatherThresholdNumber(runtime, description)
        for description in THRESHOLD_DESCRIPTIONS
    ]
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


class GardenWeatherThresholdNumber(
    GardenIrrigationEntity,
    NumberEntity,
    RestoreEntity,
):
    """Home Assistant-owned weather guard threshold."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = "slider"

    def __init__(
        self,
        runtime: GardenIrrigationRuntime,
        description: GardenThresholdDescription,
    ) -> None:
        """Initialize a weather guard threshold."""
        super().__init__(runtime, description.key)
        self.description = description
        self._attr_name = description.name
        self._attr_icon = description.icon
        self._attr_native_min_value = description.native_min_value
        self._attr_native_max_value = description.native_max_value
        self._attr_native_step = description.native_step
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement

    @property
    def available(self) -> bool:
        """Return whether the HA-owned setting is available."""
        return True

    @property
    def native_value(self) -> float:
        """Return the current threshold value."""
        return self.description.value_fn(self.runtime)

    async def async_added_to_hass(self) -> None:
        """Restore the threshold after Home Assistant restart."""
        await GardenIrrigationEntity.async_added_to_hass(self)
        last_state = await self.async_get_last_state()
        if last_state is None or last_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return
        try:
            value = float(last_state.state)
        except ValueError:
            return
        try:
            self.description.set_fn(self.runtime, value)
        except ProtocolError:
            return

    async def async_set_native_value(self, value: float) -> None:
        """Set the threshold value."""
        self.description.set_fn(self.runtime, value)
