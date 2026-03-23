from fastapi.testclient import TestClient

from otonom.api import app


client = TestClient(app)


def test_geometry_geojson_import_export_roundtrip() -> None:
    geojson = {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [32.8540, 39.9207],
                    [32.8543, 39.9207],
                    [32.8543, 39.9209],
                    [32.8540, 39.9209],
                    [32.8540, 39.9207],
                ]
            ],
        },
        "properties": {},
    }

    imported = client.post("/api/v1/geometry/import", json={"format": "geojson", "content": __import__("json").dumps(geojson)})
    assert imported.status_code == 200
    body = imported.json()
    assert body["area_ha"] > 0
    assert len(body["coordinates"]) >= 4

    exported = client.post(
        "/api/v1/geometry/export",
        json={"format": "geojson", "coordinates": body["coordinates"]},
    )
    assert exported.status_code == 200
    assert "Polygon" in exported.json()["content"]
