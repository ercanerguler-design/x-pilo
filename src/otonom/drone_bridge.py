from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass


@dataclass(slots=True)
class DroneTelemetry:
    lat: float
    lon: float
    alt_m: float
    battery_pct: float
    ground_speed_mps: float
    heading_deg: float
    link_ok: bool
    last_update_s: float


@dataclass(slots=True)
class DroneStatus:
    backend: str
    connected: bool
    state: str
    message: str
    telemetry: DroneTelemetry


class DroneBridge:
    def connect(self, connection_uri: str | None = None) -> DroneStatus:
        raise NotImplementedError

    def disconnect(self) -> DroneStatus:
        raise NotImplementedError

    def fly_to(self, lat: float, lon: float, alt_m: float) -> DroneStatus:
        raise NotImplementedError

    def arm(self) -> DroneStatus:
        raise NotImplementedError

    def takeoff(self, alt_m: float) -> DroneStatus:
        raise NotImplementedError

    def land(self) -> DroneStatus:
        raise NotImplementedError

    def failsafe(self, action: str) -> DroneStatus:
        raise NotImplementedError

    def stop(self) -> DroneStatus:
        raise NotImplementedError

    def status(self) -> DroneStatus:
        raise NotImplementedError


class SimulatedDroneBridge(DroneBridge):
    def __init__(self) -> None:
        self._connected = False
        self._state = "DISCONNECTED"
        self._message = "Simulated drone not connected"
        self._telemetry = DroneTelemetry(
            lat=39.9208,
            lon=32.8541,
            alt_m=0.0,
            battery_pct=92.0,
            ground_speed_mps=0.0,
            heading_deg=0.0,
            link_ok=True,
            last_update_s=time.time(),
        )

    def connect(self, connection_uri: str | None = None) -> DroneStatus:
        _ = connection_uri
        self._connected = True
        self._state = "CONNECTED"
        self._message = "Simulated drone ready"
        self._telemetry.link_ok = True
        self._telemetry.last_update_s = time.time()
        return self.status()

    def disconnect(self) -> DroneStatus:
        self._connected = False
        self._state = "DISCONNECTED"
        self._message = "Simulated drone not connected"
        self._telemetry.ground_speed_mps = 0.0
        self._telemetry.last_update_s = time.time()
        return self.status()

    def fly_to(self, lat: float, lon: float, alt_m: float) -> DroneStatus:
        if not self._connected:
            return self.status()
        if self._state in {"STOPPED", "FAILSAFE_HOLD"}:
            self._telemetry.ground_speed_mps = 0.0
            self._telemetry.last_update_s = time.time()
            return self.status()
        self._telemetry.lat = lat
        self._telemetry.lon = lon
        self._telemetry.alt_m = alt_m
        self._telemetry.ground_speed_mps = 6.0
        self._telemetry.heading_deg = (self._telemetry.heading_deg + 25.0) % 360.0
        self._telemetry.battery_pct = max(5.0, round(self._telemetry.battery_pct - 0.3, 2))
        self._telemetry.last_update_s = time.time()
        self._state = "IN_MISSION"
        self._message = "Simulated waypoint reached"
        return self.status()

    def arm(self) -> DroneStatus:
        if not self._connected:
            return self.status()
        self._state = "ARMED"
        self._message = "Simulated arm success"
        self._telemetry.last_update_s = time.time()
        return DroneStatus(
            backend="sim",
            connected=True,
            state="ARMED",
            message="Simulated arm success",
            telemetry=self._telemetry,
        )

    def takeoff(self, alt_m: float) -> DroneStatus:
        if not self._connected:
            return self.status()
        self._telemetry.alt_m = max(1.0, alt_m)
        self._telemetry.ground_speed_mps = 2.5
        self._telemetry.last_update_s = time.time()
        self._state = "AIRBORNE"
        self._message = f"Simulated takeoff to {alt_m:.1f}m"
        return DroneStatus(
            backend="sim",
            connected=True,
            state="AIRBORNE",
            message=f"Simulated takeoff to {alt_m:.1f}m",
            telemetry=self._telemetry,
        )

    def land(self) -> DroneStatus:
        if not self._connected:
            return self.status()
        self._telemetry.alt_m = 0.0
        self._telemetry.ground_speed_mps = 0.0
        self._telemetry.last_update_s = time.time()
        self._state = "LANDED"
        self._message = "Simulated landing complete"
        return DroneStatus(
            backend="sim",
            connected=True,
            state="LANDED",
            message="Simulated landing complete",
            telemetry=self._telemetry,
        )

    def failsafe(self, action: str) -> DroneStatus:
        action_name = action.lower().strip()
        if action_name == "rtl":
            self._telemetry.lat = 39.9208
            self._telemetry.lon = 32.8541
            self._telemetry.alt_m = 6.0
            self._telemetry.ground_speed_mps = 5.0
            self._telemetry.last_update_s = time.time()
            self._state = "FAILSAFE_RTL"
            self._message = "Simulated RTL triggered"
            return DroneStatus(
                backend="sim",
                connected=self._connected,
                state="FAILSAFE_RTL",
                message="Simulated RTL triggered",
                telemetry=self._telemetry,
            )
        if action_name == "land":
            return self.land()
        self._telemetry.ground_speed_mps = 0.0
        self._telemetry.last_update_s = time.time()
        self._state = "FAILSAFE_HOLD"
        self._message = "Simulated hold triggered"
        return DroneStatus(
            backend="sim",
            connected=self._connected,
            state="FAILSAFE_HOLD",
            message="Simulated hold triggered",
            telemetry=self._telemetry,
        )

    def stop(self) -> DroneStatus:
        if not self._connected:
            return self.status()
        self._telemetry.ground_speed_mps = 0.0
        self._telemetry.last_update_s = time.time()
        self._state = "STOPPED"
        self._message = "Operator stop requested"
        return DroneStatus(
            backend="sim",
            connected=True,
            state="STOPPED",
            message="Operator stop requested",
            telemetry=self._telemetry,
        )

    def status(self) -> DroneStatus:
        state = self._state if self._connected else "DISCONNECTED"
        message = self._message if self._connected else "Simulated drone not connected"
        return DroneStatus(
            backend="sim",
            connected=self._connected,
            state=state,
            message=message,
            telemetry=self._telemetry,
        )


