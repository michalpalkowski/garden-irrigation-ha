"""Shared entity helpers for Garden Irrigation."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import GardenIrrigationRuntime


class GardenIrrigationEntity(Entity):
    """Base class for Garden Irrigation entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, runtime: GardenIrrigationRuntime, key: str) -> None:
        """Initialize the entity."""
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.device_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, runtime.device_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=runtime.device_id,
        )

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self.runtime.available

    async def async_added_to_hass(self) -> None:
        """Subscribe entity to coordinator updates."""
        self.async_on_remove(
            self.runtime.async_add_listener(self.async_write_ha_state)
        )
