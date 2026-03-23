from __future__ import annotations

from math import cos, radians
from typing import Iterable, List

from .models import Detection, DronePose, TargetPoint


class GeoReferencer:
    """Projects image-space detections to rough geo-points around drone pose."""

    def __init__(self, meter_per_norm: float = 2.0) -> None:
        self.meter_per_norm = meter_per_norm

    def project(self, pose: DronePose, detections: Iterable[Detection]) -> List[TargetPoint]:
        targets: List[TargetPoint] = []
        lat_scale = 1.0 / 111_111.0
        lon_scale = 1.0 / (111_111.0 * cos(radians(pose.lat)))
        for det in detections:
            dx_m = (det.image_x - 0.5) * self.meter_per_norm * 2
            dy_m = (det.image_y - 0.5) * self.meter_per_norm * 2
            target = TargetPoint(
                id=det.id,
                lat=pose.lat + (dy_m * lat_scale),
                lon=pose.lon + (dx_m * lon_scale),
                confidence=det.confidence,
                priority=det.confidence,
            )
            targets.append(target)
        return targets
