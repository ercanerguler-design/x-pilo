from __future__ import annotations

import math
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .config import load_config
from .detector import FrameMetadata, WeedDetector
from .drone_bridge import DroneManager
from .geometry_io import (
    AreaGeometry,
    _point_in_polygon,
    export_geojson,
    export_kml,
    import_geojson,
    import_kml,
    parcelize_geometry,
)
from .inference import YOLOModelRuntime
from .mission import MissionController
from .models import DronePose, SafetyStatus
from .schemas import (
    DroneConnectRequest,
    DroneFailsafeRequest,
    DroneGotoRequest,
    DroneStatusResponse,
    DroneTakeoffRequest,
    GeometryExportRequest,
    GeometryExportResponse,
    GeometryImportRequest,
    GeometryImportResponse,
    ImageDetectionResponse,
    LiveParcelMissionResponse,
    LiveMissionJobAcceptedResponse,
    LiveMissionJobStatusResponse,
    ParcelMissionItem,
    ParcelMissionRequest,
    ParcelMissionResponse,
    ParcelPolygon,
    ParcelizeRequest,
    ParcelizeResponse,
    RunMissionRequest,
    RunMissionResponse,
    ServicedTargetResponse,
    StopEventLogItem,
    StopMissionRequest,
    RestartConfirmRequest,
    SimulateDetectionRequest,
    SimulateDetectionResponse,
)


