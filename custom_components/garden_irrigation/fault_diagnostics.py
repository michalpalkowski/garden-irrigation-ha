"""Deterministic outage classification for Garden Irrigation controllers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .protocol import NetworkStatus

HEAP_PRESSURE_BYTES = 8 * 1024
HIGH_CHIP_TEMPERATURE_CELSIUS = 85
WEAK_WIFI_RSSI_DBM = -75


class OutageCause(StrEnum):
    """Stable machine-readable outage causes exposed to Home Assistant."""

    POWER_INSTABILITY = "power_instability"
    POWER_CYCLE = "power_cycle"
    WATCHDOG_RESET = "watchdog_reset"
    MEMORY_PRESSURE = "memory_pressure"
    THERMAL_STRESS = "thermal_stress"
    WIFI_INSTABILITY = "wifi_instability"
    MQTT_PATH_LOSS = "mqtt_path_loss"
    CONTROLLER_OFFLINE = "controller_offline"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class OutageDiagnosis:
    """One outage classification with human-readable evidence."""

    cause: OutageCause
    confidence: str
    summary: str
    detected_at: datetime
    recovered_at: datetime | None
    evidence: tuple[str, ...]

    def as_attributes(self) -> dict[str, object]:
        """Return Home Assistant state attributes."""
        return {
            "confidence": self.confidence,
            "summary": self.summary,
            "detected_at": self.detected_at.isoformat(),
            "recovered_at": (
                self.recovered_at.isoformat() if self.recovered_at is not None else None
            ),
            "evidence": list(self.evidence),
        }


def classify_outage(
    *,
    detected_at: datetime,
    recovered_at: datetime | None,
    last_status: NetworkStatus | None,
    recovered_status: NetworkStatus | None,
    last_wifi_rssi: int | None,
) -> OutageDiagnosis:
    """Classify an outage from retained pre-failure and post-boot evidence."""
    evidence = _evidence(last_status, recovered_status, last_wifi_rssi)

    reset_reason = recovered_status.reset_reason if recovered_status else None
    if reset_reason == "sys_brownout":
        return _diagnosis(
            OutageCause.POWER_INSTABILITY,
            "high",
            "Sterownik uruchomił się po wykryciu spadku napięcia (brownout).",
            detected_at,
            recovered_at,
            evidence,
        )
    if reset_reason in {
        "core_mwdt0",
        "core_mwdt1",
        "core_rtc_wdt",
        "cpu0_mwdt0",
        "cpu0_mwdt1",
        "cpu0_rtc_wdt",
        "sys_rtc_wdt",
        "sys_super_wdt",
    }:
        watchdog_report = recovered_status.watchdog_report if recovered_status else None
        summary = "Sterownik został zresetowany przez sprzętowy watchdog."
        if watchdog_report is not None:
            summary = (
                "Sterownik został zresetowany przez sprzętowy watchdog; "
                "ostatni checkpoint: "
                f"{watchdog_report.task}/{watchdog_report.operation}/"
                f"{watchdog_report.phase}."
            )
        return _diagnosis(
            OutageCause.WATCHDOG_RESET,
            "high",
            summary,
            detected_at,
            recovered_at,
            evidence,
        )
    if reset_reason == "chip_power_on":
        return _diagnosis(
            OutageCause.POWER_CYCLE,
            "high",
            "Sterownik wykonał pełny start po ponownym podaniu zasilania.",
            detected_at,
            recovered_at,
            evidence,
        )

    if (
        last_status is not None
        and last_status.chip_temperature_celsius is not None
        and last_status.chip_temperature_celsius >= HIGH_CHIP_TEMPERATURE_CELSIUS
    ):
        return _diagnosis(
            OutageCause.THERMAL_STRESS,
            "medium",
            "Ostatnia temperatura układu przed awarią była wysoka.",
            detected_at,
            recovered_at,
            evidence,
        )
    if (
        last_status is not None
        and last_status.min_free_heap_bytes <= HEAP_PRESSURE_BYTES
    ):
        return _diagnosis(
            OutageCause.MEMORY_PRESSURE,
            "medium",
            "Minimalna ilość wolnej pamięci przed awarią była krytycznie mała.",
            detected_at,
            recovered_at,
            evidence,
        )

    reason = last_status.reason if last_status is not None else ""
    rebooted = (
        last_status is not None
        and recovered_status is not None
        and recovered_status.uptime_seconds < last_status.uptime_seconds
    )
    if last_wifi_rssi is not None and last_wifi_rssi <= WEAK_WIFI_RSSI_DBM:
        return _diagnosis(
            OutageCause.WIFI_INSTABILITY,
            "medium" if not rebooted else "low",
            "Przed awarią sygnał Wi-Fi był słaby; utrata łącza jest prawdopodobna.",
            detected_at,
            recovered_at,
            evidence,
        )
    if reason.startswith(("mqtt", "tcp", "dns")) or (
        last_status is not None and last_status.mqtt_reconnects > 0
    ):
        return _diagnosis(
            OutageCause.MQTT_PATH_LOSS,
            "medium",
            "Ostatnia telemetria wskazuje utratę ścieżki MQTT lub TCP.",
            detected_at,
            recovered_at,
            evidence,
        )
    if recovered_at is None:
        return _diagnosis(
            OutageCause.CONTROLLER_OFFLINE,
            "confirmed",
            "Broker utracił połączenie z kontrolerem; dokładna przyczyna będzie dostępna po jego powrocie.",
            detected_at,
            None,
            evidence,
        )
    return _diagnosis(
        OutageCause.UNKNOWN,
        "low",
        "Sterownik wrócił online, ale dostępne dane nie wskazują jednej przyczyny.",
        detected_at,
        recovered_at,
        evidence,
    )


def _evidence(
    last_status: NetworkStatus | None,
    recovered_status: NetworkStatus | None,
    last_wifi_rssi: int | None,
) -> tuple[str, ...]:
    values: list[str] = []
    if last_status is not None:
        values.extend(
            (
                f"last_reason={last_status.reason}",
                f"last_uptime_seconds={last_status.uptime_seconds}",
                f"mqtt_reconnects={last_status.mqtt_reconnects}",
                f"min_free_heap_bytes={last_status.min_free_heap_bytes}",
                f"chip_temperature_celsius={last_status.chip_temperature_celsius}",
            )
        )
    if last_wifi_rssi is not None:
        values.append(f"wifi_rssi_dbm={last_wifi_rssi}")
    if recovered_status is not None:
        values.extend(
            (
                f"recovery_reset_reason={recovered_status.reset_reason}",
                f"recovery_uptime_seconds={recovered_status.uptime_seconds}",
                f"recovery_build_id={recovered_status.build_id}",
            )
        )
        report = recovered_status.watchdog_report
        if report is not None:
            values.extend(
                (
                    f"watchdog_task={report.task}",
                    f"watchdog_operation={report.operation}",
                    f"watchdog_phase={report.phase}",
                    f"watchdog_stale_task_mask={report.stale_task_mask}",
                    f"watchdog_registered_task_mask={report.registered_task_mask}",
                    f"watchdog_operation_sequence={report.operation_sequence}",
                )
            )
    return tuple(values)


def _diagnosis(
    cause: OutageCause,
    confidence: str,
    summary: str,
    detected_at: datetime,
    recovered_at: datetime | None,
    evidence: tuple[str, ...],
) -> OutageDiagnosis:
    return OutageDiagnosis(
        cause=cause,
        confidence=confidence,
        summary=summary,
        detected_at=detected_at,
        recovered_at=recovered_at,
        evidence=evidence,
    )
