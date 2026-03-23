from fastapi.testclient import TestClient

from otonom.api import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_run_mission_endpoint() -> None:
    payload = {
        "pose": {"lat": 39.9208, "lon": 32.8541, "alt_m": 8.0, "yaw_deg": 0.0},
        "safety": {
            "rtk_fix": True,
            "battery_pct": 90,
            "wind_mps": 3.5,
            "link_ok": True,
            "human_detected": False,
        },
        "frame_count": 6,
    }

    response = client.post("/api/v1/mission/run", json=payload)
    body = response.json()

    assert response.status_code == 200
    assert body["state"] in {"COMPLETE", "ABORT"}
    assert "states" in body


def test_simulate_detection_endpoint() -> None:
    response = client.post("/api/v1/detection/simulate", json={"frame_count": 4})
    body = response.json()

    assert response.status_code == 200
    assert body["model"] == "deterministic-mvp"
    assert len(body["detections"]) >= 4


def test_run_parcels_mission_endpoint() -> None:
    payload = {
        "parcels": [
            {
                "parcel_id": "P1",
                "coordinates": [
                    [39.9200, 32.8540],
                    [39.9200, 32.8550],
                    [39.9210, 32.8550],
                    [39.9210, 32.8540],
                ],
            },
            {
                "parcel_id": "P2",
                "coordinates": [
                    [39.9210, 32.8540],
                    [39.9210, 32.8550],
                    [39.9220, 32.8550],
                    [39.9220, 32.8540],
                ],
            },
        ],
        "safety": {
            "rtk_fix": True,
            "battery_pct": 85,
            "wind_mps": 3.0,
            "link_ok": True,
            "human_detected": False,
        },
        "frame_count": 6,
        "alt_m": 10,
        "yaw_deg": 0,
    }

    response = client.post("/api/v1/mission/run-parcels", json=payload)
    body = response.json()

    assert response.status_code == 200
    assert body["total_parcels"] == 2
    assert body["completed_parcels"] + body["failed_parcels"] == 2
    assert len(body["parcel_results"]) == 2


def test_drone_status_and_connect_endpoints() -> None:
    before = client.get("/api/v1/drone/status")
    assert before.status_code == 200
    assert "connected" in before.json()

    connect = client.post(
        "/api/v1/drone/connect",
        json={"backend": "sim", "connection_uri": "udp://:14540"},
    )
    assert connect.status_code == 200
    assert connect.json()["connected"] is True


def test_live_parcel_mission_endpoint() -> None:
    client.post("/api/v1/drone/connect", json={"backend": "sim", "connection_uri": "udp://:14540"})
    payload = {
        "parcels": [
            {
                "parcel_id": "P1",
                "coordinates": [
                    [39.9200, 32.8540],
                    [39.9200, 32.8550],
                    [39.9210, 32.8550],
                    [39.9210, 32.8540],
                ],
            }
        ],
        "safety": {
            "rtk_fix": True,
            "battery_pct": 85,
            "wind_mps": 3.0,
            "link_ok": True,
            "human_detected": False,
        },
        "frame_count": 6,
        "alt_m": 10,
        "yaw_deg": 0,
    }

    response = client.post("/api/v1/mission/run-parcels-live", json=payload)
    body = response.json()
    assert response.status_code == 200
    assert body["total_parcels"] == 1
    assert "drone_status" in body


def test_drone_command_endpoints() -> None:
    client.post("/api/v1/drone/connect", json={"backend": "sim", "connection_uri": "udp://:14540"})

    arm = client.post("/api/v1/drone/arm")
    assert arm.status_code == 200

    takeoff = client.post("/api/v1/drone/takeoff", json={"alt_m": 12})
    assert takeoff.status_code == 200
    assert takeoff.json()["state"] in {"AIRBORNE", "CONNECTED"}

    goto = client.post("/api/v1/drone/goto", json={"lat": 39.9208, "lon": 32.8541, "alt_m": 10})
    assert goto.status_code == 200

    failsafe = client.post("/api/v1/drone/failsafe", json={"action": "rtl"})
    assert failsafe.status_code == 200

    land = client.post("/api/v1/drone/land")
    assert land.status_code == 200


def test_manual_approval_and_no_spray_blocking() -> None:
    payload = {
        "pose": {"lat": 39.9208, "lon": 32.8541, "alt_m": 8.0, "yaw_deg": 0.0},
        "safety": {
            "rtk_fix": True,
            "battery_pct": 90,
            "wind_mps": 3.5,
            "link_ok": True,
            "human_detected": False,
        },
        "frame_count": 8,
        "manual_approval_required": True,
        "approved_target_ids": [],
        "no_spray_zones": [[[39.9200, 32.8530], [39.9200, 32.8560], [39.9220, 32.8560], [39.9220, 32.8530]]],
    }

    response = client.post("/api/v1/mission/run", json=payload)
    assert response.status_code == 200
    body = response.json()
    notes = [item["note"] for item in body["serviced_targets"]]
    assert any("no-spray" in note.lower() or "manual approval" in note.lower() for note in notes)
