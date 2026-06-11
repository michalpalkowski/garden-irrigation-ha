"""Runtime MQTT coordinator for Garden Irrigation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import datetime as dt
import logging
from typing import Any

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_BASE_TOPIC,
    CONF_DEVICE_ID,
    DEFAULT_MANUAL_DURATION_MINUTES,
    DEFAULT_SCHEDULE_TIME,
    DEFAULT_SCHEDULED_DURATION_MINUTES,
    DEFAULT_ZONE_COUNT,
    WEEKDAYS,
)
from . import protocol

_LOGGER = logging.getLogger(__name__)


@dataclass
class GardenZoneState:
    """In-memory state for one irrigation zone."""

    state: protocol.ZoneState | None = None
    manual_duration_minutes: int = DEFAULT_MANUAL_DURATION_MINUTES
    scheduled_duration_minutes: int = DEFAULT_SCHEDULED_DURATION_MINUTES
    schedule_enabled: bool = False
    schedule_time: dt.time = DEFAULT_SCHEDULE_TIME
    schedule_weekdays: dict[int, bool] = field(
        default_factory=lambda: {weekday: False for weekday, _, _ in WEEKDAYS}
    )
    run_seconds: int | None = None


@dataclass
class GardenControllerState:
    """In-memory state for one controller."""

    availability: protocol.Availability | None = None
    controller_state: str | None = None
    diagnostics: str | None = None
    network_status: dict[str, Any] | None = None
    wifi_rssi: int | None = None
    zones: dict[int, GardenZoneState] = field(
        default_factory=lambda: {
            zone: GardenZoneState() for zone in range(DEFAULT_ZONE_COUNT)
        }
    )
    schedule_run_keys: set[str] = field(default_factory=set)


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
        self._unsub_schedule: CALLBACK_TYPE | None = None

    async def async_start(self) -> None:
        """Subscribe to controller MQTT topics."""
        await mqtt.async_wait_for_mqtt_client(self.hass)

        topics = [
            protocol.availability_topic(self.base_topic),
            protocol.state_topic(self.base_topic),
            protocol.diagnostics_topic(self.base_topic),
            protocol.network_status_topic(self.base_topic),
            protocol.wifi_signal_topic(self.base_topic),
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

        self._unsub_schedule = async_track_time_interval(
            self.hass,
            self._handle_schedule_tick,
            dt.timedelta(seconds=30),
        )

    async def async_stop(self) -> None:
        """Unsubscribe from MQTT topics."""
        if self._unsub_schedule is not None:
            self._unsub_schedule()
            self._unsub_schedule = None
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
        self.set_manual_duration_minutes(zone, minutes)

    @callback
    def set_manual_duration_minutes(self, zone: int, minutes: int) -> None:
        """Set the local manual start duration for one zone."""
        zone = protocol.validate_zone(zone)
        self.state.zones[zone].manual_duration_minutes = (
            protocol.validate_duration_minutes(minutes)
        )
        self._async_notify_listeners()

    @callback
    def set_scheduled_duration_minutes(self, zone: int, minutes: int) -> None:
        """Set the local scheduled start duration for one zone."""
        zone = protocol.validate_zone(zone)
        self.state.zones[zone].scheduled_duration_minutes = (
            protocol.validate_duration_minutes(minutes)
        )
        self._async_notify_listeners()

    @callback
    def set_schedule_enabled(self, zone: int, enabled: bool) -> None:
        """Enable or disable the local schedule for one zone."""
        zone = protocol.validate_zone(zone)
        self.state.zones[zone].schedule_enabled = enabled
        self._async_notify_listeners()

    @callback
    def set_schedule_weekday(self, zone: int, weekday: int, enabled: bool) -> None:
        """Enable or disable one scheduled weekday for one zone."""
        zone = protocol.validate_zone(zone)
        if weekday not in self.state.zones[zone].schedule_weekdays:
            raise protocol.ProtocolError("invalid weekday")
        self.state.zones[zone].schedule_weekdays[weekday] = enabled
        self._async_notify_listeners()

    @callback
    def set_schedule_time(self, zone: int, value: dt.time) -> None:
        """Set the local scheduled start time for one zone."""
        zone = protocol.validate_zone(zone)
        self.state.zones[zone].schedule_time = value.replace(
            second=0,
            microsecond=0,
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
            elif topic == protocol.network_status_topic(self.base_topic):
                self.state.network_status = protocol.parse_network_status(payload)
            elif topic == protocol.wifi_signal_topic(self.base_topic):
                self.state.wifi_rssi = protocol.parse_wifi_rssi(payload)
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
    def _handle_schedule_tick(self, now: dt.datetime) -> None:
        """Schedule async irrigation checks from the HA event loop."""
        self.hass.async_create_task(self.async_check_schedule(now))

    async def async_check_schedule(self, now: dt.datetime) -> None:
        """Run due local schedules once per date, zone, and minute."""
        self._prune_schedule_run_keys(now.date())
        for zone, zone_state in self.state.zones.items():
            scheduled_time = zone_state.schedule_time
            if (
                not zone_state.schedule_enabled
                or not zone_state.schedule_weekdays.get(now.weekday(), False)
                or scheduled_time.hour != now.hour
                or scheduled_time.minute != now.minute
            ):
                continue

            run_key = (
                f"{now.date().isoformat()}:{zone}:"
                f"{now.hour:02d}:{now.minute:02d}"
            )
            if run_key in self.state.schedule_run_keys:
                continue

            self.state.schedule_run_keys.add(run_key)
            await self.async_start_zone(
                zone,
                zone_state.scheduled_duration_minutes * 60,
            )

    @callback
    def _prune_schedule_run_keys(self, today: dt.date) -> None:
        """Keep only today's schedule dedupe keys."""
        today_prefix = today.isoformat()
        self.state.schedule_run_keys = {
            key for key in self.state.schedule_run_keys if key.startswith(today_prefix)
        }

    def next_watering_state(self, now: dt.datetime) -> str:
        """Return a compact state for the next watering sensor."""
        return "scheduled" if self._next_scheduled_zone(now) is not None else "disabled"

    def next_watering_attributes(self, now: dt.datetime) -> dict[str, Any]:
        """Return dashboard-friendly schedule attributes."""
        next_item = self._next_scheduled_zone(now)
        active_zones = [
            f"Zone {zone}"
            for zone, zone_state in self.state.zones.items()
            if zone_state.schedule_enabled
        ]
        total_duration = sum(
            zone_state.scheduled_duration_minutes
            for zone_state in self.state.zones.values()
            if zone_state.schedule_enabled
        )
        attrs: dict[str, Any] = {
            "active_zones": ", ".join(active_zones) if active_zones else "none",
            "total_duration_minutes": total_duration,
            "reason": "Schedules are disabled."
            if next_item is None
            else "Next enabled zone schedule is ready.",
        }
        if next_item is not None:
            zone, scheduled_at = next_item
            attrs["next_zone"] = zone
            attrs["scheduled_at"] = scheduled_at.isoformat(timespec="minutes")
        else:
            attrs["scheduled_at"] = "none"
        return attrs

    def _next_scheduled_zone(self, now: dt.datetime) -> tuple[int, dt.datetime] | None:
        """Find the next enabled scheduled zone within the next seven days."""
        candidates: list[tuple[dt.datetime, int]] = []
        for day_offset in range(8):
            day = now.date() + dt.timedelta(days=day_offset)
            weekday = day.weekday()
            for zone, zone_state in self.state.zones.items():
                if not zone_state.schedule_enabled:
                    continue
                if not zone_state.schedule_weekdays.get(weekday, False):
                    continue
                scheduled_at = dt.datetime.combine(
                    day,
                    zone_state.schedule_time,
                    tzinfo=now.tzinfo,
                )
                if scheduled_at >= now.replace(second=0, microsecond=0):
                    candidates.append((scheduled_at, zone))
        if not candidates:
            return None
        scheduled_at, zone = min(candidates)
        return zone, scheduled_at

    @callback
    def _async_notify_listeners(self) -> None:
        for listener in list(self._listeners):
            listener()
