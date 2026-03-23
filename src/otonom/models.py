from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class MissionState(str, Enum):
    PRECHECK = "PRECHECK"
    SURVEY = "SURVEY"
    RECHECK = "RECHECK"
    APPROACH = "APPROACH"
    ALIGN = "ALIGN"
    ACTION = "ACTION"
    VERIFY = "VERIFY"
    COMPLETE = "COMPLETE"
    ABORT = "ABORT"


@dataclass(slots=True)
class DronePose:
    lat: float
    lon: float
    alt_m: float
    yaw_deg: float = 0.0


@dataclass(slots=True)
class Detection:
    id: str
    label: str
    confidence: float
    image_x: float
    image_y: float


@dataclass(slots=True)
class TargetPoint:
    id: str
    lat: float
    lon: float
    confidence: float
    priority: float


@dataclass(slots=True)
class InterventionResult:
    target_id: str
    target_lat: float
    target_lon: float
    sequence: int
    event_time_s: float
    success: bool
    method: str
    duration_sec: float
    note: str = ""


@dataclass(slots=True)
class SafetyStatus:
    rtk_fix: bool
    battery_pct: float
    wind_mps: float
    link_ok: bool
    human_detected: bool


@dataclass(slots=True)
class MissionLog:
    states: List[MissionState] = field(default_factory=list)
    serviced_targets: List[InterventionResult] = field(default_factory=list)
    aborted_reason: str | None = None
