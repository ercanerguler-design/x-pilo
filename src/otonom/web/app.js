const form = document.getElementById("mission-form");
const simulateBtn = document.getElementById("simulate-btn");
const runParcelsBtn = document.getElementById("run-parcels-btn");
const runLiveBtn = document.getElementById("run-live-btn");
const findLocationBtn = document.getElementById("find-location-btn");
const geometryFileInput = document.getElementById("geometry-file");
const exportGeoJsonBtn = document.getElementById("export-geojson");
const exportKmlBtn = document.getElementById("export-kml");
const toggleHeatmapBtn = document.getElementById("toggle-heatmap");
const playbackPlayBtn = document.getElementById("playback-play");
const playbackPauseBtn = document.getElementById("playback-pause");
const sprayPreviewBtn = document.getElementById("spray-preview-btn");
const playbackSlider = document.getElementById("playback-slider");
const playbackLabel = document.getElementById("playback-label");
const parcelRowsInput = document.getElementById("parcel-rows");
const parcelColsInput = document.getElementById("parcel-cols");
const scanOrientationInput = document.getElementById("scan-orientation");
const laneSpacingInput = document.getElementById("lane-spacing");
const sampleSpacingInput = document.getElementById("sample-spacing");
const routeQualityInput = document.getElementById("route-quality");
const parcelizeBtn = document.getElementById("parcelize-btn");
const droneBackendSelect = document.getElementById("drone-backend");
const droneUriInput = document.getElementById("drone-uri");
const droneConnectBtn = document.getElementById("drone-connect-btn");
const droneDisconnectBtn = document.getElementById("drone-disconnect-btn");
const droneRefreshBtn = document.getElementById("drone-refresh-btn");
const droneArmBtn = document.getElementById("drone-arm-btn");
const droneTakeoffBtn = document.getElementById("drone-takeoff-btn");
const droneGotoBtn = document.getElementById("drone-goto-btn");
const droneLandBtn = document.getElementById("drone-land-btn");
const droneFailsafeBtn = document.getElementById("drone-failsafe-btn");
const droneAutoRefreshInput = document.getElementById("drone-auto-refresh");
const droneRefreshIntervalInput = document.getElementById("drone-refresh-interval");

const drawnAreaNode = document.getElementById("drawn-area");
const selectedCenterNode = document.getElementById("selected-center");
const targetCountNode = document.getElementById("target-count");
const parcelCountNode = document.getElementById("parcel-count");
const stateNode = document.getElementById("state");
const servicedNode = document.getElementById("serviced");
const abortNode = document.getElementById("abort");
const timelineNode = document.getElementById("timeline");
const parcelProgressSummaryNode = document.getElementById("parcel-progress-summary");
const parcelProgressBodyNode = document.getElementById("parcel-progress-body");
const liveActiveParcelNode = document.getElementById("live-active-parcel");
const liveNextParcelNode = document.getElementById("live-next-parcel");
const liveCompletedParcelsNode = document.getElementById("live-completed-parcels");
const interventionsNode = document.getElementById("interventions");
const rawOutputNode = document.getElementById("raw-output");
const droneStatusNode = document.getElementById("drone-status");
const droneBackendValueNode = document.getElementById("drone-backend-value");
const droneBatteryNode = document.getElementById("drone-battery");
const droneSpeedNode = document.getElementById("drone-speed");
const droneTelemetryNode = document.getElementById("drone-telemetry");
const sprayVolumeNode = document.getElementById("spray-volume");

let map;
let centerMarker;
let drawnLayerGroup;
let targetLayerGroup;
let parcelLayerGroup;
let routeLayerGroup;
let sprayLayerGroup;
let heatLayer;
let heatVisible = false;
let missionTargets = [];
let playbackTimer = null;
let sprayPreviewTimer = null;
let currentParcels = [];
let routeDashTimer = null;
let droneAnimationTimer = null;
let droneMarker = null;
let currentDroneTelemetry = null;
let totalSprayMl = 0;
let droneStatusTimer = null;
let droneStatusInFlight = false;
let lastDroneHeadingDeg = 0;
let routeAnimationActive = false;

function getPayload() {
  const data = new FormData(form);
  const approved = (data.get("approved_target_ids") || "")
    .toString()
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);

  const noSpray = [];
  if (data.get("use_drawn_no_spray") === "on") {
    const drawn = coordinatesFromDrawnLayer();
    if (drawn.length >= 3) {
      noSpray.push(drawn);
    }
  }

  return {
    pose: {
      lat: Number(data.get("lat")),
      lon: Number(data.get("lon")),
      alt_m: Number(data.get("alt_m")),
      yaw_deg: Number(data.get("yaw_deg"))
    },
    safety: {
      rtk_fix: data.get("rtk_fix") === "on",
      battery_pct: Number(data.get("battery_pct")),
      wind_mps: Number(data.get("wind_mps")),
      wind_dir_deg: Number(data.get("wind_dir_deg") || 0),
      link_ok: data.get("link_ok") === "on",
      human_detected: data.get("human_detected") === "on"
    },
    frame_count: Number(data.get("frame_count")),
    no_spray_zones: noSpray,
    manual_approval_required: data.get("manual_approval_required") === "on",
    approved_target_ids: approved
  };
}

