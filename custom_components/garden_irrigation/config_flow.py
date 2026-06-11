"""Config flow for Garden Irrigation."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo

from .const import (
    CONF_BASE_TOPIC,
    CONF_BOARD,
    CONF_CHIP,
    CONF_DEVICE_ID,
    CONF_PROTOCOL_SCHEMA,
    CONF_WEATHER_ENTITY,
    DOMAIN,
)
from .protocol import (
    DeviceIdentity,
    ProtocolError,
    base_topic_from_device_id,
    normalize_base_topic,
    normalize_device_id,
)
from . import protocol

MQTT_VALIDATE_TIMEOUT_SECONDS = 5


class GardenIrrigationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Garden Irrigation config flow."""

    VERSION = 1
    _discovered_identity: DeviceIdentity | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> GardenIrrigationOptionsFlow:
        """Create the options flow."""
        return GardenIrrigationOptionsFlow(config_entry)

    async def async_step_mqtt(
        self, discovery_info: MqttServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by MQTT identity discovery."""
        try:
            identity = protocol.parse_identity_payload(
                _identity_payload_from_mqtt(discovery_info.payload)
            )
        except ProtocolError:
            return self.async_abort(reason="invalid_discovery_payload")

        await self.async_set_unique_id(identity.device_id)
        self._abort_if_unique_id_configured()

        self._discovered_identity = identity
        self.context["title_placeholders"] = {"name": identity.device_id}
        return self.async_show_form(
            step_id="mqtt_confirm",
            data_schema=vol.Schema({}),
            description_placeholders={
                CONF_DEVICE_ID: identity.device_id,
                CONF_BASE_TOPIC: identity.base_topic,
                CONF_BOARD: identity.board,
                CONF_CHIP: identity.chip,
            },
        )

    async def async_step_mqtt_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm a controller discovered from retained MQTT identity."""
        identity = self._discovered_identity
        if identity is None:
            return self.async_abort(reason="discovery_expired")

        if user_input is None:
            return self.async_show_form(
                step_id="mqtt_confirm",
                data_schema=vol.Schema({}),
                description_placeholders={
                    CONF_DEVICE_ID: identity.device_id,
                    CONF_BASE_TOPIC: identity.base_topic,
                    CONF_BOARD: identity.board,
                    CONF_CHIP: identity.chip,
                },
            )

        await self.async_set_unique_id(identity.device_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=identity.device_id,
            data=_entry_data_from_identity(identity),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle manual setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                device_id = normalize_device_id(user_input[CONF_DEVICE_ID])
                base_topic = normalize_base_topic(
                    user_input.get(CONF_BASE_TOPIC)
                    or base_topic_from_device_id(device_id)
                )
            except (KeyError, ProtocolError):
                errors["base"] = "invalid_controller"
            else:
                identity = await _async_read_controller_identity(self.hass, base_topic)
                if identity is None:
                    errors["base"] = "controller_not_found"
                elif identity.device_id != device_id:
                    errors["base"] = "identity_mismatch"
                elif identity.base_topic != base_topic:
                    errors["base"] = "identity_mismatch"
                else:
                    await self.async_set_unique_id(device_id)
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=device_id,
                        data=_entry_data_from_identity(identity),
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ID): str,
                    vol.Optional(CONF_BASE_TOPIC): str,
                }
            ),
            errors=errors,
        )


async def _async_read_controller_identity(
    hass: Any, base_topic: str
) -> DeviceIdentity | None:
    """Read and validate the retained controller identity for a base topic."""
    await mqtt.async_wait_for_mqtt_client(hass)
    loop = asyncio.get_running_loop()
    done: asyncio.Future[DeviceIdentity] = loop.create_future()
    unsubscribe = None

    def _handle_identity(message: Any) -> None:
        try:
            identity = protocol.parse_identity_payload(
                _identity_payload_from_mqtt(message.payload)
            )
        except ProtocolError:
            return

        if identity.base_topic == base_topic and not done.done():
            done.set_result(identity)

    try:
        unsubscribe = await mqtt.async_subscribe(
            hass,
            protocol.runtime_identity_topic(base_topic),
            _handle_identity,
            qos=0,
        )
        return await asyncio.wait_for(done, timeout=MQTT_VALIDATE_TIMEOUT_SECONDS)
    except TimeoutError:
        return None
    finally:
        if unsubscribe is not None:
            unsubscribe()


def _identity_payload_from_mqtt(payload: Any) -> dict[str, object]:
    """Decode an MQTT payload into an identity JSON object."""
    try:
        if isinstance(payload, dict):
            data = payload
        elif isinstance(payload, bytes | bytearray):
            data = json.loads(bytes(payload).decode())
        elif isinstance(payload, str):
            data = json.loads(payload)
        else:
            raise ProtocolError("MQTT identity payload must be JSON")
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ProtocolError("MQTT identity payload must be valid JSON") from error

    if not isinstance(data, dict):
        raise ProtocolError("MQTT identity payload must be an object")
    return data


def _entry_data_from_identity(identity: DeviceIdentity) -> dict[str, str]:
    """Build stable config entry data from a validated controller identity."""
    return {
        CONF_BASE_TOPIC: identity.base_topic,
        CONF_DEVICE_ID: identity.device_id,
        CONF_PROTOCOL_SCHEMA: identity.protocol_schema,
        CONF_BOARD: identity.board,
        CONF_CHIP: identity.chip,
    }


class GardenIrrigationOptionsFlow(config_entries.OptionsFlow):
    """Handle Garden Irrigation options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Configure weather guard options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            weather_entity = str(user_input.get(CONF_WEATHER_ENTITY, "")).strip()
            if weather_entity and not weather_entity.startswith("weather."):
                errors[CONF_WEATHER_ENTITY] = "invalid_weather_entity"
            else:
                return self.async_create_entry(
                    title="",
                    data={CONF_WEATHER_ENTITY: weather_entity},
                )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_WEATHER_ENTITY,
                        default=self.config_entry.options.get(CONF_WEATHER_ENTITY, ""),
                    ): str,
                }
            ),
            errors=errors,
        )
