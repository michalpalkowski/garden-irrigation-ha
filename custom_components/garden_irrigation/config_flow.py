"""Config flow for Garden Irrigation."""

from __future__ import annotations

import asyncio
from typing import Any

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant import config_entries

from .const import (
    CONF_BASE_TOPIC,
    CONF_BOARD,
    CONF_CHIP,
    CONF_DEVICE_ID,
    CONF_PROTOCOL_SCHEMA,
    DEFAULT_BOARD,
    DEFAULT_CHIP,
    DEFAULT_DEVICE_ID,
    DEFAULT_PROTOCOL_SCHEMA,
    DOMAIN,
)
from .protocol import ProtocolError, normalize_base_topic
from . import protocol

MQTT_VALIDATE_TIMEOUT_SECONDS = 5


class GardenIrrigationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Garden Irrigation config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle manual setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                base_topic = normalize_base_topic(user_input[CONF_BASE_TOPIC])
            except (KeyError, ProtocolError):
                errors[CONF_BASE_TOPIC] = "invalid_base_topic"
            else:
                valid = await _async_validate_controller_topic(self.hass, base_topic)
                if not valid:
                    errors["base"] = "controller_not_found"
                else:
                    device_id = user_input.get(CONF_DEVICE_ID) or DEFAULT_DEVICE_ID
                    await self.async_set_unique_id(device_id)
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=device_id,
                        data={
                            CONF_BASE_TOPIC: base_topic,
                            CONF_DEVICE_ID: device_id,
                            CONF_PROTOCOL_SCHEMA: DEFAULT_PROTOCOL_SCHEMA,
                            CONF_BOARD: DEFAULT_BOARD,
                            CONF_CHIP: DEFAULT_CHIP,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BASE_TOPIC): str,
                    vol.Optional(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID): str,
                }
            ),
            errors=errors,
        )


async def _async_validate_controller_topic(hass: Any, base_topic: str) -> bool:
    """Validate that the MQTT base topic looks like a live Garden controller."""
    await mqtt.async_wait_for_mqtt_client(hass)
    loop = asyncio.get_running_loop()
    done: asyncio.Future[bool] = loop.create_future()
    seen: dict[str, bool] = {
        "availability": False,
        "state": False,
        "duration": False,
    }
    unsubscribers = []

    def _maybe_done() -> None:
        if all(seen.values()) and not done.done():
            done.set_result(True)

    def _handle_availability(message: Any) -> None:
        try:
            protocol.parse_availability(str(message.payload))
        except ProtocolError:
            return
        seen["availability"] = True
        _maybe_done()

    def _handle_state(message: Any) -> None:
        if str(message.payload).strip():
            seen["state"] = True
            _maybe_done()

    def _handle_duration(message: Any) -> None:
        try:
            protocol.parse_duration_minutes(str(message.payload))
        except ProtocolError:
            return
        seen["duration"] = True
        _maybe_done()

    try:
        unsubscribers.append(
            await mqtt.async_subscribe(
                hass,
                protocol.availability_topic(base_topic),
                _handle_availability,
                qos=0,
            )
        )
        unsubscribers.append(
            await mqtt.async_subscribe(
                hass,
                protocol.state_topic(base_topic),
                _handle_state,
                qos=0,
            )
        )
        unsubscribers.append(
            await mqtt.async_subscribe(
                hass,
                protocol.zone_duration_state_topic(base_topic, 0),
                _handle_duration,
                qos=0,
            )
        )
        return await asyncio.wait_for(done, timeout=MQTT_VALIDATE_TIMEOUT_SECONDS)
    except TimeoutError:
        return False
    finally:
        for unsubscribe in unsubscribers:
            unsubscribe()
