from __future__ import annotations

from math import hypot
from typing import Iterable, List

from .models import DronePose, TargetPoint


def _distance_m(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    # Lightweight local approximation for short in-field distances.
    dy = (a_lat - b_lat) * 111_111.0
    dx = (a_lon - b_lon) * 111_111.0
    return hypot(dx, dy)


class TargetPlanner:
    def __init__(self, min_confidence: float) -> None:
        self.min_confidence = min_confidence

    def prioritize(self, targets: Iterable[TargetPoint], pose: DronePose) -> List[TargetPoint]:
        filtered = [t for t in targets if t.confidence >= self.min_confidence]
        return sorted(
            filtered,
            key=lambda t: (-t.priority, _distance_m(t.lat, t.lon, pose.lat, pose.lon)),
        )
