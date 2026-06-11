"""Constants for the Garden Irrigation integration."""

from __future__ import annotations

DOMAIN = "garden_irrigation"
PLATFORMS = ["button", "number", "sensor", "switch"]

CONF_BASE_TOPIC = "base_topic"
CONF_DEVICE_ID = "device_id"
CONF_PROTOCOL_SCHEMA = "protocol_schema"
CONF_BOARD = "board"
CONF_CHIP = "chip"

DEFAULT_DEVICE_ID = "garden-irrigation-wifi"
DEFAULT_PROTOCOL_SCHEMA = "garden-irrigation-mqtt/v1"
DEFAULT_BOARD = "xiao-esp32c6"
DEFAULT_CHIP = "esp32c6"
DEFAULT_ZONE_COUNT = 4

MANUFACTURER = "home-automations"
MODEL = "Garden Irrigation Wi-Fi"