class OtonomService:
    def __init__(self, config_path: str | Path = "configs/mission.yaml") -> None:
        self.config_path = Path(config_path)
        self.config = load_config(self.config_path)
        self._detector = WeedDetector(seed=42)
        self._runtime = YOLOModelRuntime(
            model_path=self.config.model_path,
            tensorrt_engine_path=self.config.tensorrt_engine_path,
            backend_preference=self.config.model_backend_preference,
        )
        self._drone = DroneManager()
        self._stop_requested = False
        self._restart_confirmation_required = False
        self._jobs_lock = threading.Lock()
        self._live_jobs: dict[str, dict] = {}
        self._active_live_job_id: str | None = None
        self._active_parcel_id: str | None = None
        self._stop_events: list[dict] = []

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _record_stop_event(self, operator_id: str, reason: str) -> dict:
        event = {
            "operator_id": operator_id,
            "requested_at": self._utc_now(),
            "job_id": self._active_live_job_id,
            "parcel_id": self._active_parcel_id,
            "reason": reason,
        }
        with self._jobs_lock:
            self._stop_events.append(event)
            if len(self._stop_events) > 200:
                self._stop_events = self._stop_events[-200:]
            if self._active_live_job_id and self._active_live_job_id in self._live_jobs:
                self._live_jobs[self._active_live_job_id].setdefault("stop_events", []).append(event)
                self._live_jobs[self._active_live_job_id]["updated_at"] = self._utc_now()
        return event

    def _new_live_job(self, total_parcels: int) -> dict:
        job_id = str(uuid.uuid4())
        now = self._utc_now()
        job = {
            "job_id": job_id,
            "status": "QUEUED",
            "message": "Live mission queued",
            "created_at": now,
            "updated_at": now,
            "total_parcels": int(total_parcels),
            "completed_parcels": 0,
            "active_parcel_id": None,
            "next_parcel_id": None,
            "stop_events": [],
            "result": None,
        }
        with self._jobs_lock:
            self._live_jobs[job_id] = job
        return job

    def _update_live_job(self, job_id: str, **updates) -> None:
        with self._jobs_lock:
            job = self._live_jobs.get(job_id)
            if not job:
                return
            job.update(updates)
            job["updated_at"] = self._utc_now()

    def _get_live_job(self, job_id: str) -> dict | None:
        with self._jobs_lock:
            job = self._live_jobs.get(job_id)
            if not job:
                return None
            copied = dict(job)
            copied["stop_events"] = list(job.get("stop_events", []))
            copied["result"] = job.get("result")
            return copied

    def request_mission_stop(self) -> None:
        self._stop_requested = True

    def clear_mission_stop(self) -> None:
        self._stop_requested = False

    def reload_config(self) -> None:
        self.config = load_config(self.config_path)
        self._runtime = YOLOModelRuntime(
            model_path=self.config.model_path,
            tensorrt_engine_path=self.config.tensorrt_engine_path,
            backend_preference=self.config.model_backend_preference,
        )

    def _map_serviced_targets(self, parcel_id: str | None, items) -> list[ServicedTargetResponse]:
        return [
            ServicedTargetResponse(
                target_id=(f"{parcel_id}:{item.target_id}" if parcel_id else item.target_id),
                parcel_id=parcel_id,
                target_lat=item.target_lat,
                target_lon=item.target_lon,
                sequence=item.sequence,
                event_time_s=item.event_time_s,
                success=item.success,
                method=item.method,
                duration_sec=item.duration_sec,
                note=item.note,
            )
            for item in items
        ]

    def _zones_from_request(self, request) -> list[list[tuple[float, float]]]:
        return [[(float(lat), float(lon)) for lat, lon in zone] for zone in request.no_spray_zones]

    def _generate_scan_path(
        self,
        polygon: list[tuple[float, float]],
        lane_spacing_m: float,
        sample_spacing_m: float,
        orientation: str,
    ) -> list[tuple[float, float]]:
        if len(polygon) < 3:
            return []

        coords = polygon[:]
        if coords[0] == coords[-1]:
            coords = coords[:-1]
        if len(coords) < 3:
            return []

        lats = [p[0] for p in coords]
        lons = [p[1] for p in coords]
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        mean_lat = sum(lats) / len(lats)

        dlat_lane = lane_spacing_m / 111_111.0
        dlon_lane = lane_spacing_m / max(1.0, 111_111.0 * math.cos(math.radians(mean_lat)))
        dlat_sample = sample_spacing_m / 111_111.0
        dlon_sample = sample_spacing_m / max(1.0, 111_111.0 * math.cos(math.radians(mean_lat)))
        if dlat_lane <= 0 or dlon_lane <= 0 or dlat_sample <= 0 or dlon_sample <= 0:
            return []

        sweep: list[tuple[float, float]] = []
        mode = (orientation or "horizontal").strip().lower()
        if mode == "vertical":
            col_idx = 0
            lon = min_lon
            while lon <= max_lon + 1e-12:
                col_points: list[tuple[float, float]] = []
                lat = min_lat
                while lat <= max_lat + 1e-12:
                    if _point_in_polygon(lat, lon, coords):
                        col_points.append((lat, lon))
                    lat += dlat_sample

                if col_points:
                    if col_idx % 2 == 1:
                        col_points.reverse()
                    sweep.extend(col_points)

                col_idx += 1
                lon += dlon_lane
        else:
            row_idx = 0
            lat = min_lat
            while lat <= max_lat + 1e-12:
                row_points: list[tuple[float, float]] = []
                lon = min_lon
                while lon <= max_lon + 1e-12:
                    if _point_in_polygon(lat, lon, coords):
                        row_points.append((lat, lon))
                    lon += dlon_sample

                if row_points:
                    if row_idx % 2 == 1:
                        row_points.reverse()
                    sweep.extend(row_points)

                row_idx += 1
                lat += dlat_lane

        if not sweep:
            area = AreaGeometry(coordinates=coords)
            return [area.center]
        return sweep

    def run_mission(self, request: RunMissionRequest) -> RunMissionResponse:
        controller = MissionController(self.config)
        pose = DronePose(
            lat=request.pose.lat,
            lon=request.pose.lon,
            alt_m=request.pose.alt_m,
            yaw_deg=request.pose.yaw_deg,
        )
        safety = SafetyStatus(
            rtk_fix=request.safety.rtk_fix,
            battery_pct=request.safety.battery_pct,
            wind_mps=request.safety.wind_mps,
            link_ok=request.safety.link_ok,
            human_detected=request.safety.human_detected,
        )
        frames = [FrameMetadata(frame_id=i, timestamp_s=i * 0.2) for i in range(1, request.frame_count + 1)]

        result = controller.run(
            pose=pose,
            status=safety,
            frames=frames,
            no_spray_zones=self._zones_from_request(request),
            manual_approval_required=request.manual_approval_required,
            approved_target_ids=set(request.approved_target_ids),
        )

        return RunMissionResponse(
            state=result.state.value,
            states=[s.value for s in result.log.states],
            aborted_reason=result.log.aborted_reason,
            serviced_targets=self._map_serviced_targets(None, result.log.serviced_targets),
        )

    def simulate_detection(self, request: SimulateDetectionRequest) -> SimulateDetectionResponse:
        frames = [FrameMetadata(frame_id=i, timestamp_s=i * 0.1) for i in range(1, request.frame_count + 1)]
        detections = self._detector.infer_batch(frames)
        return SimulateDetectionResponse(
            model="deterministic-mvp",
            detections=[
                {
                    "id": d.id,
                    "label": d.label,
                    "confidence": d.confidence,
                    "image_x": d.image_x,
                    "image_y": d.image_y,
                }
                for d in detections
            ],
        )

    def detect_image(self, image_bytes: bytes) -> ImageDetectionResponse:
        result = self._runtime.detect_from_image_bytes(image_bytes)
        return ImageDetectionResponse(
            backend=result.backend,
            detections=[
                {
                    "id": d.id,
                    "label": d.label,
                    "confidence": d.confidence,
                    "image_x": d.image_x,
                    "image_y": d.image_y,
                }
                for d in result.detections
            ],
        )

    def import_geometry(self, payload: GeometryImportRequest) -> GeometryImportResponse:
        area = import_geojson(payload.content) if payload.format == "geojson" else import_kml(payload.content)
        center_lat, center_lon = area.center
        return GeometryImportResponse(
            center_lat=round(center_lat, 7),
            center_lon=round(center_lon, 7),
            area_ha=round(area.area_ha, 4),
            coordinates=[[lat, lon] for lat, lon in area.coordinates],
        )

    def export_geometry(self, payload: GeometryExportRequest) -> GeometryExportResponse:
        area = AreaGeometry(coordinates=[(float(lat), float(lon)) for lat, lon in payload.coordinates])
        content = export_geojson(area) if payload.format == "geojson" else export_kml(area)
        return GeometryExportResponse(format=payload.format, content=content)

    def parcelize(self, payload: ParcelizeRequest) -> ParcelizeResponse:
        area = AreaGeometry(coordinates=[(float(lat), float(lon)) for lat, lon in payload.coordinates])
        parcels = parcelize_geometry(area, rows=payload.rows, cols=payload.cols)
        return ParcelizeResponse(
            rows=payload.rows,
            cols=payload.cols,
            parcel_count=len(parcels),
            parcels=[
                ParcelPolygon(
                    parcel_id=f"P-{idx + 1}",
                    coordinates=[[lat, lon] for lat, lon in parcel],
                )
                for idx, parcel in enumerate(parcels)
            ],
        )

    def _run_parcel_loop(
        self,
        request: ParcelMissionRequest,
        use_live_drone: bool,
        progress_cb=None,
    ) -> ParcelMissionResponse:
        controller = MissionController(self.config)
        safety = SafetyStatus(
            rtk_fix=request.safety.rtk_fix,
            battery_pct=request.safety.battery_pct,
            wind_mps=request.safety.wind_mps,
            link_ok=request.safety.link_ok,
            human_detected=request.safety.human_detected,
        )

        parcel_results: list[ParcelMissionItem] = []
        all_targets: list[ServicedTargetResponse] = []
        global_sequence = 0
        global_time_offset = 0.0
        completed = 0
        zones = self._zones_from_request(request)
        approved = set(request.approved_target_ids)

        for parcel_idx, parcel in enumerate(request.parcels):
            if self._stop_requested:
                parcel_results.append(
                    ParcelMissionItem(
                        parcel_id=parcel.parcel_id,
                        state="PARTIAL",
                        aborted_reason="Mission stop requested by operator",
                        serviced_target_count=0,
                        scan_path=[],
                    )
                )
                continue

            self._active_parcel_id = parcel.parcel_id
            if progress_cb:
                next_parcel = request.parcels[parcel_idx + 1].parcel_id if parcel_idx + 1 < len(request.parcels) else None
                progress_cb(
                    {
                        "completed_parcels": completed,
                        "active_parcel_id": parcel.parcel_id,
                        "next_parcel_id": next_parcel,
                        "message": f"Parcel running: {parcel.parcel_id}",
                    }
                )

            area = AreaGeometry(coordinates=[(float(lat), float(lon)) for lat, lon in parcel.coordinates])
            scan_path = self._generate_scan_path(
                polygon=area.coordinates,
                lane_spacing_m=request.lane_spacing_m,
                sample_spacing_m=request.sample_spacing_m,
                orientation=request.scan_orientation,
            )

            frames_per_waypoint = max(1, int(round(request.frame_count / max(1, len(scan_path)))))
            parcel_state = "COMPLETE"
            parcel_abort_reason: str | None = None
            parcel_serviced = 0
            parcel_time_offset = 0.0

            for wp_idx, (wp_lat, wp_lon) in enumerate(scan_path, start=1):
                if self._stop_requested:
                    parcel_state = "PARTIAL"
                    parcel_abort_reason = "Mission stop requested by operator"
                    if use_live_drone:
                        self._drone.stop()
                    break

                if use_live_drone:
                    self._drone.fly_to(wp_lat, wp_lon, request.alt_m)
                    status = self._drone.status()
                    current = status.get("telemetry", {})
                    pose = DronePose(
                        lat=float(current.get("lat", wp_lat)),
                        lon=float(current.get("lon", wp_lon)),
                        alt_m=float(current.get("alt_m", request.alt_m)),
                        yaw_deg=request.yaw_deg,
                    )
                else:
                    pose = DronePose(lat=wp_lat, lon=wp_lon, alt_m=request.alt_m, yaw_deg=request.yaw_deg)

                frames = [
                    FrameMetadata(frame_id=i, timestamp_s=i * 0.2 + (wp_idx - 1) * 0.01)
                    for i in range(1, frames_per_waypoint + 1)
                ]
                result = controller.run(
                    pose=pose,
                    status=safety,
                    frames=frames,
                    no_spray_zones=zones,
                    manual_approval_required=request.manual_approval_required,
                    approved_target_ids=approved,
                )

                if result.state.value != "COMPLETE":
                    parcel_state = "PARTIAL"
                    parcel_abort_reason = result.log.aborted_reason

                if result.log.serviced_targets:
                    max_local_time = 0.0
                    for item in result.log.serviced_targets:
                        global_sequence += 1
                        parcel_serviced += 1
                        max_local_time = max(max_local_time, item.event_time_s)
                        all_targets.append(
                            ServicedTargetResponse(
                                target_id=f"{parcel.parcel_id}:W{wp_idx}:{item.target_id}",
                                parcel_id=parcel.parcel_id,
                                target_lat=item.target_lat,
                                target_lon=item.target_lon,
                                sequence=global_sequence,
                                event_time_s=round(global_time_offset + parcel_time_offset + item.event_time_s, 2),
                                success=item.success,
                                method=item.method,
                                duration_sec=item.duration_sec,
                                note=item.note,
                            )
                        )
                    parcel_time_offset += max_local_time + 0.4
                else:
                    parcel_time_offset += 0.4

                if result.state.value != "COMPLETE":
                    break

            if parcel_state == "COMPLETE":
                completed += 1

            if progress_cb:
                next_parcel = request.parcels[parcel_idx + 1].parcel_id if parcel_idx + 1 < len(request.parcels) else None
                progress_cb(
                    {
                        "completed_parcels": completed,
                        "active_parcel_id": (None if next_parcel else parcel.parcel_id),
                        "next_parcel_id": next_parcel,
                        "message": f"Parcel {parcel.parcel_id} -> {parcel_state}",
                    }
                )

            parcel_results.append(
                ParcelMissionItem(
                    parcel_id=parcel.parcel_id,
                    state=parcel_state,
                    aborted_reason=parcel_abort_reason,
                    serviced_target_count=parcel_serviced,
                    scan_path=[[lat, lon] for lat, lon in scan_path],
                )
            )

            global_time_offset += parcel_time_offset + 1.0

        total = len(request.parcels)
        failed = total - completed
        self._active_parcel_id = None
        return ParcelMissionResponse(
            state=("COMPLETE" if failed == 0 else "PARTIAL"),
            total_parcels=total,
            completed_parcels=completed,
            failed_parcels=failed,
            parcel_results=parcel_results,
            serviced_targets=all_targets,
        )

    def run_mission_parcels(self, request: ParcelMissionRequest) -> ParcelMissionResponse:
        self.clear_mission_stop()
        return self._run_parcel_loop(request, use_live_drone=False)

    def run_live_parcel_mission(self, request: ParcelMissionRequest) -> LiveParcelMissionResponse:
        if self._restart_confirmation_required and not getattr(request, "restart_confirmed", False):
            raise ValueError("RESTART_CONFIRM_REQUIRED")
        self.clear_mission_stop()
        status = self._drone.status()
        if not status.get("connected"):
            raise ValueError("Drone bagli degil. Once drone baglantisini kur.")
        parcel_result = self._run_parcel_loop(request, use_live_drone=True)
        return LiveParcelMissionResponse(
            state=parcel_result.state,
            total_parcels=parcel_result.total_parcels,
            completed_parcels=parcel_result.completed_parcels,
            failed_parcels=parcel_result.failed_parcels,
            parcel_results=parcel_result.parcel_results,
            serviced_targets=parcel_result.serviced_targets,
            drone_status=DroneStatusResponse.model_validate(self._drone.status()),
        )

    def start_live_parcel_mission(self, request: ParcelMissionRequest) -> LiveMissionJobAcceptedResponse:
        if self._restart_confirmation_required and not getattr(request, "restart_confirmed", False):
            raise ValueError("RESTART_CONFIRM_REQUIRED")
        status = self._drone.status()
        if not status.get("connected"):
            raise ValueError("Drone bagli degil. Once drone baglantisini kur.")
        if self._active_live_job_id:
            active = self._get_live_job(self._active_live_job_id)
            if active and active.get("status") in {"QUEUED", "RUNNING"}:
                raise ValueError("LIVE_MISSION_ALREADY_RUNNING")

        self.clear_mission_stop()
        job = self._new_live_job(total_parcels=len(request.parcels))
        job_id = job["job_id"]

        def _runner() -> None:
            self._active_live_job_id = job_id
            self._update_live_job(job_id, status="RUNNING", message="Live mission started")

            def _progress_cb(payload: dict) -> None:
                self._update_live_job(
                    job_id,
                    completed_parcels=payload.get("completed_parcels", 0),
                    active_parcel_id=payload.get("active_parcel_id"),
                    next_parcel_id=payload.get("next_parcel_id"),
                    message=payload.get("message", "Running"),
                )

            try:
                parcel_result = self._run_parcel_loop(request, use_live_drone=True, progress_cb=_progress_cb)
                final_response = LiveParcelMissionResponse(
                    state=parcel_result.state,
                    total_parcels=parcel_result.total_parcels,
                    completed_parcels=parcel_result.completed_parcels,
                    failed_parcels=parcel_result.failed_parcels,
                    parcel_results=parcel_result.parcel_results,
                    serviced_targets=parcel_result.serviced_targets,
                    drone_status=DroneStatusResponse.model_validate(self._drone.status()),
                )
                final_status = "STOPPED" if self._stop_requested else parcel_result.state
                self._update_live_job(
                    job_id,
                    status=final_status,
                    completed_parcels=parcel_result.completed_parcels,
                    active_parcel_id=None,
                    next_parcel_id=None,
                    message="Live mission finished",
                    result=final_response.model_dump(),
                )
            except Exception as exc:
                self._update_live_job(
                    job_id,
                    status="FAILED",
                    message=str(exc),
                    active_parcel_id=None,
                    next_parcel_id=None,
                )
            finally:
                self._active_live_job_id = None
                self._active_parcel_id = None

        threading.Thread(target=_runner, daemon=True).start()

        return LiveMissionJobAcceptedResponse(
            job_id=job_id,
            status=job["status"],
            message=job["message"],
            total_parcels=job["total_parcels"],
        )

    def get_live_mission_job(self, job_id: str) -> LiveMissionJobStatusResponse:
        job = self._get_live_job(job_id)
        if not job:
            raise ValueError("MISSION_JOB_NOT_FOUND")
        result_obj = None
        if job.get("result"):
            result_obj = LiveParcelMissionResponse.model_validate(job["result"])
        return LiveMissionJobStatusResponse(
            job_id=job["job_id"],
            status=job["status"],
            message=job["message"],
            created_at=job["created_at"],
            updated_at=job["updated_at"],
            total_parcels=job["total_parcels"],
            completed_parcels=job["completed_parcels"],
            active_parcel_id=job.get("active_parcel_id"),
            next_parcel_id=job.get("next_parcel_id"),
            stop_events=[StopEventLogItem.model_validate(e) for e in job.get("stop_events", [])],
            result=result_obj,
        )

    def list_stop_events(self) -> list[StopEventLogItem]:
        with self._jobs_lock:
            return [StopEventLogItem.model_validate(e) for e in list(self._stop_events)]

    def connect_drone(self, payload: DroneConnectRequest) -> DroneStatusResponse:
        self._drone.configure_backend(payload.backend)
        return DroneStatusResponse.model_validate(self._drone.connect(payload.connection_uri))

    def disconnect_drone(self) -> DroneStatusResponse:
        return DroneStatusResponse.model_validate(self._drone.disconnect())

    def get_drone_status(self) -> DroneStatusResponse:
        return DroneStatusResponse.model_validate(self._drone.status())

    def arm_drone(self) -> DroneStatusResponse:
        return DroneStatusResponse.model_validate(self._drone.arm())

    def drone_takeoff(self, payload: DroneTakeoffRequest) -> DroneStatusResponse:
        return DroneStatusResponse.model_validate(self._drone.takeoff(payload.alt_m))

    def drone_goto(self, payload: DroneGotoRequest) -> DroneStatusResponse:
        return DroneStatusResponse.model_validate(self._drone.fly_to(payload.lat, payload.lon, payload.alt_m))

    def drone_land(self) -> DroneStatusResponse:
        return DroneStatusResponse.model_validate(self._drone.land())

    def drone_failsafe(self, payload: DroneFailsafeRequest) -> DroneStatusResponse:
        return DroneStatusResponse.model_validate(self._drone.failsafe(payload.action))

    def drone_stop(self) -> DroneStatusResponse:
        return DroneStatusResponse.model_validate(self._drone.stop())

    def stop_live_mission(self, payload: StopMissionRequest) -> DroneStatusResponse:
        self.request_mission_stop()
        self._restart_confirmation_required = True
        self._record_stop_event(payload.operator_id, "Operator emergency stop")
        return self.drone_stop()

    def confirm_restart_after_stop(self, payload: RestartConfirmRequest) -> dict[str, str | bool]:
        if payload.confirmation_token != "CONFIRM":
            raise ValueError("RESTART_CONFIRM_INVALID")
        self._restart_confirmation_required = False
        return {
            "status": "confirmed",
            "required": False,
            "confirmed_by": payload.operator_id,
            "confirmed_at": self._utc_now(),
        }
