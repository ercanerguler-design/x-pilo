from __future__ import annotations

from pathlib import Path
import json
import time

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

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
    ParcelMissionRequest,
    ParcelMissionResponse,
    ParcelizeRequest,
    ParcelizeResponse,
    RunMissionRequest,
    RunMissionResponse,
    StopEventLogItem,
    StopMissionRequest,
    RestartConfirmRequest,
    SimulateDetectionRequest,
    SimulateDetectionResponse,
)
from .service import OtonomService


BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"

app = FastAPI(
    title="Otonom Field Control",
    version="0.2.0",
    description="Safe autonomous weed detection and intervention control API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

service = OtonomService()


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/mission/run", response_model=RunMissionResponse)
def run_mission(payload: RunMissionRequest) -> RunMissionResponse:
    return service.run_mission(payload)


@app.post("/api/v1/mission/run-parcels", response_model=ParcelMissionResponse)
def run_mission_parcels(payload: ParcelMissionRequest) -> ParcelMissionResponse:
    return service.run_mission_parcels(payload)


@app.post("/api/v1/mission/run-parcels-live", response_model=LiveParcelMissionResponse)
def run_mission_parcels_live(payload: ParcelMissionRequest) -> LiveParcelMissionResponse:
    try:
        return service.run_live_parcel_mission(payload)
    except ValueError as exc:
        if str(exc) == "RESTART_CONFIRM_REQUIRED":
            raise HTTPException(status_code=409, detail="RESTART_CONFIRM_REQUIRED") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/mission/run-parcels-live/start", response_model=LiveMissionJobAcceptedResponse)
def start_mission_parcels_live(payload: ParcelMissionRequest) -> LiveMissionJobAcceptedResponse:
    try:
        return service.start_live_parcel_mission(payload)
    except ValueError as exc:
        if str(exc) == "RESTART_CONFIRM_REQUIRED":
            raise HTTPException(status_code=409, detail="RESTART_CONFIRM_REQUIRED") from exc
        if str(exc) == "LIVE_MISSION_ALREADY_RUNNING":
            raise HTTPException(status_code=409, detail="LIVE_MISSION_ALREADY_RUNNING") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/mission/jobs/{job_id}", response_model=LiveMissionJobStatusResponse)
def get_mission_job(job_id: str) -> LiveMissionJobStatusResponse:
    try:
        return service.get_live_mission_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/mission/jobs/{job_id}/stream")
def stream_mission_job(job_id: str) -> StreamingResponse:
    def event_stream():
        while True:
            try:
                snapshot = service.get_live_mission_job(job_id)
            except ValueError:
                yield "event: error\ndata: {\"detail\":\"MISSION_JOB_NOT_FOUND\"}\n\n"
                break

            payload = snapshot.model_dump_json()
            yield f"data: {payload}\n\n"
            if snapshot.status in {"COMPLETE", "PARTIAL", "FAILED", "STOPPED"}:
                break
            time.sleep(1.0)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/v1/mission/stop", response_model=DroneStatusResponse)
def stop_live_mission(payload: StopMissionRequest) -> DroneStatusResponse:
    return service.stop_live_mission(payload)


@app.post("/api/v1/mission/restart-confirm")
def restart_confirm(payload: RestartConfirmRequest) -> dict[str, str | bool]:
    try:
        return service.confirm_restart_after_stop(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/mission/stop-events", response_model=list[StopEventLogItem])
def get_stop_events() -> list[StopEventLogItem]:
    return service.list_stop_events()


@app.post("/api/v1/detection/simulate", response_model=SimulateDetectionResponse)
def simulate_detection(payload: SimulateDetectionRequest) -> SimulateDetectionResponse:
    return service.simulate_detection(payload)


@app.post("/api/v1/detection/image", response_model=ImageDetectionResponse)
async def detect_from_image(file: UploadFile = File(...)) -> ImageDetectionResponse:
    image_bytes = await file.read()
    return service.detect_image(image_bytes)


@app.post("/api/v1/geometry/import", response_model=GeometryImportResponse)
def import_geometry(payload: GeometryImportRequest) -> GeometryImportResponse:
    return service.import_geometry(payload)


@app.post("/api/v1/geometry/export", response_model=GeometryExportResponse)
def export_geometry(payload: GeometryExportRequest) -> GeometryExportResponse:
    return service.export_geometry(payload)


@app.post("/api/v1/geometry/parcelize", response_model=ParcelizeResponse)
def parcelize_geometry(payload: ParcelizeRequest) -> ParcelizeResponse:
    return service.parcelize(payload)


@app.post("/api/v1/config/reload")
def reload_config() -> dict[str, str]:
    service.reload_config()
    return {"status": "reloaded"}


@app.post("/api/v1/drone/connect", response_model=DroneStatusResponse)
def connect_drone(payload: DroneConnectRequest) -> DroneStatusResponse:
    return service.connect_drone(payload)


@app.post("/api/v1/drone/disconnect", response_model=DroneStatusResponse)
def disconnect_drone() -> DroneStatusResponse:
    return service.disconnect_drone()


@app.get("/api/v1/drone/status", response_model=DroneStatusResponse)
def drone_status() -> DroneStatusResponse:
    return service.get_drone_status()


@app.post("/api/v1/drone/arm", response_model=DroneStatusResponse)
def arm_drone() -> DroneStatusResponse:
    return service.arm_drone()


@app.post("/api/v1/drone/takeoff", response_model=DroneStatusResponse)
def takeoff_drone(payload: DroneTakeoffRequest) -> DroneStatusResponse:
    return service.drone_takeoff(payload)


@app.post("/api/v1/drone/goto", response_model=DroneStatusResponse)
def goto_drone(payload: DroneGotoRequest) -> DroneStatusResponse:
    return service.drone_goto(payload)


@app.post("/api/v1/drone/land", response_model=DroneStatusResponse)
def land_drone() -> DroneStatusResponse:
    return service.drone_land()


@app.post("/api/v1/drone/failsafe", response_model=DroneStatusResponse)
def failsafe_drone(payload: DroneFailsafeRequest) -> DroneStatusResponse:
    return service.drone_failsafe(payload)


@app.post("/api/v1/drone/stop", response_model=DroneStatusResponse)
def stop_drone() -> DroneStatusResponse:
    return service.drone_stop()


app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")
