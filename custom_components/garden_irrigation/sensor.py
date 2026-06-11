"""Sensor entities for Garden Irrigation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_ZONE_COUNT
from .coordinator import GardenIrrigationRuntime
from .entity import GardenIrrigationEntity


@dataclass(frozen=True)
class GardenSensorDescription:
    """Description for a Garden Irrigation sensor."""

    key: str
    name: str
    value_fn: Callable[[GardenIrrigationRuntime], str | int | None]
    icon: str | None = None
    unit: str | None = None
    entity_category: EntityCategory | None = None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Garden Irrigation sensor entities."""
    runtime: GardenIrrigationRuntime = entry.runtime_data
    entities: list[SensorEntity] = [
        GardenRuntimeSensor(
            runtime,
            GardenSensorDescription(
                key="controller_state",
                name="Controller state",
                value_fn=lambda item: item.state.controller_state,
                icon="mdi:sprinkler",
            ),
        ),
        GardenRuntimeSensor(
            runtime,
            GardenSensorDescription(
                key="diagnostics",
                name="Diagnostics",
                value_fn=lambda item: item.state.diagnostics,
                icon="mdi:message-alert-outline",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        ),
    ]

    for zone in range(DEFAULT_ZONE_COUNT):
        entities.extend(
            [
                GardenRuntimeSensor(
                    runtime,
                    GardenSensorDescription(
                        key=f"zone_{zone}_state",
                        name=f"Zone {zone} state",
                        value_fn=lambda item, zone=zone: (
                            item.state.zones[zone].state.value
                            if item.state.zones[zone].state is not None
                            else None
                        ),
                        icon="mdi:valve",
                    ),
                ),
                GardenRuntimeSensor(
                    runtime,
                    GardenSensorDescription(
                        key=f"zone_{zone}_run_seconds",
                        name=f"Zone {zone} run seconds",
                        value_fn=lambda item, zone=zone: item.state.zones[
                            zone
                        ].run_seconds,
                        icon="mdi:timer-sync-outline",
                        unit=UnitOfTime.SECONDS,
                    ),
                ),
            ]
        )

    async_add_entities(entities)


class GardenRuntimeSensor(GardenIrrigationEntity, SensorEntity):
    """Sensor backed by coordinator memory."""

    def __init__(
        self,
        runtime: GardenIrrigationRuntime,
        description: GardenSensorDescription,
    ) -> None:
        """Initialize a runtime sensor."""
        super().__init__(runtime, description.key)
        self.entity_description = description
        self._attr_name = description.name
        self._attr_icon = description.icon
        self._attr_native_unit_of_measurement = description.unit
        self._attr_entity_category = description.entity_category

    @property
    def native_value(self) -> str | int | None:
        """Return the current sensor value."""
        return self.entity_description.value_fn(self.runtime)