function setupMap() {
  map = L.map("map", { zoomControl: true }).setView([39.9208, 32.8541], 16);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 22,
    attribution: "&copy; OpenStreetMap contributors"
  }).addTo(map);

  drawnLayerGroup = new L.FeatureGroup();
  targetLayerGroup = new L.FeatureGroup();
  parcelLayerGroup = new L.FeatureGroup();
  routeLayerGroup = new L.FeatureGroup();
  sprayLayerGroup = new L.FeatureGroup();
  map.addLayer(drawnLayerGroup);
  map.addLayer(targetLayerGroup);
  map.addLayer(parcelLayerGroup);
  map.addLayer(routeLayerGroup);
  map.addLayer(sprayLayerGroup);

  centerMarker = L.marker([39.9208, 32.8541], { draggable: true }).addTo(map);
  centerMarker.bindPopup("Mission Center");

  centerMarker.on("dragend", () => {
    const { lat, lng } = centerMarker.getLatLng();
    updateCenter(lat, lng);
  });

  map.on("click", (e) => {
    centerMarker.setLatLng(e.latlng);
    updateCenter(e.latlng.lat, e.latlng.lng);
  });

  const drawControl = new L.Control.Draw({
    position: "topright",
    draw: {
      polygon: {
        allowIntersection: false,
        showArea: true
      },
      rectangle: true,
      polyline: false,
      circle: false,
      circlemarker: false,
      marker: false
    },
    edit: {
      featureGroup: drawnLayerGroup,
      edit: true,
      remove: true
    }
  });
  map.addControl(drawControl);

  map.on(L.Draw.Event.CREATED, (event) => {
    drawnLayerGroup.clearLayers();
    parcelLayerGroup.clearLayers();
    clearRoute();
    parcelCountNode.textContent = "0";
    drawnLayerGroup.addLayer(event.layer);
    updateDrawnArea(event.layer);
  });

  map.on(L.Draw.Event.EDITED, (event) => {
    event.layers.eachLayer((layer) => updateDrawnArea(layer));
  });

  map.on(L.Draw.Event.DELETED, () => {
    drawnAreaNode.textContent = "0.00 ha";
    parcelLayerGroup.clearLayers();
    clearRoute();
    parcelCountNode.textContent = "0";
  });
}

function updateCenter(lat, lon) {
  form.elements.lat.value = lat.toFixed(6);
  form.elements.lon.value = lon.toFixed(6);
  selectedCenterNode.textContent = `${lat.toFixed(6)}, ${lon.toFixed(6)}`;
}

function updateDrawnArea(layer) {
  const latLngs = layer.getLatLngs();
  if (!latLngs || !latLngs.length) {
    drawnAreaNode.textContent = "0.00 ha";
    return;
  }

  const points = latLngs[0] || [];
  if (points.length < 3) {
    drawnAreaNode.textContent = "0.00 ha";
    return;
  }

  const areaM2 = Math.abs(L.GeometryUtil.geodesicArea(points));
  const areaHa = areaM2 / 10000;
  drawnAreaNode.textContent = `${areaHa.toFixed(2)} ha`;
}

function clearTargets() {
  targetLayerGroup.clearLayers();
  sprayLayerGroup.clearLayers();
  if (heatLayer) {
    heatLayer.remove();
    heatLayer = null;
  }
  targetCountNode.textContent = "0";
}

function sprayColor(success) {
  return success ? "#2a9d8f" : "#e76f51";
}

function toRad(deg) {
  return (deg * Math.PI) / 180;
}

function offsetPoint(lat, lon, meters, headingDeg) {
  const theta = toRad(headingDeg);
  const dLat = (meters * Math.cos(theta)) / 111111.0;
  const dLon = (meters * Math.sin(theta)) / (111111.0 * Math.cos(toRad(lat)));
  return [lat + dLat, lon + dLon];
}

function drawNozzleCone(originLat, originLon, headingDeg, success) {
  const lengthM = 8;
  const halfSpreadDeg = 18;
  const left = offsetPoint(originLat, originLon, lengthM, headingDeg - halfSpreadDeg);
  const right = offsetPoint(originLat, originLon, lengthM, headingDeg + halfSpreadDeg);
  const cone = L.polygon([[originLat, originLon], left, right], {
    color: sprayColor(success),
    fillColor: sprayColor(success),
    fillOpacity: 0.2,
    opacity: 0.85,
    weight: 1.5,
  }).addTo(sprayLayerGroup);
  setTimeout(() => sprayLayerGroup.removeLayer(cone), 650);
}

function drawDrift(originLat, originLon, windMps, windDirDeg, success) {
  const puffs = Math.max(3, Math.min(7, Math.round(windMps)));
  for (let i = 1; i <= puffs; i += 1) {
    const driftMeters = i * (1.2 + windMps * 0.4);
    const jitter = (i % 2 === 0 ? -1 : 1) * 7;
    const pt = offsetPoint(originLat, originLon, driftMeters, windDirDeg + jitter);
    const puff = L.circleMarker(pt, {
      radius: 2 + i * 0.5,
      color: sprayColor(success),
      fillColor: sprayColor(success),
      fillOpacity: Math.max(0.08, 0.24 - i * 0.03),
      opacity: Math.max(0.1, 0.45 - i * 0.05),
      weight: 1,
    }).addTo(sprayLayerGroup);
    setTimeout(() => sprayLayerGroup.removeLayer(puff), 520 + i * 80);
  }
}

function addSprayVolume(target) {
  const dur = Number(target?.duration_sec || 0);
  const mlPerSec = 5.5;
  totalSprayMl += dur > 0 ? dur * mlPerSec : 0.9;
  sprayVolumeNode.textContent = `${totalSprayMl.toFixed(1)} ml`;
}

function triggerSprayPulse(target) {
  if (!target || !sprayLayerGroup) {
    return;
  }

  const originLat = currentDroneTelemetry?.lat ?? target.target_lat;
  const originLon = currentDroneTelemetry?.lon ?? target.target_lon;
  const heading = Number(currentDroneTelemetry?.heading_deg ?? 0);
  const windMps = Number(form.elements.wind_mps.value || 0);
  const windDir = Number(form.elements.wind_dir_deg.value || 0);

  drawNozzleCone(originLat, originLon, heading, target.success);
  drawDrift(originLat, originLon, windMps, windDir, target.success);
  addSprayVolume(target);

  const pulse = L.circleMarker([target.target_lat, target.target_lon], {
    radius: 6,
    color: sprayColor(target.success),
    fillColor: sprayColor(target.success),
    fillOpacity: 0.38,
    opacity: 0.9,
    weight: 2,
  }).addTo(sprayLayerGroup);

  let frame = 0;
  const maxFrames = 10;
  const timer = setInterval(() => {
    frame += 1;
    const progress = frame / maxFrames;
    pulse.setStyle({
      radius: 6 + progress * 24,
      fillOpacity: Math.max(0, 0.38 - progress * 0.38),
      opacity: Math.max(0, 0.9 - progress * 0.9),
      weight: Math.max(1, 2 - progress),
    });

    if (frame >= maxFrames) {
      clearInterval(timer);
      sprayLayerGroup.removeLayer(pulse);
    }
  }, 70);
}

