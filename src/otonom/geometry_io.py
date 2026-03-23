from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass


@dataclass(slots=True)
class AreaGeometry:
    coordinates: list[tuple[float, float]]  # (lat, lon)

    @property
    def center(self) -> tuple[float, float]:
        if not self.coordinates:
            return 0.0, 0.0
        lat = sum(c[0] for c in self.coordinates) / len(self.coordinates)
        lon = sum(c[1] for c in self.coordinates) / len(self.coordinates)
        return lat, lon

    @property
    def area_ha(self) -> float:
        if len(self.coordinates) < 3:
            return 0.0
        # Shoelace on local projection for field-sized polygons.
        mean_lat = sum(c[0] for c in self.coordinates) / len(self.coordinates)
        meters: list[tuple[float, float]] = []
        for lat, lon in self.coordinates:
            y = lat * 111_111.0
            x = lon * 111_111.0 * math.cos(math.radians(mean_lat))
            meters.append((x, y))

        area = 0.0
        for i in range(len(meters)):
            x1, y1 = meters[i]
            x2, y2 = meters[(i + 1) % len(meters)]
            area += x1 * y2 - x2 * y1
        area_m2 = abs(area) * 0.5
        return area_m2 / 10_000.0


def import_geojson(content: str) -> AreaGeometry:
    payload = json.loads(content)
    geom = payload
    if payload.get("type") == "Feature":
        geom = payload.get("geometry", {})
    if payload.get("type") == "FeatureCollection":
        features = payload.get("features", [])
        if not features:
            return AreaGeometry(coordinates=[])
        geom = features[0].get("geometry", {})

    if geom.get("type") != "Polygon":
        raise ValueError("GeoJSON yalnizca Polygon destekliyor")

    ring = geom.get("coordinates", [[]])[0]
    coords = [(float(lat), float(lon)) for lon, lat in ring]
    return AreaGeometry(coordinates=coords)


def export_geojson(area: AreaGeometry) -> str:
    coords = [[lon, lat] for lat, lon in area.coordinates]
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    payload = {
        "type": "Feature",
        "properties": {},
        "geometry": {"type": "Polygon", "coordinates": [coords]},
    }
    return json.dumps(payload, ensure_ascii=True, indent=2)


def import_kml(content: str) -> AreaGeometry:
    root = ET.fromstring(content)
    ns = {
        "kml": "http://www.opengis.net/kml/2.2",
    }
    node = root.find(".//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", ns)
    if node is None or not node.text:
        raise ValueError("KML polygon coordinates bulunamadi")

    coords: list[tuple[float, float]] = []
    for row in node.text.strip().split():
        parts = row.split(",")
        lon = float(parts[0])
        lat = float(parts[1])
        coords.append((lat, lon))

    return AreaGeometry(coordinates=coords)


def export_kml(area: AreaGeometry) -> str:
    coords = [f"{lon},{lat},0" for lat, lon in area.coordinates]
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    joined = " ".join(coords)
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<kml xmlns=\"http://www.opengis.net/kml/2.2\">"
        "<Document><Placemark><Polygon><outerBoundaryIs><LinearRing><coordinates>"
        f"{joined}"
        "</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark></Document></kml>"
    )


def _point_in_polygon(lat: float, lon: float, polygon: list[tuple[float, float]]) -> bool:
    inside = False
    n = len(polygon)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        yi, xi = polygon[i]
        yj, xj = polygon[j]
        intersects = ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / ((yj - yi) + 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def parcelize_geometry(area: AreaGeometry, rows: int, cols: int) -> list[list[tuple[float, float]]]:
    if len(area.coordinates) < 3:
        return []

    coords = area.coordinates[:]
    if coords[0] == coords[-1]:
        coords = coords[:-1]

    lats = [c[0] for c in coords]
    lons = [c[1] for c in coords]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    dlat = (max_lat - min_lat) / rows if rows else 0.0
    dlon = (max_lon - min_lon) / cols if cols else 0.0
    if dlat == 0.0 or dlon == 0.0:
        return []

    parcels: list[list[tuple[float, float]]] = []
    for r in range(rows):
        for c in range(cols):
            a_lat = min_lat + r * dlat
            b_lat = a_lat + dlat
            a_lon = min_lon + c * dlon
            b_lon = a_lon + dlon

            center_lat = (a_lat + b_lat) / 2.0
            center_lon = (a_lon + b_lon) / 2.0
            if not _point_in_polygon(center_lat, center_lon, coords):
                continue

            parcel = [
                (a_lat, a_lon),
                (a_lat, b_lon),
                (b_lat, b_lon),
                (b_lat, a_lon),
                (a_lat, a_lon),
            ]
            parcels.append(parcel)
    return parcels
