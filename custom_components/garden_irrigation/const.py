"""Constants for the Garden Irrigation integration."""

from __future__ import annotations

from datetime import time

DOMAIN = "garden_irrigation"
DATA_RUNTIMES = "runtimes"
DATA_OTA_ARTIFACTS = "ota_artifacts"
DATA_OTA_VIEW_REGISTERED = "ota_view_registered"
PLATFORMS = [
    "binary_sensor",
    "button",
    "number",
    "sensor",
    "switch",
    "time",
    "update",
]

CONF_BASE_TOPIC = "base_topic"
CONF_DEVICE_ID = "device_id"
CONF_PROTOCOL_SCHEMA = "protocol_schema"
CONF_BOARD = "board"
CONF_CHIP = "chip"
CONF_WEATHER_ENTITY = "weather_entity"
CONF_OTA_MANIFEST_URL = "ota_manifest_url"
CONF_OTA_GITHUB_REPOSITORY = "ota_github_repository"
CONF_OTA_GITHUB_TOKEN = "ota_github_token"

DEFAULT_DEVICE_ID = "xiao-esp32c6-1"
DEFAULT_PROTOCOL_SCHEMA = "garden-irrigation-mqtt/v1"
DEFAULT_BOARD = "xiao-esp32c6"
DEFAULT_CHIP = "esp32c6"
DEFAULT_ZONE_COUNT = 4
DEFAULT_MANUAL_DURATION_MINUTES = 15
DEFAULT_SCHEDULED_DURATION_MINUTES = 15
DEFAULT_SCHEDULE_TIME = time(20, 0)
DEFAULT_RAIN_PROBABILITY_SKIP_PERCENT = 35
DEFAULT_PRECIPITATION_SKIP_MM = 0.1
DEFAULT_HUMIDITY_SKIP_PERCENT = 80
DEFAULT_RAIN_LOOKAHEAD_HOURS = 24
DEFAULT_OTA_GITHUB_REPOSITORY = "michalpalkowski/garden-irrigation-firmware"
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
