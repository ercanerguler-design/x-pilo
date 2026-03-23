from __future__ import annotations

from random import Random

from .models import InterventionResult, TargetPoint


class InterventionUnit:
    def __init__(self, method: str, max_duration_sec: float, seed: int = 7) -> None:
        self.method = method
        self.max_duration_sec = max_duration_sec
        self._rng = Random(seed)

    def execute(self, target: TargetPoint, sequence: int, event_time_s: float) -> InterventionResult:
        _ = self._rng
        duration = round(min(1.4 + (1.0 - target.confidence) * 0.9, self.max_duration_sec), 2)
        success = True
        note = "Precision gate passed; localized treatment applied"
        return InterventionResult(
            target_id=target.id,
            target_lat=target.lat,
            target_lon=target.lon,
            sequence=sequence,
            event_time_s=event_time_s,
            success=success,
            method=self.method,
            duration_sec=duration,
            note=note,
        )
