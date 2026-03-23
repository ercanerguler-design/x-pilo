from otonom.config import MissionConfig, Thresholds
from otonom.detector import FrameMetadata
from otonom.mission import MissionController
from otonom.models import DronePose, MissionState, SafetyStatus


def _config() -> MissionConfig:
    return MissionConfig(
        intervention_method="micro_spray",
        max_action_duration_sec=2.5,
        max_retry_per_target=2,
        thresholds=Thresholds(
            min_confidence=0.6,
            action_confidence=0.72,
            precision_confidence=0.86,
            max_wind_mps=8.0,
            min_battery_pct=30.0,
        ),
    )


def test_mission_completes_with_safe_conditions() -> None:
    mission = MissionController(_config())
    pose = DronePose(lat=39.9, lon=32.8, alt_m=6.0)
    status = SafetyStatus(
        rtk_fix=True,
        battery_pct=80.0,
        wind_mps=3.0,
        link_ok=True,
        human_detected=False,
    )
    frames = [FrameMetadata(frame_id=i, timestamp_s=i * 0.1) for i in range(1, 5)]

    result = mission.run(pose, status, frames)

    assert result.state == MissionState.COMPLETE
    assert MissionState.PRECHECK in result.log.states


def test_mission_aborts_when_precheck_fails() -> None:
    mission = MissionController(_config())
    pose = DronePose(lat=39.9, lon=32.8, alt_m=6.0)
    status = SafetyStatus(
        rtk_fix=False,
        battery_pct=80.0,
        wind_mps=3.0,
        link_ok=True,
        human_detected=False,
    )
    frames = [FrameMetadata(frame_id=1, timestamp_s=0.1)]

    result = mission.run(pose, status, frames)

    assert result.state == MissionState.ABORT
    assert result.log.aborted_reason == "RTK fix yok"
