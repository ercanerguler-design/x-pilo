from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(slots=True)
class Thresholds:
    min_confidence: float
    action_confidence: float
    precision_confidence: float
    max_wind_mps: float
    min_battery_pct: float


@dataclass(slots=True)
class MissionConfig:
    intervention_method: str
    max_action_duration_sec: float
    max_retry_per_target: int
    thresholds: Thresholds
    model_path: str | None = None
    tensorrt_engine_path: str | None = None
    model_backend_preference: str = "tensorrt"


def load_config(path: str | Path) -> MissionConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    thr = data["thresholds"]
    thresholds = Thresholds(
        min_confidence=float(thr["min_confidence"]),
        action_confidence=float(thr["action_confidence"]),
        precision_confidence=float(thr.get("precision_confidence", thr["action_confidence"])),
        max_wind_mps=float(thr["max_wind_mps"]),
        min_battery_pct=float(thr["min_battery_pct"]),
    )
    return MissionConfig(
        intervention_method=str(data["intervention_method"]),
        max_action_duration_sec=float(data["max_action_duration_sec"]),
        max_retry_per_target=int(data["max_retry_per_target"]),
        thresholds=thresholds,
        model_path=data.get("model_path"),
        tensorrt_engine_path=data.get("tensorrt_engine_path"),
        model_backend_preference=str(data.get("model_backend_preference", "tensorrt")),
    )
