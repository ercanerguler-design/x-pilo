from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import load_config
from .detector import FrameMetadata
from .mission import MissionController
from .models import DronePose, SafetyStatus


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Otonom zararli bitki gorev simulasyonu")
    parser.add_argument(
        "--config",
        default="configs/mission.yaml",
        help="Mission config file path",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(Path(args.config))

    mission = MissionController(config)
    pose = DronePose(lat=39.9208, lon=32.8541, alt_m=8.0)
    status = SafetyStatus(
        rtk_fix=True,
        battery_pct=82.0,
        wind_mps=4.3,
        link_ok=True,
        human_detected=False,
    )
    frames = [FrameMetadata(frame_id=i, timestamp_s=i * 0.5) for i in range(1, 8)]

    result = mission.run(pose=pose, status=status, frames=frames)

    payload = {
        "state": result.state.value,
        "states": [s.value for s in result.log.states],
        "aborted_reason": result.log.aborted_reason,
        "serviced_targets": [
            {
                "target_id": r.target_id,
                "success": r.success,
                "method": r.method,
                "duration_sec": r.duration_sec,
                "note": r.note,
            }
            for r in result.log.serviced_targets
        ],
    }
    print(json.dumps(payload, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
