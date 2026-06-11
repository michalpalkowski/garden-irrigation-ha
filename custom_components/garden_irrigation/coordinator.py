"""Runtime MQTT coordinator for Garden Irrigation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback

from .const import (
    CONF_BASE_TOPIC,
    CONF_DEVICE_ID,
    DEFAULT_MANUAL_DURATION_MINUTES,
    DEFAULT_ZONE_COUNT,
)
from . import protocol

_LOGGER = logging.getLogger(__name__)


@dataclass
class GardenZoneState:
    """In-memory state for one irrigation zone."""

    state: protocol.ZoneState | None = None
    duration_minutes: int = DEFAULT_MANUAL_DURATION_MINUTES
    run_seconds: int | None = None


@dataclass
class GardenControllerState:
    """In-memory state for one controller."""

    availability: protocol.Availability | None = None
    controller_state: str | None = None
    diagnostics: str | None = None
    zones: dict[int, GardenZoneState] = field(
        default_factory=lambda: {
            zone: GardenZoneState() for zone in range(DEFAULT_ZONE_COUNT)
        }
    )


class GardenIrrigationRuntime:
    """Own MQTT subscriptions, state, and command publishing for one entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize runtime state."""
        self.hass = hass
        self.entry = entry
        self.base_topic = protocol.normalize_base_topic(entry.data[CONF_BASE_TOPIC])
        self.device_id = entry.data[CONF_DEVICE_ID]
        self.state = GardenControllerState()
        self._listeners: list[Callable[[], None]] = []
        self._unsubscribers: list[CALLBACK_TYPE] = []

    async def async_start(self) -> None:
        """Subscribe to controller MQTT topics."""
        await mqtt.async_wait_for_mqtt_client(self.hass)

        topics = [
            protocol.availability_topic(self.base_topic),
            protocol.state_topic(self.base_topic),
            protocol.diagnostics_topic(self.base_topic),
        ]
        for zone in range(DEFAULT_ZONE_COUNT):
            topics.extend(
                [
                    protocol.zone_state_topic(self.base_topic, zone),
                    protocol.zone_run_seconds_topic(self.base_topic, zone),
                ]
            )

        for topic in topics:
            unsub = await mqtt.async_subscribe(
                self.hass,
                topic,
                self._handle_mqtt_message,
                qos=0,
            )
            self._unsubscribers.append(unsub)

    async def async_stop(self) -> None:
        """Unsubscribe from MQTT topics."""
        while self._unsubscribers:
            self._unsubscribers.pop()()
        self._listeners.clear()

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        """Register an entity update listener."""
        self._listeners.append(listener)

        @callback
        def _remove_listener() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return _remove_listener

    @property
    def available(self) -> bool:
        """Return whether the controller is online."""
        return self.state.availability == protocol.Availability.ONLINE

    async def async_start_zone(self, zone: int, duration_seconds: int) -> None:
        """Publish a safe bounded zone start command."""
        await self._async_publish(
            protocol.start_zone_publish(self.base_topic, zone, duration_seconds)
        )

    async def async_stop_zone(self, zone: int) -> None:
        """Publish a safe zone stop command."""
        await self._async_publish(protocol.stop_zone_publish(self.base_topic, zone))

    async def async_stop_all(self) -> None:
        """Publish a safe stop-all command."""
        await self._async_publish(protocol.stop_all_publish(self.base_topic))

    async def async_set_duration_minutes(self, zone: int, minutes: int) -> None:
        """Set the Home Assistant manual start duration for one zone."""
        self.set_duration_minutes(zone, minutes)

    @callback
    def set_duration_minutes(self, zone: int, minutes: int) -> None:
        """Set the local manual start duration for one zone."""
        zone = protocol.validate_zone(zone)
        self.state.zones[zone].duration_minutes = protocol.validate_duration_minutes(
            minutes
        )
        self._async_notify_listeners()

    async def _async_publish(self, publish: tuple[str, str, int, bool]) -> None:
        topic, payload, qos, retain = publish
        await mqtt.async_publish(self.hass, topic, payload, qos=qos, retain=retain)

    @callback
    def _handle_mqtt_message(self, message: Any) -> None:
        topic = message.topic
        payload = str(message.payload)

        try:
            if topic == protocol.availability_topic(self.base_topic):
                self.state.availability = protocol.parse_availability(payload)
            elif topic == protocol.state_topic(self.base_topic):
                self.state.controller_state = payload
            elif topic == protocol.diagnostics_topic(self.base_topic):
                self.state.diagnostics = payload
            else:
                self._handle_zone_message(topic, payload)
        except protocol.ProtocolError as exc:
            _LOGGER.warning(
                "Ignoring invalid Garden Irrigation MQTT payload on %s: %s",
                topic,
                exc,
            )
            return

        self._async_notify_listeners()

    @callback
    def _handle_zone_message(self, topic: str, payload: str) -> None:
        for zone in range(DEFAULT_ZONE_COUNT):
            zone_state = self.state.zones[zone]
            if topic == protocol.zone_state_topic(self.base_topic, zone):
                zone_state.state = protocol.parse_zone_state(payload)
                return
            if topic == protocol.zone_run_seconds_topic(self.base_topic, zone):
                zone_state.run_seconds = protocol.parse_run_seconds(payload)
                return
        raise protocol.ProtocolError("unexpected topic")

    @callback
    def _async_notify_listeners(self) -> None:
        for listener in list(self._listeners):
            listener()
