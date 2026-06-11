"""Constants for the Garden Irrigation integration."""

from __future__ import annotations

from datetime import time

DOMAIN = "garden_irrigation"
PLATFORMS = ["binary_sensor", "button", "number", "sensor", "switch", "time"]

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
DEFAULT_MANUAL_DURATION_MINUTES = 15
DEFAULT_SCHEDULED_DURATION_MINUTES = 15
DEFAULT_SCHEDULE_TIME = time(20, 0)
WEEKDAYS = (
    (0, "monday", "Monday"),
    (1, "tuesday", "Tuesday"),
    (2, "wednesday", "Wednesday"),
    (3, "thursday", "Thursday"),
    (4, "friday", "Friday"),
    (5, "saturday", "Saturday"),
    (6, "sunday", "Sunday"),
)

MANUFACTURER = "home-automations"
MODEL = "Garden Irrigation Wi-Fi"
