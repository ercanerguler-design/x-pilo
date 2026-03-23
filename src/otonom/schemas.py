from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field


class PoseInput(BaseModel):
    lat: float = Field(..., description="Latitude")
    lon: float = Field(..., description="Longitude")
    alt_m: float = Field(..., ge=0, description="Altitude in meters")
    yaw_deg: float = Field(0.0, description="Yaw angle")


class SafetyInput(BaseModel):
    rtk_fix: bool = True
    battery_pct: float = Field(80.0, ge=0, le=100)
    wind_mps: float = Field(3.0, ge=0)
    link_ok: bool = True
    human_detected: bool = False


class RunMissionRequest(BaseModel):
    pose: PoseInput
    safety: SafetyInput
    frame_count: int = Field(8, ge=1, le=500)
    no_spray_zones: List[List[List[float]]] = Field(default_factory=list)
    manual_approval_required: bool = False
    approved_target_ids: List[str] = Field(default_factory=list)


class ServicedTargetResponse(BaseModel):
    target_id: str
    parcel_id: str | None = None
    target_lat: float
    target_lon: float
    sequence: int
    event_time_s: float
    success: bool
    method: str
    duration_sec: float
    note: str


class RunMissionResponse(BaseModel):
    state: str
    states: List[str]
    aborted_reason: str | None
    serviced_targets: List[ServicedTargetResponse]


class SimulateDetectionRequest(BaseModel):
    frame_count: int = Field(5, ge=1, le=500)


class DetectionItem(BaseModel):
    id: str
    label: str
    confidence: float
    image_x: float
    image_y: float


class SimulateDetectionResponse(BaseModel):
    model: Literal["deterministic-mvp"]
    detections: List[DetectionItem]


class ImageDetectionResponse(BaseModel):
    backend: str
    detections: List[DetectionItem]


class GeometryImportRequest(BaseModel):
    format: Literal["geojson", "kml"]
    content: str


class GeometryImportResponse(BaseModel):
    center_lat: float
    center_lon: float
    area_ha: float
    coordinates: List[List[float]]


class GeometryExportRequest(BaseModel):
    format: Literal["geojson", "kml"]
    coordinates: List[List[float]]


class GeometryExportResponse(BaseModel):
    format: Literal["geojson", "kml"]
    content: str


class ParcelizeRequest(BaseModel):
    coordinates: List[List[float]]
    rows: int = Field(2, ge=1, le=100)
    cols: int = Field(2, ge=1, le=100)


class ParcelPolygon(BaseModel):
    parcel_id: str
    coordinates: List[List[float]]


class ParcelizeResponse(BaseModel):
    rows: int
    cols: int
    parcel_count: int
    parcels: List[ParcelPolygon]


class ParcelMissionRequest(BaseModel):
    parcels: List[ParcelPolygon]
    safety: SafetyInput
    frame_count: int = Field(8, ge=1, le=500)
    alt_m: float = Field(8.0, ge=0)
    yaw_deg: float = 0.0
    scan_orientation: Literal["horizontal", "vertical"] = "horizontal"
    lane_spacing_m: float = Field(4.0, ge=1.0, le=20.0)
    sample_spacing_m: float = Field(6.0, ge=1.0, le=30.0)
    no_spray_zones: List[List[List[float]]] = Field(default_factory=list)
    manual_approval_required: bool = False
    approved_target_ids: List[str] = Field(default_factory=list)
    restart_confirmed: bool = False


class ParcelMissionItem(BaseModel):
    parcel_id: str
    state: str
    aborted_reason: str | None
    serviced_target_count: int
    scan_path: List[List[float]] = Field(default_factory=list)


class ParcelMissionResponse(BaseModel):
    state: str
    total_parcels: int
    completed_parcels: int
    failed_parcels: int
    parcel_results: List[ParcelMissionItem]
    serviced_targets: List[ServicedTargetResponse]


class DroneConnectRequest(BaseModel):
    backend: Literal["sim", "mavsdk"] = "sim"
    connection_uri: str | None = "udp://:14540"


class DroneTakeoffRequest(BaseModel):
    alt_m: float = Field(8.0, ge=1.0, le=120.0)


class DroneGotoRequest(BaseModel):
    lat: float
    lon: float
    alt_m: float = Field(..., ge=1.0, le=120.0)


class DroneFailsafeRequest(BaseModel):
    action: Literal["rtl", "land", "hold"] = "rtl"


class DroneTelemetryResponse(BaseModel):
    lat: float
    lon: float
    alt_m: float
    battery_pct: float
    ground_speed_mps: float
    heading_deg: float
    link_ok: bool
    last_update_s: float


class DroneStatusResponse(BaseModel):
    backend: str
    connected: bool
    state: str
    message: str
    telemetry: DroneTelemetryResponse


class DroneSelfCheckRequest(BaseModel):
    operator_id: str = Field("operator", min_length=1, max_length=64)
    camera_ok: bool | None = None
    payload_ok: bool | None = None


class DroneSelfCheckResponse(BaseModel):
    backend: str
    camera_ok: bool
    payload_ok: bool
    source: str
    checked_at: str


class LiveParcelMissionResponse(ParcelMissionResponse):
    drone_status: DroneStatusResponse


class StopMissionRequest(BaseModel):
    operator_id: str = Field("operator", min_length=1, max_length=64)


class RestartConfirmRequest(BaseModel):
    operator_id: str = Field("operator", min_length=1, max_length=64)
    confirmation_token: Literal["CONFIRM"] = "CONFIRM"


class StopEventLogItem(BaseModel):
    operator_id: str
    requested_at: str
    job_id: str | None = None
    parcel_id: str | None = None
    reason: str


class LiveMissionJobAcceptedResponse(BaseModel):
    job_id: str
    status: str
    message: str
    total_parcels: int


class LiveMissionJobStatusResponse(BaseModel):
    job_id: str
    status: str
    message: str
    created_at: str
    updated_at: str
    total_parcels: int
    completed_parcels: int
    active_parcel_id: str | None = None
    next_parcel_id: str | None = None
    stop_events: List[StopEventLogItem] = Field(default_factory=list)
    result: LiveParcelMissionResponse | None = None
