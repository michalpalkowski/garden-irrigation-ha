"""Tests for Garden Irrigation weather guard policy."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

_POLICY_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "garden_irrigation"
    / "weather_policy.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "garden_irrigation_weather_policy",
    _POLICY_PATH,
)
assert _SPEC is not None
assert _SPEC.loader is not None
weather_policy = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = weather_policy
_SPEC.loader.exec_module(weather_policy)


class GardenIrrigationWeatherPolicyTest(unittest.TestCase):
    """Weather guard tests that do not require Home Assistant runtime imports."""

    def setUp(self) -> None:
        """Prepare default production-like thresholds."""
        self.thresholds = weather_policy.WeatherThresholds(
            rain_probability_skip_percent=35,
            precipitation_skip_mm=0.1,
            humidity_skip_percent=80,
            rain_lookahead_hours=24,
        )

    def test_allows_when_weather_guard_is_disabled(self) -> None:
        decision = weather_policy.evaluate_weather_policy(None, self.thresholds)

        self.assertTrue(decision.allowed)
        self.assertEqual(
            decision.state,
            weather_policy.WeatherDecisionState.WEATHER_POLICY_DISABLED,
        )

    def test_blocks_when_weather_entity_is_unavailable(self) -> None:
        decision = weather_policy.evaluate_weather_policy(
            weather_policy.WeatherSnapshot(
                entity_id="weather.forecast_dom",
                state="unavailable",
                humidity_percent=None,
                forecast=(),
            ),
            self.thresholds,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(
            decision.state,
            weather_policy.WeatherDecisionState.WEATHER_UNAVAILABLE,
        )

    def test_blocks_when_configured_forecast_is_missing(self) -> None:
        decision = weather_policy.evaluate_weather_policy(
            weather_policy.WeatherSnapshot(
                entity_id="weather.forecast_dom",
                state="unavailable",
                humidity_percent=55,
                forecast=(),
            ),
            self.thresholds,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(
            decision.state,
            weather_policy.WeatherDecisionState.WEATHER_UNAVAILABLE,
        )

    def test_blocks_by_humidity(self) -> None:
        decision = weather_policy.evaluate_weather_policy(
            weather_policy.WeatherSnapshot(
                entity_id="weather.forecast_dom",
                state="cloudy",
                humidity_percent=85,
                forecast=(),
            ),
            self.thresholds,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(
            decision.state,
            weather_policy.WeatherDecisionState.BLOCKED_BY_HUMIDITY,
        )

    def test_blocks_by_forecast_probability(self) -> None:
        decision = weather_policy.evaluate_weather_policy(
            weather_policy.WeatherSnapshot(
                entity_id="weather.forecast_dom",
                state="cloudy",
                humidity_percent=55,
                forecast=(
                    weather_policy.ForecastItem(
                        condition="rainy",
                        precipitation_mm=0,
                        precipitation_probability_percent=60,
                    ),
                ),
            ),
            self.thresholds,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(
            decision.state,
            weather_policy.WeatherDecisionState.BLOCKED_BY_FORECAST,
        )

    def test_allows_when_forecast_is_below_thresholds(self) -> None:
        decision = weather_policy.evaluate_weather_policy(
            weather_policy.WeatherSnapshot(
                entity_id="weather.forecast_dom",
                state="sunny",
                humidity_percent=45,
                forecast=(
                    weather_policy.ForecastItem(
                        condition="cloudy",
                        precipitation_mm=0,
                        precipitation_probability_percent=10,
                    ),
                ),
            ),
            self.thresholds,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.state, weather_policy.WeatherDecisionState.ALLOWED)


if __name__ == "__main__":
    unittest.main()
