from __future__ import annotations

from .config import Thresholds
from .models import SafetyStatus


class SafetyGate:
    def __init__(self, thresholds: Thresholds) -> None:
        self.thresholds = thresholds

    def precheck(self, status: SafetyStatus) -> tuple[bool, str]:
        if not status.rtk_fix:
            return False, "RTK fix yok"
        if status.battery_pct < self.thresholds.min_battery_pct:
            return False, "Batarya seviyesi dusuk"
        if status.wind_mps > self.thresholds.max_wind_mps:
            return False, "Ruzgar limiti asildi"
        if not status.link_ok:
            return False, "Telemetri linki yok"
        if status.human_detected:
            return False, "Insan algilandi"
        return True, "OK"
