from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ClassificationResult:
    label: str
    confidence: float
    reason: str


class SecondStageClassifier:
    """Lightweight second-stage validator to reduce false positives.

    In production, replace this with a dedicated crop-vs-weed classifier model.
    """

    def __init__(self, weed_threshold: float = 0.86) -> None:
        self.weed_threshold = weed_threshold

    def classify(self, detection_id: str, confidence: float) -> ClassificationResult:
        # Deterministic tie-break to avoid random behavior around threshold.
        tie_break = (sum(ord(c) for c in detection_id) % 10) / 1000.0
        score = min(0.999, max(0.0, confidence + tie_break))

        if score >= self.weed_threshold:
            return ClassificationResult(
                label="zararli_bitki",
                confidence=round(score, 3),
                reason="second-stage classifier accepted",
            )
        if score >= self.weed_threshold - 0.05:
            return ClassificationResult(
                label="belirsiz",
                confidence=round(score, 3),
                reason="manual review recommended",
            )
        return ClassificationResult(
            label="zararsiz_bitki",
            confidence=round(score, 3),
            reason="classified as non-harmful",
        )