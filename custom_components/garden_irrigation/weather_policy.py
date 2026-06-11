"""Weather guard policy for Garden Irrigation schedules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class WeatherDecisionState(StrEnum):
    """Stable states exposed by the automation decision sensor."""

    ALLOWED = "allowed"
    WEATHER_POLICY_DISABLED = "weather_policy_disabled"
    WEATHER_UNAVAILABLE = "weather_unavailable"
    BLOCKED_BY_HUMIDITY = "blocked_by_humidity"
    BLOCKED_BY_FORECAST = "blocked_by_forecast"


@dataclass(frozen=True)
class WeatherThresholds:
    """User-configurable thresholds that can block scheduled watering."""

    rain_probability_skip_percent: float
    precipitation_skip_mm: float
    humidity_skip_percent: float
    rain_lookahead_hours: int


@dataclass(frozen=True)
class ForecastItem:
    """Small normalized weather forecast item."""

    condition: str | None = None
    precipitation_mm: float = 0.0
    precipitation_probability_percent: float = 0.0


@dataclass(frozen=True)
class WeatherSnapshot:
    """Current weather state and forecast for one Home Assistant weather entity."""

    entity_id: str
    state: str | None
    humidity_percent: float | None
    forecast: tuple[ForecastItem, ...]


@dataclass(frozen=True)
class WeatherDecision:
    """Decision returned by the weather policy evaluator."""

    state: WeatherDecisionState
    allowed: bool
    reason: str
    attributes: dict[str, Any]


def validate_thresholds(thresholds: WeatherThresholds) -> WeatherThresholds:
    """Return validated threshold values."""
    if not 0 <= thresholds.rain_probability_skip_percent <= 100:
        raise ValueError("rain probability threshold must be between 0 and 100")
    if not 0 <= thresholds.precipitation_skip_mm <= 100:
        raise ValueError("precipitation threshold must be between 0 and 100")
    if not 0 <= thresholds.humidity_skip_percent <= 100:
        raise ValueError("humidity threshold must be between 0 and 100")
    if not 1 <= thresholds.rain_lookahead_hours <= 72:
        raise ValueError("rain lookahead must be between 1 and 72 hours")
    return thresholds


def evaluate_weather_policy(
    snapshot: WeatherSnapshot | None,
    thresholds: WeatherThresholds,
) -> WeatherDecision:
    """Evaluate whether scheduled watering may run under current weather."""
    thresholds = validate_thresholds(thresholds)
    base_attrs: dict[str, Any] = {
        "rain_probability_skip_percent": thresholds.rain_probability_skip_percent,
        "precipitation_skip_mm": thresholds.precipitation_skip_mm,
        "humidity_skip_percent": thresholds.humidity_skip_percent,
        "rain_lookahead_hours": thresholds.rain_lookahead_hours,
    }

    if snapshot is None:
        return WeatherDecision(
            state=WeatherDecisionState.WEATHER_POLICY_DISABLED,
            allowed=True,
            reason="No weather entity is configured; weather guard is disabled.",
            attributes=base_attrs | {"weather_entity": "none"},
        )

    attrs = base_attrs | {
        "weather_entity": snapshot.entity_id,
        "weather_state": snapshot.state,
        "humidity_percent": snapshot.humidity_percent,
    }

    if snapshot.state in (None, "", "unknown", "unavailable", "none"):
        return WeatherDecision(
            state=WeatherDecisionState.WEATHER_UNAVAILABLE,
            allowed=False,
            reason=f"{snapshot.entity_id} is unavailable.",
            attributes=attrs,
        )

    if (
        snapshot.humidity_percent is not None
        and snapshot.humidity_percent >= thresholds.humidity_skip_percent
    ):
        return WeatherDecision(
            state=WeatherDecisionState.BLOCKED_BY_HUMIDITY,
            allowed=False,
            reason=(
                "Current humidity blocks watering: "
                f"{snapshot.humidity_percent:.0f}% >= "
                f"{thresholds.humidity_skip_percent:.0f}%."
            ),
            attributes=attrs,
        )

    for forecast in snapshot.forecast[: thresholds.rain_lookahead_hours]:
        if (
            forecast.precipitation_mm >= thresholds.precipitation_skip_mm
            or forecast.precipitation_probability_percent
            >= thresholds.rain_probability_skip_percent
        ):
            return WeatherDecision(
                state=WeatherDecisionState.BLOCKED_BY_FORECAST,
                allowed=False,
                reason=(
                    "Hourly forecast blocks watering: "
                    f"condition={forecast.condition or 'unknown'}, "
                    f"precipitation={forecast.precipitation_mm:g} mm / "
                    f"threshold {thresholds.precipitation_skip_mm:g} mm, "
                    "probability="
                    f"{forecast.precipitation_probability_percent:g}% / "
                    f"threshold {thresholds.rain_probability_skip_percent:g}%."
                ),
                attributes=attrs
                | {
                    "blocking_condition": forecast.condition,
                    "blocking_precipitation_mm": forecast.precipitation_mm,
                    "blocking_probability_percent": (
                        forecast.precipitation_probability_percent
                    ),
                },
            )

    return WeatherDecision(
        state=WeatherDecisionState.ALLOWED,
        allowed=True,
        reason="Weather guard allows scheduled watering.",
        attributes=attrs,
    )


def forecast_item_from_mapping(item: Any) -> ForecastItem:
    """Normalize one Home Assistant weather forecast mapping."""
    if not isinstance(item, dict):
        return ForecastItem()
    return ForecastItem(
        condition=_optional_string(item.get("condition")),
        precipitation_mm=_float_or_default(item.get("precipitation"), 0.0),
        precipitation_probability_percent=_float_or_default(
            item.get("precipitation_probability"),
            0.0,
        ),
    )


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _float_or_default(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