function stopRouteAnimation() {
  routeAnimationActive = false;
  if (routeDashTimer) {
    clearInterval(routeDashTimer);
    routeDashTimer = null;
  }
  if (droneAnimationTimer) {
    clearInterval(droneAnimationTimer);
    droneAnimationTimer = null;
  }
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function normalize180(deg) {
  let out = deg;
  while (out > 180) {
    out -= 360;
  }
  while (out < -180) {
    out += 360;
  }
  return out;
}

function visualFromFlight(headingDeg, speedMps, altM, bankDeg = null, pitchDeg = null) {
  const speed = Number(speedMps || 0);
  const alt = Number(altM || 0);
  const heading = Number(headingDeg || 0);

  const turnDelta = normalize180(heading - lastDroneHeadingDeg);
  const bank = bankDeg != null ? Number(bankDeg) : clamp(turnDelta * 0.55, -18, 18);
  const pitch = pitchDeg != null ? Number(pitchDeg) : clamp(speed * 1.1, 0, 11);
  const scale = clamp(1.12 - alt * 0.024, 0.72, 1.14);
  const rotorDuration = clamp(0.45 - speed * 0.045, 0.09, 0.45);

  return { heading, bank, pitch, scale, rotorDuration };
}

function applyDroneVisual(el, visual) {
  if (!el || !visual) {
    return;
  }
  el.style.setProperty("--heading", `${visual.heading.toFixed(1)}deg`);
  el.style.setProperty("--bank", `${visual.bank.toFixed(1)}deg`);
  el.style.setProperty("--pitch", `${visual.pitch.toFixed(1)}deg`);
  el.style.setProperty("--drone-scale", `${visual.scale.toFixed(3)}`);
  el.style.setProperty("--rotor-duration", `${visual.rotorDuration.toFixed(3)}s`);
}

function headingFromPoints(from, to) {
  if (!from || !to) {
    return 0;
  }
  const dLat = to[0] - from[0];
  const dLon = to[1] - from[1];
  const angleDeg = (Math.atan2(dLon, dLat) * 180) / Math.PI;
  return (angleDeg + 360) % 360;
}

function droneIconHtml(headingDeg) {
  return `
    <div class="drone-aircraft" style="--heading:${Number(headingDeg || 0).toFixed(1)}deg;">
      <span class="drone-arm drone-arm-a"></span>
      <span class="drone-arm drone-arm-b"></span>
      <span class="drone-rotor rotor-nw"></span>
      <span class="drone-rotor rotor-ne"></span>
      <span class="drone-rotor rotor-sw"></span>
      <span class="drone-rotor rotor-se"></span>
      <span class="drone-body"></span>
      <span class="drone-nose"></span>
    </div>
  `;
}

function removeDroneMarker() {
  if (droneMarker && routeLayerGroup) {
    routeLayerGroup.removeLayer(droneMarker);
  }
  droneMarker = null;
}

function placeDroneMarker(point, headingDeg = 0, flightVisual = {}) {
  if (!point) {
    return;
  }

  const visual = visualFromFlight(
    headingDeg,
    flightVisual.speedMps ?? currentDroneTelemetry?.ground_speed_mps,
    flightVisual.altM ?? currentDroneTelemetry?.alt_m ?? Number(form.elements.alt_m.value || 8),
    flightVisual.bankDeg ?? null,
    flightVisual.pitchDeg ?? null,
  );

  if (!droneMarker) {
    droneMarker = L.marker(point, {
      icon: L.divIcon({
        className: "drone-icon-wrapper",
        html: droneIconHtml(headingDeg),
        iconSize: [60, 60],
        iconAnchor: [30, 30],
      })
    }).addTo(routeLayerGroup);
    const elNew = droneMarker.getElement();
    if (elNew) {
      const aircraftNew = elNew.querySelector(".drone-aircraft");
      applyDroneVisual(aircraftNew, visual);
    }
    lastDroneHeadingDeg = visual.heading;
    return;
  }

  droneMarker.setLatLng(point);
  const el = droneMarker.getElement();
  if (el) {
    const aircraft = el.querySelector(".drone-aircraft");
    if (aircraft) {
      applyDroneVisual(aircraft, visual);
    }
  }
  lastDroneHeadingDeg = visual.heading;
}

function clearRoute() {
  stopRouteAnimation();
  removeDroneMarker();
  if (routeLayerGroup) {
    routeLayerGroup.clearLayers();
  }
}

function getParcelCenter(parcel) {
  const points = parcel.coordinates || [];
  if (!points.length) {
    return null;
  }
  let lat = 0;
  let lon = 0;
  points.forEach((p) => {
    lat += Number(p[0]);
    lon += Number(p[1]);
  });
  return [lat / points.length, lon / points.length];
}

function downsamplePath(path, maxPoints) {
  if (!Array.isArray(path) || path.length <= maxPoints) {
    return path || [];
  }
  const step = Math.ceil(path.length / maxPoints);
  const sampled = [];
  for (let i = 0; i < path.length; i += step) {
    sampled.push(path[i]);
  }
  const last = path[path.length - 1];
  const tail = sampled[sampled.length - 1];
  if (!tail || tail[0] !== last[0] || tail[1] !== last[1]) {
    sampled.push(last);
  }
  return sampled;
}

function downsampleRouteWithParcelIds(points, parcelIds, maxPoints) {
  if (!Array.isArray(points) || points.length <= maxPoints) {
    return { points: points || [], parcelIds: parcelIds || [] };
  }

  const safeMax = Math.max(2, Number(maxPoints || 2));
  const step = Math.ceil(points.length / safeMax);
  const sampledPoints = [];
  const sampledParcelIds = [];

  for (let i = 0; i < points.length; i += step) {
    sampledPoints.push(points[i]);
    sampledParcelIds.push(parcelIds[i]);
  }

  const lastIdx = points.length - 1;
  const tail = sampledPoints[sampledPoints.length - 1];
  const last = points[lastIdx];
  if (!tail || tail[0] !== last[0] || tail[1] !== last[1]) {
    sampledPoints.push(last);
    sampledParcelIds.push(parcelIds[lastIdx]);
  }

  return { points: sampledPoints, parcelIds: sampledParcelIds };
}

function getRouteRenderProfile(totalPoints) {
  const mode = routeQualityInput?.value || "auto";

  if (mode === "performance") {
    return {
      maxPoints: 260,
      markerMax: 26,
      dashTickMs: 120,
      animationTickMs: 70,
      segmentSpeed: 0.042,
    };
  }

  if (mode === "detailed") {
    return {
      maxPoints: 900,
      markerMax: 75,
      dashTickMs: 70,
      animationTickMs: 40,
      segmentSpeed: 0.025,
    };
  }

  if (totalPoints > 2400) {
    return {
      maxPoints: 300,
      markerMax: 28,
      dashTickMs: 120,
      animationTickMs: 70,
      segmentSpeed: 0.044,
    };
  }

  if (totalPoints > 1200) {
    return {
      maxPoints: 420,
      markerMax: 40,
      dashTickMs: 100,
      animationTickMs: 60,
      segmentSpeed: 0.036,
    };
  }

  return {
    maxPoints: 620,
    markerMax: 55,
    dashTickMs: 85,
    animationTickMs: 50,
    segmentSpeed: 0.03,
  };
}

function renderParcelRoute(parcelResults) {
  clearRoute();
  if (!Array.isArray(parcelResults) || !parcelResults.length) {
    return;
  }

  const parcelById = new Map();
  currentParcels.forEach((parcel) => {
    parcelById.set(parcel.parcel_id, parcel);
  });

  const routePoints = [];
  const routeParcelIds = [];
  parcelResults.forEach((item) => {
    if (Array.isArray(item.scan_path) && item.scan_path.length) {
      const compactPath = downsamplePath(item.scan_path, 90);
      compactPath.forEach((pt) => {
        if (!Array.isArray(pt) || pt.length < 2) {
          return;
        }
        const p = [Number(pt[0]), Number(pt[1])];
        const prev = routePoints[routePoints.length - 1];
        if (!prev || prev[0] !== p[0] || prev[1] !== p[1]) {
          routePoints.push(p);
          routeParcelIds.push(item.parcel_id);
        }
      });
      return;
    }

    const parcel = parcelById.get(item.parcel_id);
    if (!parcel) {
      return;
    }
    const center = getParcelCenter(parcel);
    if (center) {
      routePoints.push(center);
      routeParcelIds.push(item.parcel_id);
    }
  });

  const orderedParcelIds = parcelResults.map((p) => p.parcel_id);

  const profile = getRouteRenderProfile(routePoints.length);
  const compact = downsampleRouteWithParcelIds(routePoints, routeParcelIds, profile.maxPoints);
  const routePointsCompact = compact.points;
  const routeParcelIdsCompact = compact.parcelIds;

  if (!routePointsCompact.length) {
    return;
  }

  if (routePointsCompact.length === 1) {
    placeDroneMarker(routePointsCompact[0], Number(currentDroneTelemetry?.heading_deg ?? 0), {
      speedMps: 0,
      altM: currentDroneTelemetry?.alt_m ?? Number(form.elements.alt_m.value || 8),
    });
    updateLiveParcelStatus(routeParcelIdsCompact[0] || "-", "-", routeParcelIdsCompact[0] ? 0 : 0, orderedParcelIds.length);
    return;
  }

  const base = L.polyline(routePointsCompact, {
    color: "#274c77",
    weight: 3,
    opacity: 0.55,
  }).addTo(routeLayerGroup);

  const animated = L.polyline(routePointsCompact, {
    color: "#f4a261",
    weight: 5,
    opacity: 0.95,
    dashArray: "14 10",
    lineCap: "round",
  }).addTo(routeLayerGroup);

  const markerStep = Math.max(1, Math.ceil(routePointsCompact.length / profile.markerMax));
  routePointsCompact.forEach((point, idx) => {
    if (idx % markerStep !== 0 && idx !== routePointsCompact.length - 1) {
      return;
    }
    L.circleMarker(point, {
      radius: 4,
      color: "#1d3557",
      fillColor: "#ffd166",
      fillOpacity: 1,
      weight: 2,
    })
      .bindTooltip(`P${idx + 1}`, { direction: "top", offset: [0, -4] })
      .addTo(routeLayerGroup);
  });

  let dashOffset = 0;
  routeAnimationActive = true;
  routeDashTimer = setInterval(() => {
    dashOffset = (dashOffset + 2) % 200;
    animated.setStyle({ dashOffset: String(-dashOffset) });
  }, profile.dashTickMs);

  let segment = 0;
  let progress = 0;
  const speed = profile.segmentSpeed;
  updateLiveParcelStatus(routeParcelIdsCompact[0] || "-", orderedParcelIds[1] || "-", 0, orderedParcelIds.length);
  placeDroneMarker(routePointsCompact[0], headingFromPoints(routePointsCompact[0], routePointsCompact[1]), {
    speedMps: 6,
    altM: currentDroneTelemetry?.alt_m ?? Number(form.elements.alt_m.value || 8),
  });
  droneAnimationTimer = setInterval(() => {
    if (segment >= routePointsCompact.length - 1) {
      stopRouteAnimation();
      updateLiveParcelStatus("-", "-", orderedParcelIds.length, orderedParcelIds.length);
      placeDroneMarker(routePointsCompact[routePointsCompact.length - 1], Number(currentDroneTelemetry?.heading_deg ?? 0), {
        speedMps: 0,
        altM: currentDroneTelemetry?.alt_m ?? Number(form.elements.alt_m.value || 8),
      });
      return;
    }

    const from = routePointsCompact[segment];
    const to = routePointsCompact[segment + 1];
    progress += speed;

    if (progress >= 1) {
      segment += 1;
      progress = 0;
      const idx = Math.min(segment, routePointsCompact.length - 1);
      const nextIdx = Math.min(idx + 1, routePointsCompact.length - 1);
      const activeParcel = routeParcelIdsCompact[idx] || "-";
      const activeParcelIdx = orderedParcelIds.indexOf(activeParcel);
      const completedCount = activeParcelIdx > -1 ? activeParcelIdx : 0;
      const nextParcel = activeParcelIdx > -1 ? (orderedParcelIds[activeParcelIdx + 1] || "-") : "-";
      updateLiveParcelStatus(activeParcel, nextParcel, completedCount, orderedParcelIds.length);
      placeDroneMarker(routePointsCompact[idx], headingFromPoints(routePointsCompact[idx], routePointsCompact[nextIdx]), {
        speedMps: 5.4,
        altM: currentDroneTelemetry?.alt_m ?? Number(form.elements.alt_m.value || 8),
      });
      return;
    }

    const lat = from[0] + (to[0] - from[0]) * progress;
    const lon = from[1] + (to[1] - from[1]) * progress;
    placeDroneMarker([lat, lon], headingFromPoints(from, to), {
      speedMps: 6.2,
      altM: currentDroneTelemetry?.alt_m ?? Number(form.elements.alt_m.value || 8),
    });
  }, profile.animationTickMs);

  const bounds = L.latLngBounds(routePointsCompact);
  map.fitBounds(bounds.pad(0.25), { animate: true, duration: 0.7 });
  base.bringToBack();
}

function markerColor(success) {
  return success
    ? { stroke: "#0a7f8e", fill: "#99d98c" }
    : { stroke: "#9d0208", fill: "#ff8fa3" };
}

function renderTargets(targets, maxSequence = targets.length) {
  clearTargets();
  const filtered = targets.filter((t) => t.sequence <= maxSequence);
  filtered.forEach((t) => {
    const colors = markerColor(t.success);
    const marker = L.circleMarker([t.target_lat, t.target_lon], {
      radius: 8,
      color: colors.stroke,
      fillColor: colors.fill,
      fillOpacity: 0.9,
      weight: 2
    }).addTo(targetLayerGroup);

    marker.bindPopup(
      `<strong>${t.target_id}</strong><br/>Seq: ${t.sequence}<br/>Method: ${t.method}<br/>T: ${t.event_time_s}s<br/>Success: ${t.success}`
    );

    // Keep a subtle persistent spray footprint so operators can see where
    // spraying has occurred even when pulse animation is not running.
    if (t.success) {
      L.circleMarker([t.target_lat, t.target_lon], {
        radius: 13,
        color: "#2a9d8f",
        fillColor: "#2a9d8f",
        fillOpacity: 0.08,
        opacity: 0.25,
        weight: 1,
      }).addTo(sprayLayerGroup);
    }
  });

  targetCountNode.textContent = String(filtered.length);
  refreshHeatmap(filtered);
}

function refreshHeatmap(targets) {
  if (!heatVisible) {
    return;
  }
  const points = targets.map((t) => [t.target_lat, t.target_lon, Math.max(0.3, t.success ? 0.9 : 0.6)]);
  heatLayer = L.heatLayer(points, { radius: 32, blur: 20, maxZoom: 18, minOpacity: 0.2 }).addTo(map);
}

function toggleHeatmap() {
  heatVisible = !heatVisible;
  toggleHeatmapBtn.textContent = heatVisible ? "Heatmap Kapat" : "Heatmap Ac/Kapat";
  renderTargets(missionTargets, Number(playbackSlider.value));
}

function setPlayback(total) {
  playbackSlider.max = String(total);
  playbackSlider.value = String(total);
  playbackLabel.textContent = `Adim: ${total} / ${total}`;
}

function renderMission(data) {
  stateNode.textContent = data.state;
  servicedNode.textContent = String(data.serviced_targets.length);
  abortNode.textContent = data.aborted_reason || "-";

  missionTargets = [...data.serviced_targets].sort((a, b) => a.sequence - b.sequence);
  setPlayback(missionTargets.length);
  renderTargets(missionTargets, missionTargets.length);

  timelineNode.innerHTML = "";
  const states = Array.isArray(data.states) ? data.states : [];
  states.forEach((s) => {
    const li = document.createElement("li");
    li.textContent = s;
    timelineNode.appendChild(li);
  });

  interventionsNode.innerHTML = "";
  missionTargets.forEach((t) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${t.target_id}</td>
      <td>${t.parcel_id || "-"}</td>
      <td>${t.method}</td>
      <td>${t.duration_sec}s</td>
      <td class="${t.success ? "success" : "fail"}">${t.success ? "Yes" : "No"}</td>
      <td>${t.note}</td>
    `;
    interventionsNode.appendChild(tr);
  });

  rawOutputNode.textContent = JSON.stringify(data, null, 2);

  // Automatically preview spray events so the operator sees spray behavior
  // without manually starting playback after each mission run.
  if (missionTargets.length > 0 && missionTargets.length <= 40) {
    setTimeout(() => {
      playPlayback();
    }, 220);
  }
}

function renderParcelProgress(parcelResults, completedParcels = null, totalParcels = null) {
  const rows = Array.isArray(parcelResults) ? parcelResults : [];
  parcelProgressBodyNode.innerHTML = "";

  if (!rows.length) {
    parcelProgressSummaryNode.textContent = "Parsel gorevi henuz calismadi.";
    updateLiveParcelStatus("-", "-", 0, 0);
    return;
  }

  const total = totalParcels ?? rows.length;
  const completed = completedParcels ?? rows.filter((p) => p.state === "COMPLETE").length;
  parcelProgressSummaryNode.textContent = `Tamamlanan parsel: ${completed}/${total}`;
  const firstPending = rows.find((p) => p.state !== "COMPLETE")?.parcel_id || "-";
  const nextAfterPending = rows.find((p, idx) => p.parcel_id === firstPending && rows[idx + 1])?.parcel_id || "-";
  updateLiveParcelStatus(firstPending, nextAfterPending, completed, total);

  rows.forEach((p) => {
    const tr = document.createElement("tr");
    const ok = p.state === "COMPLETE";
    tr.innerHTML = `
      <td>${p.parcel_id}</td>
      <td><span class="parcel-status ${ok ? "complete" : "partial"}">${p.state}</span></td>
      <td>${p.serviced_target_count ?? 0}</td>
      <td>${p.aborted_reason || "-"}</td>
    `;
    parcelProgressBodyNode.appendChild(tr);
  });
}

function updateLiveParcelStatus(activeParcel, nextParcel, completedCount, totalCount) {
  liveActiveParcelNode.textContent = activeParcel || "-";
  liveNextParcelNode.textContent = nextParcel || "-";
  const total = Number(totalCount || 0);
  const done = Number(completedCount || 0);
  liveCompletedParcelsNode.textContent = total > 0 ? `${done}/${total}` : "0";
}

function renderDroneStatus(data) {
  if (!data) {
    return;
  }
  droneStatusNode.textContent = data.state || "-";
  droneBackendValueNode.textContent = data.backend || "-";
  const telemetry = data.telemetry || {};
  currentDroneTelemetry = telemetry;
  droneBatteryNode.textContent = telemetry.battery_pct != null ? `${telemetry.battery_pct}%` : "-";
  droneSpeedNode.textContent = telemetry.ground_speed_mps != null ? `${telemetry.ground_speed_mps} m/s` : "-";
  if (telemetry.lat != null && telemetry.lon != null) {
    droneTelemetryNode.textContent = `${Number(telemetry.lat).toFixed(6)}, ${Number(telemetry.lon).toFixed(6)} @ ${Number(telemetry.alt_m || 0).toFixed(1)}m`;
    if (routeLayerGroup && map && !routeAnimationActive) {
      placeDroneMarker([Number(telemetry.lat), Number(telemetry.lon)], Number(telemetry.heading_deg || 0), {
        speedMps: Number(telemetry.ground_speed_mps || 0),
        altM: Number(telemetry.alt_m || 0),
      });
    }
  } else {
    droneTelemetryNode.textContent = "-";
  }
}

async function runMission(evt) {
  evt.preventDefault();
  clearRoute();
  renderParcelProgress([]);
  updateLiveParcelStatus("-", "-", 0, 0);
  totalSprayMl = 0;
  sprayVolumeNode.textContent = "0 ml";
  const payload = getPayload();

  const res = await fetch("/api/v1/mission/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  const json = await res.json();
  renderMission(json);
}

async function runParcelsMission() {
  if (!currentParcels.length) {
    alert("Once Parsel Uret ile parselleri olusturmalisin.");
    return;
  }

  const base = getPayload();
  const payload = {
    parcels: currentParcels,
    safety: base.safety,
    frame_count: base.frame_count,
    alt_m: base.pose.alt_m,
    yaw_deg: base.pose.yaw_deg,
    scan_orientation: scanOrientationInput.value || "horizontal",
    lane_spacing_m: Number(laneSpacingInput.value || 4),
    sample_spacing_m: Number(sampleSpacingInput.value || 6),
    no_spray_zones: base.no_spray_zones,
    manual_approval_required: base.manual_approval_required,
    approved_target_ids: base.approved_target_ids,
  };

  runParcelsBtn.disabled = true;
  totalSprayMl = 0;
  sprayVolumeNode.textContent = "0 ml";
  runParcelsBtn.textContent = "Parseller Taraniyor...";
  try {
    const res = await fetch("/api/v1/mission/run-parcels", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    const adapted = {
      state: data.state,
      states: (data.parcel_results || []).map((p) => `${p.parcel_id}: ${p.state}`),
      aborted_reason: data.failed_parcels > 0 ? `${data.failed_parcels} parcel failed` : null,
      serviced_targets: data.serviced_targets || []
    };
    renderMission(adapted);
    renderParcelProgress(data.parcel_results || [], data.completed_parcels, data.total_parcels);
    renderParcelRoute(data.parcel_results || []);
    stateNode.textContent = `${data.state} (${data.completed_parcels}/${data.total_parcels})`;
  } finally {
    runParcelsBtn.disabled = false;
    runParcelsBtn.textContent = "Tum Parselleri Tara";
  }
}

async function runLiveParcelsMission() {
  if (!currentParcels.length) {
    alert("Once Parsel Uret ile parselleri olusturmalisin.");
    return;
  }

  const base = getPayload();
  const payload = {
    parcels: currentParcels,
    safety: base.safety,
    frame_count: base.frame_count,
    alt_m: base.pose.alt_m,
    yaw_deg: base.pose.yaw_deg,
    scan_orientation: scanOrientationInput.value || "horizontal",
    lane_spacing_m: Number(laneSpacingInput.value || 4),
    sample_spacing_m: Number(sampleSpacingInput.value || 6),
    no_spray_zones: base.no_spray_zones,
    manual_approval_required: base.manual_approval_required,
    approved_target_ids: base.approved_target_ids,
  };

  runLiveBtn.disabled = true;
  totalSprayMl = 0;
  sprayVolumeNode.textContent = "0 ml";
  runLiveBtn.textContent = "Canli Gorev Isleniyor...";
  try {
    const res = await fetch("/api/v1/mission/run-parcels-live", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    const adapted = {
      state: data.state,
      states: (data.parcel_results || []).map((p) => `${p.parcel_id}: ${p.state}`),
      aborted_reason: data.failed_parcels > 0 ? `${data.failed_parcels} parcel failed` : null,
      serviced_targets: data.serviced_targets || []
    };
    renderMission(adapted);
    renderParcelProgress(data.parcel_results || [], data.completed_parcels, data.total_parcels);
    renderParcelRoute(data.parcel_results || []);
    renderDroneStatus(data.drone_status);
    stateNode.textContent = `${data.state} (${data.completed_parcels}/${data.total_parcels})`;
  } finally {
    runLiveBtn.disabled = false;
    runLiveBtn.textContent = "Canli Drone Gorevi";
  }
}

async function connectDrone() {
  const payload = {
    backend: droneBackendSelect.value,
    connection_uri: droneUriInput.value || null,
  };
  const res = await fetch("/api/v1/drone/connect", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  renderDroneStatus(data);
  rawOutputNode.textContent = JSON.stringify(data, null, 2);
}

async function disconnectDrone() {
  const res = await fetch("/api/v1/drone/disconnect", { method: "POST" });
  const data = await res.json();
  renderDroneStatus(data);
  rawOutputNode.textContent = JSON.stringify(data, null, 2);
}

async function refreshDroneStatus() {
  if (droneStatusInFlight) {
    return;
  }

  droneStatusInFlight = true;
  try {
    const res = await fetch("/api/v1/drone/status");
    const data = await res.json();
    renderDroneStatus(data);
  } catch (err) {
    droneStatusNode.textContent = "OFFLINE";
  } finally {
    droneStatusInFlight = false;
  }
}

function stopDroneStatusAutoRefresh() {
  if (droneStatusTimer) {
    clearInterval(droneStatusTimer);
    droneStatusTimer = null;
  }
}

function startDroneStatusAutoRefresh() {
  stopDroneStatusAutoRefresh();
  if (!droneAutoRefreshInput?.checked) {
    return;
  }

  const sec = Number(droneRefreshIntervalInput?.value || 2);
  const intervalMs = Math.max(1000, sec * 1000);
  droneStatusTimer = setInterval(() => {
    refreshDroneStatus();
  }, intervalMs);
}

function onDroneAutoRefreshSettingsChanged() {
  if (droneAutoRefreshInput?.checked) {
    refreshDroneStatus();
  }
  startDroneStatusAutoRefresh();
}

async function armDrone() {
  const res = await fetch("/api/v1/drone/arm", { method: "POST" });
  const data = await res.json();
  renderDroneStatus(data);
}

async function takeoffDrone() {
  const alt = Number(form.elements.alt_m.value || 8);
  const res = await fetch("/api/v1/drone/takeoff", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ alt_m: alt })
  });
  const data = await res.json();
  renderDroneStatus(data);
}

async function gotoCenterDrone() {
  const lat = Number(form.elements.lat.value);
  const lon = Number(form.elements.lon.value);
  const alt = Number(form.elements.alt_m.value || 8);
  const res = await fetch("/api/v1/drone/goto", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lat, lon, alt_m: alt })
  });
  const data = await res.json();
  renderDroneStatus(data);
}

async function landDrone() {
  const res = await fetch("/api/v1/drone/land", { method: "POST" });
  const data = await res.json();
  renderDroneStatus(data);
}

async function failsafeDrone() {
  const res = await fetch("/api/v1/drone/failsafe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action: "rtl" })
  });
  const data = await res.json();
  renderDroneStatus(data);
}

async function simulateDetection() {
  const payload = { frame_count: getPayload().frame_count };

  const res = await fetch("/api/v1/detection/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  const json = await res.json();
  rawOutputNode.textContent = JSON.stringify(json, null, 2);
}

function coordinatesFromDrawnLayer() {
  const layers = drawnLayerGroup.getLayers();
  if (!layers.length) {
    return [];
  }
  const points = layers[0].getLatLngs()[0] || [];
  return points.map((p) => [p.lat, p.lng]);
}

function downloadText(filename, content) {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

async function exportGeometry(format) {
  const coordinates = coordinatesFromDrawnLayer();
  if (!coordinates.length) {
    alert("Once haritada bir alan cizmelisin.");
    return;
  }

  const res = await fetch("/api/v1/geometry/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ format, coordinates })
  });
  const data = await res.json();
  downloadText(`field_area.${format === "geojson" ? "geojson" : "kml"}`, data.content);
}

async function importGeometry(file) {
  const extension = file.name.toLowerCase().endsWith(".kml") ? "kml" : "geojson";
  const content = await file.text();

  const res = await fetch("/api/v1/geometry/import", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ format: extension, content })
  });
  const data = await res.json();

  const layer = L.polygon(data.coordinates.map((c) => [c[0], c[1]]));
  drawnLayerGroup.clearLayers();
  parcelLayerGroup.clearLayers();
  clearRoute();
  parcelCountNode.textContent = "0";
  drawnLayerGroup.addLayer(layer);

  centerMarker.setLatLng([data.center_lat, data.center_lon]);
  map.setView([data.center_lat, data.center_lon], 16);
  updateCenter(data.center_lat, data.center_lon);
  drawnAreaNode.textContent = `${Number(data.area_ha).toFixed(2)} ha`;
}

function renderParcels(parcels) {
  parcelLayerGroup.clearLayers();
  clearRoute();
  currentParcels = parcels;
  parcels.forEach((parcel, idx) => {
    const hue = (idx * 47) % 360;
    const polygon = L.polygon(parcel.coordinates.map((c) => [c[0], c[1]]), {
      color: `hsl(${hue}, 55%, 42%)`,
      fillColor: `hsl(${hue}, 65%, 65%)`,
      fillOpacity: 0.25,
      weight: 1.5,
    }).addTo(parcelLayerGroup);
    polygon.bindTooltip(parcel.parcel_id, { permanent: false });
  });
  parcelCountNode.textContent = String(parcels.length);
}

async function parcelizeGeometry() {
  const coordinates = coordinatesFromDrawnLayer();
  if (!coordinates.length) {
    alert("Once haritada bir alan cizmelisin.");
    return;
  }

  const rows = Number(parcelRowsInput.value || 0);
  const cols = Number(parcelColsInput.value || 0);
  if (rows < 1 || cols < 1) {
    alert("Rows ve Cols en az 1 olmali.");
    return;
  }

  const res = await fetch("/api/v1/geometry/parcelize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ coordinates, rows, cols })
  });
  const data = await res.json();
  renderParcels(data.parcels || []);
  rawOutputNode.textContent = JSON.stringify(data, null, 2);
}

function findCurrentLocation() {
  if (!navigator.geolocation) {
    alert("Tarayici konum servisini desteklemiyor.");
    return;
  }

  const previousText = findLocationBtn?.textContent;
  if (findLocationBtn) {
    findLocationBtn.disabled = true;
    findLocationBtn.textContent = "Konum Araniyor...";
  }

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const lat = Number(pos.coords.latitude);
      const lon = Number(pos.coords.longitude);
      centerMarker.setLatLng([lat, lon]);
      map.setView([lat, lon], 17, { animate: true });
      updateCenter(lat, lon);
      rawOutputNode.textContent = JSON.stringify(
        {
          location: {
            lat,
            lon,
            accuracy_m: Number(pos.coords.accuracy || 0),
          },
          source: "browser_geolocation",
        },
        null,
        2,
      );
      if (findLocationBtn) {
        findLocationBtn.disabled = false;
        findLocationBtn.textContent = previousText || "Konumu Bul";
      }
    },
    (err) => {
      let msg = "Konum alinamadi.";
      if (err?.code === 1) {
        msg = "Konum izni reddedildi. Tarayici izinlerini acip tekrar dene.";
      } else if (err?.code === 2) {
        msg = "Konum bilgisi su an mevcut degil.";
      } else if (err?.code === 3) {
        msg = "Konum istegi zaman asimina ugradi.";
      }
      alert(msg);
      if (findLocationBtn) {
        findLocationBtn.disabled = false;
        findLocationBtn.textContent = previousText || "Konumu Bul";
      }
    },
    {
      enableHighAccuracy: true,
      timeout: 15000,
      maximumAge: 15000,
    },
  );
}

function pausePlayback() {
  if (playbackTimer) {
    clearInterval(playbackTimer);
    playbackTimer = null;
  }
}

function stopSprayPreview() {
  if (sprayPreviewTimer) {
    clearInterval(sprayPreviewTimer);
    sprayPreviewTimer = null;
  }
}

function playSprayPreview() {
  if (!missionTargets.length) {
    return;
  }
  stopSprayPreview();

  const maxEvents = 60;
  const stride = Math.max(1, Math.ceil(missionTargets.length / maxEvents));
  const previewTargets = missionTargets.filter((_, idx) => idx % stride === 0);
  let idx = 0;

  sprayPreviewTimer = setInterval(() => {
    if (idx >= previewTargets.length) {
      stopSprayPreview();
      return;
    }
    triggerSprayPulse(previewTargets[idx]);
    idx += 1;
  }, 130);
}

function playPlayback() {
  if (!missionTargets.length) {
    return;
  }
  stopSprayPreview();
  pausePlayback();
  sprayLayerGroup.clearLayers();
  playbackSlider.value = "0";

  playbackTimer = setInterval(() => {
    const current = Number(playbackSlider.value);
    const next = current + 1;
    if (next > missionTargets.length) {
      pausePlayback();
      return;
    }
    playbackSlider.value = String(next);
    playbackLabel.textContent = `Adim: ${next} / ${missionTargets.length}`;
    renderTargets(missionTargets, next);
    triggerSprayPulse(missionTargets[next - 1]);
  }, 650);
}

function onPlaybackManualChange() {
  const current = Number(playbackSlider.value);
  playbackLabel.textContent = `Adim: ${current} / ${missionTargets.length}`;
  renderTargets(missionTargets, current);
  sprayLayerGroup.clearLayers();
  if (current > 0 && missionTargets[current - 1]) {
    triggerSprayPulse(missionTargets[current - 1]);
  }
}

window.addEventListener("beforeunload", () => {
  stopRouteAnimation();
  removeDroneMarker();
  pausePlayback();
  stopSprayPreview();
  stopDroneStatusAutoRefresh();
});

setupMap();

form.addEventListener("submit", runMission);
simulateBtn.addEventListener("click", simulateDetection);
exportGeoJsonBtn.addEventListener("click", () => exportGeometry("geojson"));
exportKmlBtn.addEventListener("click", () => exportGeometry("kml"));
toggleHeatmapBtn.addEventListener("click", toggleHeatmap);
geometryFileInput.addEventListener("change", (evt) => {
  const file = evt.target.files?.[0];
  if (file) {
    importGeometry(file);
  }
});
playbackPlayBtn.addEventListener("click", playPlayback);
playbackPauseBtn.addEventListener("click", pausePlayback);
sprayPreviewBtn.addEventListener("click", playSprayPreview);
playbackSlider.addEventListener("input", onPlaybackManualChange);
parcelizeBtn.addEventListener("click", parcelizeGeometry);
runParcelsBtn.addEventListener("click", runParcelsMission);
runLiveBtn.addEventListener("click", runLiveParcelsMission);
findLocationBtn?.addEventListener("click", findCurrentLocation);
droneConnectBtn.addEventListener("click", connectDrone);
droneDisconnectBtn.addEventListener("click", disconnectDrone);
droneRefreshBtn.addEventListener("click", refreshDroneStatus);
droneArmBtn.addEventListener("click", armDrone);
droneTakeoffBtn.addEventListener("click", takeoffDrone);
droneGotoBtn.addEventListener("click", gotoCenterDrone);
droneLandBtn.addEventListener("click", landDrone);
droneFailsafeBtn.addEventListener("click", failsafeDrone);
droneAutoRefreshInput.addEventListener("change", onDroneAutoRefreshSettingsChanged);
droneRefreshIntervalInput.addEventListener("change", onDroneAutoRefreshSettingsChanged);
refreshDroneStatus();
startDroneStatusAutoRefresh();