class MavsdkDroneBridge(DroneBridge):
    def __init__(self) -> None:
        self._connected = False
        self._state = "DISCONNECTED"
        self._message = "MAVSDK not connected"
        self._system = None
        self._telemetry = DroneTelemetry(
            lat=0.0,
            lon=0.0,
            alt_m=0.0,
            battery_pct=0.0,
            ground_speed_mps=0.0,
            heading_deg=0.0,
            link_ok=False,
            last_update_s=time.time(),
        )

    def _run(self, coro) -> None:
        asyncio.run(coro)

    async def _connect_async(self, connection_uri: str | None) -> None:
        from mavsdk import System  # type: ignore

        self._system = System()
        await self._system.connect(system_address=connection_uri or "udp://:14540")
        async for state in self._system.core.connection_state():
            if state.is_connected:
                self._connected = True
                break
        await self._refresh_async()

    async def _refresh_async(self) -> None:
        if not self._system or not self._connected:
            return
        async for battery in self._system.telemetry.battery():
            self._telemetry.battery_pct = round(float(battery.remaining_percent) * 100.0, 2)
            break
        async for pos in self._system.telemetry.position():
            self._telemetry.lat = float(pos.latitude_deg)
            self._telemetry.lon = float(pos.longitude_deg)
            self._telemetry.alt_m = float(pos.relative_altitude_m)
            break
        async for vel in self._system.telemetry.velocity_ned():
            self._telemetry.ground_speed_mps = round(
                (float(vel.north_m_s) ** 2 + float(vel.east_m_s) ** 2) ** 0.5,
                2,
            )
            break
        async for heading in self._system.telemetry.heading():
            self._telemetry.heading_deg = float(heading.heading_deg)
            break
        self._telemetry.link_ok = True
        self._telemetry.last_update_s = time.time()

    async def _arm_async(self) -> None:
        await self._system.action.arm()
        await self._refresh_async()

    async def _takeoff_async(self, alt_m: float) -> None:
        await self._system.action.set_takeoff_altitude(float(alt_m))
        await self._system.action.takeoff()
        await self._refresh_async()

    async def _goto_async(self, lat: float, lon: float, alt_m: float) -> None:
        await self._system.action.goto_location(float(lat), float(lon), float(alt_m), 0.0)
        await self._refresh_async()

    async def _land_async(self) -> None:
        await self._system.action.land()
        await self._refresh_async()

    async def _failsafe_async(self, action: str) -> None:
        action_name = action.lower().strip()
        if action_name == "rtl":
            await self._system.action.return_to_launch()
        elif action_name == "land":
            await self._system.action.land()
        elif action_name == "hold":
            hold_fn = getattr(self._system.action, "hold", None)
            if hold_fn is not None:
                await hold_fn()
        await self._refresh_async()

    def connect(self, connection_uri: str | None = None) -> DroneStatus:
        self._run(self._connect_async(connection_uri))
        self._state = "CONNECTED"
        self._message = "MAVSDK drone ready"
        return self.status()

    def disconnect(self) -> DroneStatus:
        self._connected = False
        self._state = "DISCONNECTED"
        self._message = "MAVSDK not connected"
        self._telemetry.link_ok = False
        self._telemetry.ground_speed_mps = 0.0
        self._telemetry.last_update_s = time.time()
        return self.status()

    def fly_to(self, lat: float, lon: float, alt_m: float) -> DroneStatus:
        if not self._connected:
            return self.status()
        if self._state in {"STOPPED", "FAILSAFE_HOLD"}:
            self._telemetry.ground_speed_mps = 0.0
            self._telemetry.last_update_s = time.time()
            return self.status()
        self._run(self._goto_async(lat, lon, alt_m))
        self._state = "IN_MISSION"
        self._message = "MAVSDK waypoint command sent"
        return self.status()

    def arm(self) -> DroneStatus:
        if not self._connected:
            return self.status()
        self._run(self._arm_async())
        self._state = "ARMED"
        self._message = "MAVSDK arm success"
        return DroneStatus(
            backend="mavsdk",
            connected=True,
            state="ARMED",
            message="MAVSDK arm success",
            telemetry=self._telemetry,
        )

    def takeoff(self, alt_m: float) -> DroneStatus:
        if not self._connected:
            return self.status()
        self._run(self._takeoff_async(alt_m))
        self._state = "AIRBORNE"
        self._message = f"MAVSDK takeoff to {alt_m:.1f}m"
        return DroneStatus(
            backend="mavsdk",
            connected=True,
            state="AIRBORNE",
            message=f"MAVSDK takeoff to {alt_m:.1f}m",
            telemetry=self._telemetry,
        )

    def land(self) -> DroneStatus:
        if not self._connected:
            return self.status()
        self._run(self._land_async())
        self._state = "LANDED"
        self._message = "MAVSDK landing command sent"
        return DroneStatus(
            backend="mavsdk",
            connected=True,
            state="LANDED",
            message="MAVSDK landing command sent",
            telemetry=self._telemetry,
        )

    def failsafe(self, action: str) -> DroneStatus:
        if not self._connected:
            return self.status()
        self._run(self._failsafe_async(action))
        self._state = f"FAILSAFE_{action.upper()}"
        self._message = f"MAVSDK failsafe {action} command sent"
        return DroneStatus(
            backend="mavsdk",
            connected=True,
            state=f"FAILSAFE_{action.upper()}",
            message=f"MAVSDK failsafe {action} command sent",
            telemetry=self._telemetry,
        )

    def stop(self) -> DroneStatus:
        if not self._connected:
            return self.status()
        self._run(self._failsafe_async("hold"))
        self._telemetry.ground_speed_mps = 0.0
        self._telemetry.last_update_s = time.time()
        self._state = "STOPPED"
        self._message = "Operator stop requested"
        return DroneStatus(
            backend="mavsdk",
            connected=True,
            state="STOPPED",
            message="Operator stop requested",
            telemetry=self._telemetry,
        )

    def status(self) -> DroneStatus:
        state = self._state if self._connected else "DISCONNECTED"
        message = self._message if self._connected else "MAVSDK not connected"
        return DroneStatus(
            backend="mavsdk",
            connected=self._connected,
            state=state,
            message=message,
            telemetry=self._telemetry,
        )


