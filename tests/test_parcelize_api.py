from fastapi.testclient import TestClient

from otonom.api import app


client = TestClient(app)


def test_parcelize_endpoint_returns_cells() -> None:
    payload = {
        "coordinates": [
            [39.9207, 32.8540],
            [39.9207, 32.8546],
            [39.9211, 32.8546],
            [39.9211, 32.8540],
            [39.9207, 32.8540],
        ],
        "rows": 3,
        "cols": 4,
    }

    response = client.post("/api/v1/geometry/parcelize", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["rows"] == 3
    assert body["cols"] == 4
    assert body["parcel_count"] > 0
    assert len(body["parcels"]) == body["parcel_count"]
