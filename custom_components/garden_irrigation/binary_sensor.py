"""Binary sensor entities for Garden Irrigation."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
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
    """Set up Garden Irrigation binary sensor entities."""
    runtime: GardenIrrigationRuntime = entry.runtime_data
    async_add_entities([GardenAvailabilityBinarySensor(runtime)])


class GardenAvailabilityBinarySensor(GardenIrrigationEntity, BinarySensorEntity):
    """Controller MQTT availability sensor."""

    _attr_name = "MQTT availability"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:cloud-check-outline"

    def __init__(self, runtime: GardenIrrigationRuntime) -> None:
        """Initialize the availability binary sensor."""
        super().__init__(runtime, "mqtt_availability")

    @property
    def available(self) -> bool:
        """Return whether this status entity is available."""
        return True

    @property
    def is_on(self) -> bool:
        """Return whether the controller is online in MQTT."""
        return self.runtime.available
