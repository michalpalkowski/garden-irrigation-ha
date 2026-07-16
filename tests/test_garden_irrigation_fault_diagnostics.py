"""Tests for deterministic controller outage classification."""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
import types
import unittest

from garden_irrigation_test_support import COMPONENT_PATH

_PACKAGE = types.ModuleType("garden_irrigation_fault_testpkg")
_PACKAGE.__path__ = [str(COMPONENT_PATH)]  # type: ignore[attr-defined]
sys.modules[_PACKAGE.__name__] = _PACKAGE


def _load(name: str, filename: str) -> object:
    spec = importlib.util.spec_from_file_location(name, COMPONENT_PATH / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


protocol = _load(f"{_PACKAGE.__name__}.protocol", "protocol.py")
diagnostics = _load(
    f"{_PACKAGE.__name__}.fault_diagnostics", "fault_diagnostics.py"
)


def _status(**overrides: object) -> object:
    values: dict[str, object] = {
        "board": "xiao-esp32c6",
        "chip": "esp32c6",
        "version": "0.1.0",
        "build_id": "test-build",
        "phase": "online",
        "reason": "boot",
        "reset_reason": "core_sw",
        "runtime_config_persisted": True,
        "mqtt_reconnects": 0,
        "uptime_seconds": 120,
        "free_heap_bytes": 50_000,
        "min_free_heap_bytes": 45_000,
        "heap_used_bytes": 10_000,
        "chip_temperature_celsius": 55,
    }
    values.update(overrides)
    return protocol.NetworkStatus(**values)


class FaultDiagnosticsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.detected = dt.datetime(2026, 7, 16, 10, tzinfo=dt.UTC)
        self.recovered = self.detected + dt.timedelta(minutes=5)

    def test_brownout_has_priority_over_secondary_signals(self) -> None:
        result = diagnostics.classify_outage(
            detected_at=self.detected,
            recovered_at=self.recovered,
            last_status=_status(chip_temperature_celsius=90),
            recovered_status=_status(reset_reason="sys_brownout", uptime_seconds=3),
            last_wifi_rssi=-85,
        )
        self.assertEqual(result.cause, diagnostics.OutageCause.POWER_INSTABILITY)
        self.assertEqual(result.confidence, "high")

    def test_watchdog_reset_is_explicit(self) -> None:
        result = diagnostics.classify_outage(
            detected_at=self.detected,
            recovered_at=self.recovered,
            last_status=_status(),
            recovered_status=_status(reset_reason="core_mwdt0", uptime_seconds=2),
            last_wifi_rssi=-60,
        )
        self.assertEqual(result.cause, diagnostics.OutageCause.WATCHDOG_RESET)

    def test_offline_without_recovery_remains_provisional(self) -> None:
        result = diagnostics.classify_outage(
            detected_at=self.detected,
            recovered_at=None,
            last_status=_status(),
            recovered_status=None,
            last_wifi_rssi=-60,
        )
        self.assertEqual(result.cause, diagnostics.OutageCause.CONTROLLER_OFFLINE)

    def test_heap_pressure_is_detected(self) -> None:
        result = diagnostics.classify_outage(
            detected_at=self.detected,
            recovered_at=self.recovered,
            last_status=_status(min_free_heap_bytes=4096),
            recovered_status=_status(reset_reason="core_sw", uptime_seconds=2),
            last_wifi_rssi=-60,
        )
        self.assertEqual(result.cause, diagnostics.OutageCause.MEMORY_PRESSURE)


if __name__ == "__main__":
    unittest.main()
