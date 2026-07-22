"""Sensor entities for Garden Irrigation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime as dt
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
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


@dataclass(frozen=True, kw_only=True)
class GardenSensorDescription(SensorEntityDescription):
    """Description for a Garden Irrigation sensor."""

    value_fn: Callable[
        [GardenIrrigationRuntime], str | int | float | dt.datetime | None
    ]
    attrs_fn: Callable[[GardenIrrigationRuntime], dict[str, Any]] | None = None
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
                value_fn=_network_status_compact_value,
                attrs_fn=lambda item: (
                    item.state.network_status.as_dict()
                    if item.state.network_status is not None
                    else {}
                ),
                icon="mdi:lan-connect",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        ),
        GardenRuntimeSensor(
            runtime,
            GardenSensorDescription(
                key="reset_reason",
                name="Reset reason",
                value_fn=lambda item: _network_status_text_value(
                    item, "reset_reason"
                ),
                icon="mdi:restart-alert",
                entity_category=EntityCategory.DIAGNOSTIC,
                always_available=True,
            ),
        ),
        GardenRuntimeSensor(
            runtime,
            GardenSensorDescription(
                key="watchdog_report",
                name="Watchdog report",
                value_fn=_watchdog_report_value,
                attrs_fn=_watchdog_report_attributes,
                icon="mdi:timer-alert-outline",
                entity_category=EntityCategory.DIAGNOSTIC,
                always_available=True,
            ),
        ),
        GardenRuntimeSensor(
            runtime,
            GardenSensorDescription(
                key="telemetry_last_seen",
                name="Telemetry last seen",
                value_fn=lambda item: item.state.network_status_received_at,
                icon="mdi:clock-check-outline",
                device_class=SensorDeviceClass.TIMESTAMP,
                entity_category=EntityCategory.DIAGNOSTIC,
                always_available=True,
            ),
        ),
        GardenRuntimeSensor(
            runtime,
            GardenSensorDescription(
                key="telemetry_age_seconds",
                name="Telemetry age",
                value_fn=_telemetry_age_seconds,
                icon="mdi:timer-alert-outline",
                native_unit_of_measurement="s",
                device_class=SensorDeviceClass.DURATION,
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
                always_available=True,
            ),
        ),
        GardenRuntimeSensor(
            runtime,
            GardenSensorDescription(
                key="last_outage_cause",
                name="Last outage cause",
                value_fn=lambda item: (
                    item.state.last_outage.cause.value
                    if item.state.last_outage is not None
                    else None
                ),
                attrs_fn=lambda item: (
                    item.state.last_outage.as_attributes()
                    if item.state.last_outage is not None
                    else {}
                ),
                icon="mdi:alert-decagram-outline",
                entity_category=EntityCategory.DIAGNOSTIC,
                always_available=True,
            ),
        ),
        GardenRuntimeSensor(
            runtime,
            GardenSensorDescription(
                key="free_heap_bytes",
                name="Free heap",
                value_fn=lambda item: _network_status_int(item, "free_heap_bytes"),
                icon="mdi:memory",
                native_unit_of_measurement="B",
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
                always_available=True,
            ),
        ),
        GardenRuntimeSensor(
            runtime,
            GardenSensorDescription(
                key="min_free_heap_bytes",
                name="Min free heap",
                value_fn=lambda item: _network_status_int(
                    item, "min_free_heap_bytes"
                ),
                icon="mdi:memory",
                native_unit_of_measurement="B",
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
                always_available=True,
            ),
        ),
        GardenRuntimeSensor(
            runtime,
            GardenSensorDescription(
                key="heap_used_bytes",
                name="Heap used",
                value_fn=lambda item: _network_status_int(item, "heap_used_bytes"),
                icon="mdi:memory",
                native_unit_of_measurement="B",
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
                always_available=True,
            ),
        ),
        GardenRuntimeSensor(
            runtime,
            GardenSensorDescription(
                key="chip_temperature_celsius",
                name="Chip temperature",
                value_fn=lambda item: _network_status_int(
                    item, "chip_temperature_celsius"
                ),
                icon="mdi:thermometer",
                native_unit_of_measurement="°C",
                device_class=SensorDeviceClass.TEMPERATURE,
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
                always_available=True,
            ),
        ),
        GardenRuntimeSensor(
            runtime,
            GardenSensorDescription(
                key="wifi_signal",
                name="Wi-Fi signal",
                value_fn=lambda item: item.state.wifi_rssi,
                icon="mdi:wifi",
                native_unit_of_measurement="dBm",
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
                native_unit_of_measurement=PERCENTAGE,
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
                        native_unit_of_measurement=UnitOfTime.SECONDS,
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
                        native_unit_of_measurement=UnitOfTime.MINUTES,
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
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
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
    def native_value(self) -> str | int | float | dt.datetime | None:
        """Return the current sensor value."""
        return self.entity_description.value_fn(self.runtime)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional dashboard attributes."""
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.runtime)


def _network_status_compact_value(
    runtime: GardenIrrigationRuntime,
) -> str | None:
    """Return a compact network status state."""
    status = runtime.state.network_status
    if status is None:
        return None
    return status.reason or status.phase


def _network_status_text_value(
    runtime: GardenIrrigationRuntime, key: str
) -> str | None:
    """Return a named string value from the network status payload."""
    status = runtime.state.network_status
    if status is None:
        return None
    value = getattr(status, key, None)
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _network_status_int(runtime: GardenIrrigationRuntime, key: str) -> int | None:
    """Return a named integer value from the network status payload."""
    status = runtime.state.network_status
    if status is None:
        return None
    value = getattr(status, key, None)
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    return value


def _watchdog_report_value(runtime: GardenIrrigationRuntime) -> str | None:
    status = runtime.state.network_status
    if status is None or status.watchdog_report is None:
        return None
    report = status.watchdog_report
    return f"{report.task}:{report.operation}:{report.phase}"


def _watchdog_report_attributes(runtime: GardenIrrigationRuntime) -> dict[str, Any]:
    status = runtime.state.network_status
    if status is None or status.watchdog_report is None:
        return {}
    return status.watchdog_report.as_dict()


def _telemetry_age_seconds(runtime: GardenIrrigationRuntime) -> int | None:
    """Return age of the last validated network status sample."""
    received_at = runtime.state.network_status_received_at
    if received_at is None:
        return None
    return max(0, int((dt.datetime.now(dt.UTC) - received_at).total_seconds()))