class DroneManager:
    def __init__(self) -> None:
        self._backend: DroneBridge = SimulatedDroneBridge()
        self._backend_name = "sim"

    def configure_backend(self, backend: str) -> None:
        backend_name = backend.lower().strip()
        if backend_name == "sim":
            self._backend = SimulatedDroneBridge()
            self._backend_name = "sim"
            return

        if backend_name == "mavsdk":
            try:
                __import__("mavsdk")
            except Exception as exc:
                raise RuntimeError("MAVSDK backend requested but mavsdk package is not installed") from exc
            self._backend = MavsdkDroneBridge()
            self._backend_name = "mavsdk"
            return

        raise ValueError(f"Unsupported backend: {backend}")

    def _as_payload(self, status: DroneStatus) -> dict:
        payload = asdict(status)
        payload["backend"] = self._backend_name
        return payload

    def connect(self, connection_uri: str | None = None) -> dict:
        return self._as_payload(self._backend.connect(connection_uri))

    def disconnect(self) -> dict:
        return self._as_payload(self._backend.disconnect())

    def fly_to(self, lat: float, lon: float, alt_m: float) -> dict:
        return self._as_payload(self._backend.fly_to(lat, lon, alt_m))

    def status(self) -> dict:
        return self._as_payload(self._backend.status())

    def arm(self) -> dict:
        return self._as_payload(self._backend.arm())

    def takeoff(self, alt_m: float) -> dict:
        return self._as_payload(self._backend.takeoff(alt_m))

    def land(self) -> dict:
        return self._as_payload(self._backend.land())

    def failsafe(self, action: str) -> dict:
        return self._as_payload(self._backend.failsafe(action))

    def stop(self) -> dict:
        return self._as_payload(self._backend.stop())
