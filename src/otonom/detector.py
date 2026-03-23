from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import Iterable, List

from .models import Detection


@dataclass(slots=True)
class FrameMetadata:
    frame_id: int
    timestamp_s: float


class WeedDetector:
    """Deterministic mock detector for MVP development and testing."""

    def __init__(self, seed: int = 42) -> None:
        self._rng = Random(seed)

    def infer(self, frame: FrameMetadata) -> List[Detection]:
        count = 1 + self._rng.randint(0, 2)
        detections: List[Detection] = []
        for idx in range(count):
            conf = round(0.55 + self._rng.random() * 0.44, 3)
            detections.append(
                Detection(
                    id=f"f{frame.frame_id}-d{idx}",
                    label="zararli_bitki",
                    confidence=conf,
                    image_x=round(self._rng.random(), 3),
                    image_y=round(self._rng.random(), 3),
                )
            )
        return detections

    def infer_batch(self, frames: Iterable[FrameMetadata]) -> List[Detection]:
        result: List[Detection] = []
        for frame in frames:
            result.extend(self.infer(frame))
        return result
