from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from .actuator import InterventionUnit
from .classifier import SecondStageClassifier
from .config import MissionConfig
from .detector import FrameMetadata, WeedDetector
from .georef import GeoReferencer
from .models import DronePose, InterventionResult, MissionLog, MissionState, SafetyStatus, TargetPoint
from .planner import TargetPlanner
from .safety import SafetyGate


@dataclass(slots=True)
class MissionResult:
    state: MissionState
    log: MissionLog


class MissionController:
    def __init__(self, config: MissionConfig) -> None:
        self.config = config
        self.detector = WeedDetector()
        self.georef = GeoReferencer()
        self.planner = TargetPlanner(min_confidence=config.thresholds.min_confidence)
        self.safety = SafetyGate(config.thresholds)
        self.classifier = SecondStageClassifier(weed_threshold=config.thresholds.precision_confidence)
        self.actuator = InterventionUnit(
            method=config.intervention_method,
            max_duration_sec=config.max_action_duration_sec,
        )

    def run(
        self,
        pose: DronePose,
        status: SafetyStatus,
        frames: Iterable[FrameMetadata],
        no_spray_zones: list[list[tuple[float, float]]] | None = None,
        manual_approval_required: bool = False,
        approved_target_ids: set[str] | None = None,
    ) -> MissionResult:
        log = MissionLog()
        elapsed_time_s = 0.0
        zones = no_spray_zones or []
        approved_ids = approved_target_ids or set()
        log.states.append(MissionState.PRECHECK)
        safe, reason = self.safety.precheck(status)
        if not safe:
            log.states.append(MissionState.ABORT)
            log.aborted_reason = reason
            return MissionResult(state=MissionState.ABORT, log=log)

        log.states.append(MissionState.SURVEY)
        raw_detections = self.detector.infer_batch(frames)
        harmful_detections = []
        uncertain_detections = []
        classification_by_detection_id = {}
        for detection in raw_detections:
            classification = self.classifier.classify(detection.id, detection.confidence)
            classification_by_detection_id[detection.id] = classification
            if classification.label == "zararli_bitki":
                harmful_detections.append(detection)
            elif classification.label == "belirsiz":
                uncertain_detections.append(detection)

        log.states.append(MissionState.RECHECK)
        uncertain_targets = self.georef.project(pose, uncertain_detections)
        for uncertain in uncertain_targets:
            log.states.append(MissionState.VERIFY)
            log.serviced_targets.append(
                InterventionResult(
                    target_id=uncertain.id,
                    target_lat=uncertain.lat,
                    target_lon=uncertain.lon,
                    sequence=len(log.serviced_targets) + 1,
                    event_time_s=round(elapsed_time_s, 2),
                    success=False,
                    method="blocked_uncertain",
                    duration_sec=0.0,
                    note="Blocked by hard rule: uncertain target requires manual review",
                )
            )
            elapsed_time_s += 0.15

        targets = self.georef.project(pose, harmful_detections)
        plan = self.planner.prioritize(targets, pose)

        for target in plan:
            elapsed_time_s = self._service_target(
                log,
                target,
                status,
                elapsed_time_s,
                zones,
                manual_approval_required,
                approved_ids,
                classification_by_detection_id,
            )
            if log.states and log.states[-1] == MissionState.ABORT:
                return MissionResult(state=MissionState.ABORT, log=log)

        log.states.append(MissionState.COMPLETE)
        return MissionResult(state=MissionState.COMPLETE, log=log)

    def _service_target(
        self,
        log: MissionLog,
        target: TargetPoint,
        status: SafetyStatus,
        elapsed_time_s: float,
        no_spray_zones: list[list[tuple[float, float]]],
        manual_approval_required: bool,
        approved_target_ids: set[str],
        classification_by_detection_id: dict | None = None,
    ) -> float:
        log.states.extend([MissionState.APPROACH, MissionState.ALIGN])
        elapsed_time_s += 1.5

        if classification_by_detection_id is not None:
            cls = classification_by_detection_id.get(target.id)
            cls_label = getattr(cls, "label", "")
            if cls_label != "zararli_bitki":
                log.states.append(MissionState.VERIFY)
                log.serviced_targets.append(
                    InterventionResult(
                        target_id=target.id,
                        target_lat=target.lat,
                        target_lon=target.lon,
                        sequence=len(log.serviced_targets) + 1,
                        event_time_s=round(elapsed_time_s, 2),
                        success=False,
                        method="blocked_uncertain",
                        duration_sec=0.0,
                        note="Blocked by hard rule: non-harmful or uncertain classification",
                    )
                )
                elapsed_time_s += 0.2
                return elapsed_time_s

        if status.human_detected:
            log.states.append(MissionState.ABORT)
            log.aborted_reason = "Insan algilandi, gorev durduruldu"
            return elapsed_time_s

        action_floor = max(
            self.config.thresholds.action_confidence,
            self.config.thresholds.precision_confidence,
        )
        if target.confidence < action_floor:
            return elapsed_time_s

        if self._in_no_spray_zone(target.lat, target.lon, no_spray_zones):
            log.states.append(MissionState.VERIFY)
            log.serviced_targets.append(
                InterventionResult(
                    target_id=target.id,
                    target_lat=target.lat,
                    target_lon=target.lon,
                    sequence=len(log.serviced_targets) + 1,
                    event_time_s=round(elapsed_time_s, 2),
                    success=False,
                    method="blocked",
                    duration_sec=0.0,
                    note="Blocked by no-spray zone",
                )
            )
            elapsed_time_s += 0.2
            return elapsed_time_s

        if manual_approval_required and not self._is_approved(target.id, approved_target_ids):
            log.states.append(MissionState.VERIFY)
            log.serviced_targets.append(
                InterventionResult(
                    target_id=target.id,
                    target_lat=target.lat,
                    target_lon=target.lon,
                    sequence=len(log.serviced_targets) + 1,
                    event_time_s=round(elapsed_time_s, 2),
                    success=False,
                    method="manual_hold",
                    duration_sec=0.0,
                    note="Manual approval required",
                )
            )
            elapsed_time_s += 0.2
            return elapsed_time_s

        log.states.append(MissionState.ACTION)
        sequence = len(log.serviced_targets) + 1
        result = self.actuator.execute(target, sequence=sequence, event_time_s=round(elapsed_time_s, 2))
        log.serviced_targets.append(result)
        elapsed_time_s += result.duration_sec
        log.states.append(MissionState.VERIFY)
        elapsed_time_s += 0.4
        return elapsed_time_s

    def _is_approved(self, target_id: str, approved_target_ids: set[str]) -> bool:
        if target_id in approved_target_ids:
            return True
        for item in approved_target_ids:
            if item.endswith(target_id):
                return True
        return False

    def _in_no_spray_zone(self, lat: float, lon: float, zones: list[list[tuple[float, float]]]) -> bool:
        for polygon in zones:
            if self._point_in_polygon(lat, lon, polygon):
                return True
        return False

    def _point_in_polygon(self, lat: float, lon: float, polygon: list[tuple[float, float]]) -> bool:
        if len(polygon) < 3:
            return False
        inside = False
        j = len(polygon) - 1
        for i in range(len(polygon)):
            yi, xi = polygon[i]
            yj, xj = polygon[j]
            intersects = ((yi > lat) != (yj > lat)) and (
                lon < (xj - xi) * (lat - yi) / ((yj - yi) + 1e-12) + xi
            )
            if intersects:
                inside = not inside
            j = i
        return inside
