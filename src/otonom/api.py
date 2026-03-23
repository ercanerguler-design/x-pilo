from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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
    ParcelMissionRequest,
    ParcelMissionResponse,
    ParcelizeRequest,
    ParcelizeResponse,
    RunMissionRequest,
    RunMissionResponse,
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
    return service.run_live_parcel_mission(payload)


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


app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")
