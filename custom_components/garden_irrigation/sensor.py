"""Sensor entities for Garden Irrigation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DEFAULT_ZONE_COUNT
from .coordinator import GardenIrrigationRuntime
from .entity import GardenIrrigationEntity
from .protocol import wifi_quality_percent, wifi_status_label


@dataclass(frozen=True)
class GardenSensorDescription:
    """Description for a Garden Irrigation sensor."""

    key: str
    name: str
    value_fn: Callable[[GardenIrrigationRuntime], str | int | float | None]
    attrs_fn: Callable[[GardenIrrigationRuntime], dict[str, Any]] | None = None
    icon: str | None = None
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    entity_category: EntityCategory | None = None
    always_available: bool = False


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
        GardenRuntimeSensor(
            runtime,
            GardenSensorDescription(
                key="network_status",
                name="Network status",
                value_fn=_network_status_value,
                attrs_fn=lambda item: item.state.network_status or {},
                icon="mdi:lan-connect",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        ),
        GardenRuntimeSensor(
            runtime,
            GardenSensorDescription(
                key="wifi_signal",
                name="Wi-Fi signal",
                value_fn=lambda item: item.state.wifi_rssi,
                icon="mdi:wifi",
                unit="dBm",
                device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        ),
        GardenRuntimeSensor(
            runtime,
            GardenSensorDescription(
                key="wifi_quality",
                name="Wi-Fi quality",
                value_fn=lambda item: (
                    wifi_quality_percent(item.state.wifi_rssi)
                    if item.state.wifi_rssi is not None
                    else None
                ),
                attrs_fn=lambda item: {
                    "rssi_dbm": item.state.wifi_rssi,
                    "quality_label": wifi_status_label(item.state.wifi_rssi)
                    if item.state.wifi_rssi is not None
                    else None,
                },
                icon="mdi:wifi-strength-3",
                unit=PERCENTAGE,
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        ),
        GardenRuntimeSensor(
            runtime,
            GardenSensorDescription(
                key="wifi_status",
                name="Wi-Fi status",
                value_fn=lambda item: (
                    wifi_status_label(item.state.wifi_rssi)
                    if item.state.wifi_rssi is not None
                    else None
                ),
                attrs_fn=lambda item: {
                    "rssi_dbm": item.state.wifi_rssi,
                    "quality_percent": wifi_quality_percent(item.state.wifi_rssi)
                    if item.state.wifi_rssi is not None
                    else None,
                },
                icon="mdi:wifi",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        ),
        GardenRuntimeSensor(
            runtime,
            GardenSensorDescription(
                key="automation_decision",
                name="Automation decision",
                value_fn=lambda item: item.state.last_weather_decision.state.value,
                attrs_fn=lambda item: item.state.last_weather_decision.attributes
                | {"reason": item.state.last_weather_decision.reason},
                icon="mdi:robot-outline",
                always_available=True,
            ),
        ),
        GardenRuntimeSensor(
            runtime,
            GardenSensorDescription(
                key="next_watering",
                name="Next watering",
                value_fn=lambda item: item.next_watering_state(dt_util.now()),
                attrs_fn=lambda item: item.next_watering_attributes(dt_util.now()),
                icon="mdi:calendar-clock",
                always_available=True,
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
                        device_class=SensorDeviceClass.DURATION,
                        state_class=SensorStateClass.TOTAL_INCREASING,
                    ),
                ),
                GardenRuntimeSensor(
                    runtime,
                    GardenSensorDescription(
                        key=f"zone_{zone}_run_minutes",
                        name=f"Zone {zone} run minutes",
                        value_fn=lambda item, zone=zone: (
                            round(item.state.zones[zone].run_seconds / 60, 3)
                            if item.state.zones[zone].run_seconds is not None
                            else None
                        ),
                        icon="mdi:timer-outline",
                        unit=UnitOfTime.MINUTES,
                        device_class=SensorDeviceClass.DURATION,
                        state_class=SensorStateClass.TOTAL_INCREASING,
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
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        self._attr_entity_category = description.entity_category

    @property
    def available(self) -> bool:
        """Return entity availability."""
        if self.entity_description.always_available:
            return True
        return super().available

    @property
    def native_value(self) -> str | int | float | None:
        """Return the current sensor value."""
        return self.entity_description.value_fn(self.runtime)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional dashboard attributes."""
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.runtime)


def _network_status_value(runtime: GardenIrrigationRuntime) -> str | None:
    """Return a compact network status state."""
    status = runtime.state.network_status
    if status is None:
        return None
    for key in ("reason", "phase", "status"):
        value = status.get(key)
        if isinstance(value, str) and value:
            return value
    return "online"
